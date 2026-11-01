from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user
from models import Stream, User
from telegram import telegram_service

router = APIRouter(tags=["Telegram Webhooks (B2)"])


class TelegramConfigRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: Optional[bool] = None


class TelegramSendRequest(BaseModel):
    chat_id: Optional[str] = None
    text: str = Field(min_length=1, max_length=4000)


class TelegramSimulateRequest(BaseModel):
    command: str = Field(default="/live", description="Command to simulate: /start, /live, /status, /help")
    chat_id: Optional[str] = None


@router.get("/api/telegram/status")
async def get_telegram_status():
    """Returns Telegram Bot status, target channel, and recent webhook events."""
    return telegram_service.get_status()


@router.get("/api/telegram/history")
async def get_telegram_history(limit: int = Query(default=20, ge=1, le=100)):
    """Audit log of all sent Telegram notifications and received webhooks."""
    return {
        "total": len(telegram_service.delivery_history),
        "items": telegram_service.delivery_history[-limit:],
    }


@router.post("/api/telegram/config")
async def update_telegram_config(
    payload: TelegramConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """Update Telegram bot token, target chat ID, or enable/disable bot."""
    if payload.bot_token is not None:
        telegram_service.bot_token = payload.bot_token.strip()
    if payload.chat_id is not None:
        telegram_service.default_chat_id = payload.chat_id.strip()
    if payload.enabled is not None:
        telegram_service.enabled = payload.enabled
    return telegram_service.get_status()


@router.post("/api/telegram/test")
async def send_telegram_test_message(
    chat_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Sends a verification test alert to Telegram to confirm integration."""
    username = current_user.username if current_user else "Admin"
    text = (
        f"<b>STREAMHUB TELEGRAM INTEGRATION TEST</b>\n\n"
        f"Verified by: @{username}\n"
        f"Status: Webhook and Bot API connection operational.\n"
        f"Mode: Real-time broadcast ready."
    )
    result = await telegram_service.send_message(chat_id=chat_id, text=text)
    return result


@router.post("/api/telegram/broadcast")
async def send_telegram_broadcast(
    payload: TelegramSendRequest,
    current_user: User = Depends(get_current_user),
):
    """Broadcasts a custom announcement message to the target Telegram channel."""
    return await telegram_service.send_message(chat_id=payload.chat_id, text=payload.text)


@router.post("/api/streams/{stream_id}/telegram/notify")
async def notify_stream_live_endpoint(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually triggers a Telegram live announcement for the given stream.
    Used by creators or automated hooks when going live.
    """
    result = await db.execute(
        select(Stream, User).join(User, Stream.user_id == User.id).where(Stream.id == stream_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    stream, owner = row

    if not stream.is_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Стрім '{stream.title}' зараз офлайн. Розсилка сповіщень можлива лише для активних трансляцій.",
        )

    alert_result = await telegram_service.notify_stream_live(
        stream_id=stream.id,
        title=stream.title,
        owner=owner.username,
        description=stream.description or "",
    )
    return {
        "message": f"Сповіщення для активного стріму '{stream.title}' надіслано в Telegram",
        "result": alert_result,
    }


@router.post("/api/webhooks/telegram")
async def receive_telegram_webhook(
    update: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Incoming Telegram Webhook Handler.
    Registered with Telegram setWebhook to receive commands (/start, /live, /status, /help)
    and reply with real-time StreamHub data.
    """
    return await telegram_service.handle_webhook_update(update, db)


@router.post("/api/webhooks/telegram/simulate")
async def simulate_telegram_command(
    payload: TelegramSimulateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simulates an incoming Telegram update with the given command (/live, /status, /start, etc.)
    and executes the bot logic. Useful for testing and demos without an external Telegram bot account.
    """
    simulated_update = {
        "update_id": 999999,
        "message": {
            "message_id": 8888,
            "date": 1700000000,
            "chat": {
                "id": payload.chat_id or telegram_service.default_chat_id,
                "type": "supergroup",
                "title": "StreamHub Community",
            },
            "from": {
                "id": 12345678,
                "is_bot": False,
                "first_name": "DemoViewer",
                "username": "demoviewer",
            },
            "text": payload.command,
        },
    }
    return await telegram_service.handle_webhook_update(simulated_update, db)
