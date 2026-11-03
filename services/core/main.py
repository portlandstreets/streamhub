import asyncio
import hmac
import json
import logging
import os
from datetime import datetime
from urllib.request import urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache import cache
from controllers import analytics, auth, cache_admin, features, mcp, queue, recordings, social, storage, streams, telegram, users
from database import AsyncSessionLocal, create_tables, get_db
from models import ChatMessage, Stream, User
from schemas import MediaMTXAuthPayload

logger = logging.getLogger("core")
STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/storage")
MEDIAMTX_API_URL = os.getenv("MEDIAMTX_API_URL", "http://mediamtx:9997/v3/paths/list")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
CHAT_HISTORY_LIMIT = 100
os.makedirs(os.path.join(STORAGE_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(STORAGE_DIR, "recordings"), exist_ok=True)

app = FastAPI(title="StreamHub Core API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(streams.router)
app.include_router(recordings.router)
app.include_router(social.router)
app.include_router(cache_admin.router)
app.include_router(telegram.router)
app.include_router(queue.router)
app.include_router(features.router)
app.include_router(analytics.router)
app.include_router(mcp.router)
app.include_router(storage.router)


class InternalChatMessage(BaseModel):
    stream_id: int
    username: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=500)
    is_bot: bool = False
    created_at: datetime | None = None


def get_ready_paths() -> set[str]:
    with urlopen(MEDIAMTX_API_URL, timeout=3) as response:
        payload = json.load(response)
    return {
        item["name"]
        for item in payload.get("items", [])
        if item.get("ready") is True and isinstance(item.get("name"), str)
    }


async def sync_stream_lifecycle():
    while True:
        try:
            ready_paths = await asyncio.to_thread(get_ready_paths)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Stream, User)
                    .join(User, Stream.user_id == User.id)
                    .order_by(Stream.user_id, Stream.created_at.desc())
                )
                state_changed = False
                seen_live_users = set()
                for stream, owner in result.all():
                    is_owner_streaming = f"live/{owner.stream_key}" in ready_paths
                    # Only the most recent/active stream of a user becomes LIVE
                    if is_owner_streaming and owner.id not in seen_live_users:
                        new_live = True
                        seen_live_users.add(owner.id)
                    else:
                        new_live = False

                    if stream.is_live != new_live:
                        stream.is_live = new_live
                        state_changed = True
                        # B2 Requirement: Outgoing Webhook / Telegram Alert when stream goes live
                        if new_live:
                            try:
                                from telegram import telegram_service
                                asyncio.create_task(
                                    telegram_service.notify_stream_live(
                                        stream_id=stream.id,
                                        title=stream.title,
                                        owner=owner.username,
                                        description=stream.description or "",
                                    )
                                )
                            except Exception as ex:
                                logger.warning("Could not dispatch Telegram live alert: %s", ex)
                if state_changed:
                    await db.commit()
                    await cache.invalidate_stream()
        except Exception:
            logger.exception("Could not synchronize stream status from MediaMTX")
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup_event():
    if os.getenv("TESTING") == "1":
        return
    await create_tables()
    app.state.lifecycle_task = asyncio.create_task(sync_stream_lifecycle())
    try:
        from controllers.streams import sync_search_index
        async with AsyncSessionLocal() as db:
            await sync_search_index(db)
    except Exception as e:
        logger.warning("Could not sync search index on startup: %s", e)

    # B8 Requirement: Start Background Message Queue Consumers / Workers
    try:
        from job_queue import async_job_queue
        await async_job_queue.start()
    except Exception as e:
        logger.warning("Could not start background queue workers: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "lifecycle_task", None)
    if task:
        task.cancel()
    try:
        from job_queue import async_job_queue
        await async_job_queue.stop()
    except Exception:
        logger.exception("Could not stop background queue workers cleanly")
    await cache.close()


@app.post("/api/streams/auth")
async def authenticate_stream(
    payload: MediaMTXAuthPayload,
    db: AsyncSession = Depends(get_db),
):
    if payload.action not in (None, "publish"):
        raise HTTPException(status_code=403, detail="Only publishing is authorized")

    # Extract stream key from path (e.g. "live/live_abc123" -> "live_abc123")
    raw_path = (payload.path or "").split("?")[0].strip()
    parts = [p for p in raw_path.split("/") if p]
    candidate = parts[-1] if parts else ""

    # If path was just "live" or empty, try payload password or user
    if not candidate or candidate.lower() in ("live", "app", "stream"):
        candidate = (payload.password or payload.user or "").strip()

    stream_key = candidate
    logger.info("MediaMTX auth request: path=%s, user=%s, candidate_key=%s", payload.path, payload.user, stream_key)

    if not stream_key:
        raise HTTPException(status_code=400, detail="Stream key missing")

    result = await db.execute(select(User).where(User.stream_key == stream_key))
    user = result.scalars().first()
    if user is None:
        logger.warning("MediaMTX auth failed: Invalid stream key '%s'", stream_key)
        raise HTTPException(status_code=401, detail="Invalid stream key")

    logger.info("MediaMTX auth success for user: %s (key: %s)", user.username, stream_key)
    return {"status": "authorized"}


@app.get("/api/streams/{stream_id}/chat/messages")
async def list_chat_messages(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.stream_id == stream_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(CHAT_HISTORY_LIMIT)
    )
    return [
        {
            "id": message.id,
            "user": message.username,
            "text": message.text,
            "is_bot": message.is_bot,
            "timestamp": message.created_at.isoformat(),
        }
        for message in reversed(result.scalars().all())
    ]


@app.post("/api/internal/chat/messages", status_code=status.HTTP_201_CREATED)
async def save_chat_message(
    message: InternalChatMessage,
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not INTERNAL_API_TOKEN or not x_internal_token or not hmac.compare_digest(
        x_internal_token, INTERNAL_API_TOKEN
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if await db.get(Stream, message.stream_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    saved = ChatMessage(
        stream_id=message.stream_id,
        username=message.username,
        text=message.text,
        is_bot=message.is_bot,
        created_at=message.created_at or datetime.utcnow(),
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return {"id": saved.id, "timestamp": saved.created_at.isoformat()}
