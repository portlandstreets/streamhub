import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Recording, Stream, StreamSettings, User
from schemas import (
    RecordingUpdate,
    StreamCreate,
    StreamSettingsUpdate,
    StreamUpdate,
    UserRegister,
    UserUpdate,
)
from security import get_password_hash

RECORDINGS_DIR = Path(os.getenv("STORAGE_DIR", "/app/storage")) / "recordings"
ALLOWED_RECORDING_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov"}
MAX_RECORDING_SIZE = 1024 * 1024 * 1024


async def register_user(data: UserRegister, db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        stream_key=User.generate_stream_key(),
    )
    db.add(user)
    await db.flush()
    initial_stream = Stream(
        title=f"{user.username}'s Broadcast",
        description="Low-latency microservices stream",
        user_id=user.id,
    )
    db.add(initial_stream)
    await db.flush()
    db.add(StreamSettings(stream_id=initial_stream.id))
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(user: User, data: UserUpdate, db: AsyncSession) -> User:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user fields provided")

    for field in ("username", "email"):
        value = changes.get(field)
        if value is not None:
            result = await db.execute(select(User).where(getattr(User, field) == value, User.id != user.id))
            if result.scalars().first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{field} already exists")
            setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def create_stream(data: StreamCreate, owner: User, db: AsyncSession) -> Stream:
    stream = Stream(**data.model_dump(), user_id=owner.id)
    db.add(stream)
    await db.flush()
    settings = StreamSettings(stream_id=stream.id)
    db.add(settings)
    await db.commit()
    await db.refresh(stream)
    return stream


async def get_stream_or_404(stream_id: int, db: AsyncSession) -> Stream:
    stream = await db.get(Stream, stream_id)
    if stream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    return stream


def ensure_stream_owner(stream: Stream, user: User) -> None:
    if stream.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this stream")


async def update_stream(stream: Stream, data: StreamUpdate, db: AsyncSession) -> Stream:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No stream fields provided")
    if changes.get("title") is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title cannot be null")

    for field, value in changes.items():
        setattr(stream, field, value)
    await db.commit()
    await db.refresh(stream)
    return stream


async def get_or_create_stream_settings(stream: Stream, db: AsyncSession) -> StreamSettings:
    result = await db.execute(select(StreamSettings).where(StreamSettings.stream_id == stream.id))
    settings = result.scalars().first()
    if settings is None:
        settings = StreamSettings(stream_id=stream.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_stream_settings(
    settings: StreamSettings,
    data: StreamSettingsUpdate,
    db: AsyncSession,
) -> StreamSettings:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings


async def store_recording_file(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_RECORDING_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported recording format",
        )

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    destination = RECORDINGS_DIR / filename
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_RECORDING_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Recording exceeds the 1 GB upload limit",
                    )
                output.write(chunk)

        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recording file is empty")
        return f"/static/storage/recordings/{filename}"
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_stored_recording_path(file_path: str) -> Path:
    prefix = "/static/storage/recordings/"
    if not file_path.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"file_path must begin with {prefix}",
        )

    filename = file_path.removeprefix(prefix)
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording file path")

    storage_directory = RECORDINGS_DIR.resolve()
    stored_file = (RECORDINGS_DIR / filename).resolve()
    if stored_file.parent != storage_directory:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording file path")
    if not stored_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording file not found")
    return stored_file


async def create_recording_from_path(
    stream: Stream,
    file_path: str,
    duration_seconds: int,
    db: AsyncSession,
) -> Recording:
    get_stored_recording_path(file_path)
    existing = await db.execute(select(Recording).where(Recording.file_path == file_path))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recording file is already linked to a recording",
        )

    recording = Recording(
        stream_id=stream.id,
        file_path=file_path,
        duration_seconds=duration_seconds,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    return recording


async def get_recording_or_404(recording_id: int, db: AsyncSession) -> Recording:
    recording = await db.get(Recording, recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return recording


async def update_recording(
    recording: Recording,
    data: RecordingUpdate,
    db: AsyncSession,
) -> Recording:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recording fields provided")
    if any(value is None for value in changes.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recording fields cannot be null",
        )

    old_file_path = recording.file_path
    if "file_path" in changes and changes["file_path"] != old_file_path:
        new_file_path = changes["file_path"]
        get_stored_recording_path(new_file_path)
        existing = await db.execute(
            select(Recording).where(Recording.file_path == new_file_path, Recording.id != recording.id)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recording file is already linked to a recording",
            )

    for field, value in changes.items():
        setattr(recording, field, value)
    await db.commit()
    await db.refresh(recording)
    if "file_path" in changes and old_file_path != recording.file_path:
        old_file = RECORDINGS_DIR / Path(old_file_path).name
        old_file.unlink(missing_ok=True)
    return recording


async def delete_recording(recording: Recording, db: AsyncSession) -> None:
    file_path = RECORDINGS_DIR / Path(recording.file_path).name
    await db.delete(recording)
    await db.commit()
    file_path.unlink(missing_ok=True)


async def delete_stream(stream: Stream, db: AsyncSession) -> None:
    recordings = await db.execute(select(Recording).where(Recording.stream_id == stream.id))
    file_paths = [RECORDINGS_DIR / Path(recording.file_path).name for recording in recordings.scalars()]
    await db.delete(stream)
    await db.commit()
    for file_path in file_paths:
        file_path.unlink(missing_ok=True)


async def delete_user(user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Recording)
        .join(Stream, Recording.stream_id == Stream.id)
        .where(Stream.user_id == user.id)
    )
    file_paths = [RECORDINGS_DIR / Path(recording.file_path).name for recording in result.scalars()]
    await db.delete(user)
    await db.commit()
    for file_path in file_paths:
        file_path.unlink(missing_ok=True)
