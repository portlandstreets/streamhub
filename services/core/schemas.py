from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class MediaMTXAuthPayload(BaseModel):
    action: Optional[str] = None
    path: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    ip: Optional[str] = None


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserLogin(BaseModel):
    username: str
    password: str


class OAuthLoginRequest(BaseModel):
    code: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    demo: Optional[bool] = False


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    stream_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StreamSettingsRead(BaseModel):
    id: int
    stream_id: int
    low_latency_enabled: bool
    chat_enabled: bool
    allow_recordings: bool
    max_resolution: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StreamSettingsUpdate(BaseModel):
    low_latency_enabled: Optional[bool] = None
    chat_enabled: Optional[bool] = None
    allow_recordings: Optional[bool] = None
    max_resolution: Optional[str] = Field(default=None, max_length=20)


class StreamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = Field(default=None, max_length=255)


class StreamUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = Field(default=None, max_length=255)


class StreamRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    is_live: bool
    viewers_count: int
    thumbnail_url: Optional[str]
    user_id: int
    owner: str
    playback_url: str
    created_at: datetime
    settings: Optional[StreamSettingsRead] = None


class RecordingCreate(BaseModel):
    file_path: str = Field(min_length=1, max_length=255)
    duration_seconds: int = Field(default=0, ge=0)


class RecordingUpdate(BaseModel):
    file_path: Optional[str] = Field(default=None, min_length=1, max_length=255)
    duration_seconds: Optional[int] = Field(default=None, ge=0)


class RecordingRead(BaseModel):
    id: int
    stream_id: int
    file_path: str
    duration_seconds: int
    created_at: datetime

    model_config = {"from_attributes": True}
