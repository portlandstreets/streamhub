"""MCP JSON-RPC endpoint and tools for the StreamHub platform."""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlparse
from urllib.request import urlopen

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from blob_storage import blob_manager
from models import ChatMessage, Recording, Stream, User

logger = logging.getLogger("core.mcp")

router = APIRouter(prefix="/api/v1/mcp", tags=["Model Context Protocol (C22)"])

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "streamhub-mcp-server"
MCP_SERVER_VERSION = "2.1.0"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MEDIAMTX_API_URL = os.getenv(
    "MEDIAMTX_API_URL", "http://mediamtx:9997/v3/paths/list"
)
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
MAX_SEARCH_RESULTS = 20

TOXIC_KEYWORDS_REGEX = re.compile(
    r"\b(?:fuck|fucking|bitch|shit|asshole|сука|бля|блять|хуй|хуйня|пиздец|"
    r"піздец|єбать|ебать|нахуй|мудак|дебіл|дебил|спам|spam)\b",
    re.IGNORECASE,
)

MCP_TOOLS_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "name": "get_platform_status",
        "description": (
            "Read-only live infrastructure health check. Use when asked about "
            "MediaMTX, RTMP port 1935, HLS port 8888, Redis, Elasticsearch, "
            "or database connectivity. Returns measured component status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_active_streams",
        "description": (
            "Read-only list of currently active StreamHub broadcasts, "
            "including channel ID, title, owner, and viewer count. Use when "
            "the user asks which streams are live."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "description": "Maximum active channels to return.",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "search_streams",
        "description": (
            "Read-only search for stream channels and VOD recordings by "
            "stream title, description, or recording file name. Use when the "
            "user asks to find a broadcast or recording."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": "Search phrase to match against stream and recording data.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "moderate_chat",
        "description": (
            "Write tool for chat moderation. Only use after an explicit "
            "moderation request with the exact channel ID and registered "
            "user ID. Actions: delete all of that user's messages in this "
            "channel, or ban/mute that user from sending further chat messages. "
            "Require a reason and never invent identifiers."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "pattern": "^[0-9]+$",
                    "description": "Numeric ID of the channel to moderate.",
                },
                "user_id": {
                    "type": "string",
                    "pattern": "^[0-9]+$",
                    "description": "Numeric ID of the registered chat user to moderate.",
                },
                "action": {
                    "type": "string",
                    "enum": ["delete", "ban", "mute"],
                    "description": "Delete the user's channel messages, or ban/mute the user.",
                },
                "reason": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                    "description": "Moderator-provided reason for the action.",
                },
            },
            "required": ["channel_id", "user_id", "action", "reason"],
            "additionalProperties": False,
        },
    },
]

_TOOL_BY_NAME = {tool["name"]: tool for tool in MCP_TOOLS_DEFINITIONS}
_LEGACY_TOOL_SCHEMAS = {
    "set_ai_moderation": {
        "properties": {
            "stream_id": {"type": "integer"},
            "enabled": {"type": "boolean"},
            "requester_username": {"type": "string"},
        },
        "required": ["stream_id"],
    },
    "moderate_chat_legacy": {
        "properties": {
            "stream_id": {"type": "integer"},
            "filter_type": {
                "type": "string",
                "enum": ["toxic", "all_recent", "pattern"],
            },
            "text_pattern": {"type": "string"},
            "count": {"type": "integer", "minimum": 1, "maximum": 50},
            "requester_username": {"type": "string"},
        },
        "required": ["stream_id"],
    },
}


async def _tcp_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        del reader
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _read_mediamtx_paths() -> list[Dict[str, Any]]:
    with urlopen(MEDIAMTX_API_URL, timeout=2) as response:
        payload = json.load(response)
    return payload.get("items", [])


async def _redis_ping() -> bool:
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()


async def _get_platform_telemetry(db: AsyncSession) -> Dict[str, Any]:
    try:
        await db.execute(text("SELECT 1"))
        database_status = "healthy"
    except Exception:
        logger.exception("MCP telemetry database health check failed")
        database_status = "unavailable"

    media_url = urlparse(MEDIAMTX_API_URL)
    media_host = media_url.hostname or "mediamtx"
    media_api_status = "unavailable"
    ready_paths: list[Dict[str, Any]] = []
    try:
        ready_paths = await asyncio.to_thread(_read_mediamtx_paths)
        media_api_status = "healthy"
    except Exception:
        logger.warning("MediaMTX API health check failed", exc_info=True)

    try:
        redis_status = "healthy" if await _redis_ping() else "unavailable"
    except Exception:
        logger.warning("Redis health check failed", exc_info=True)
        redis_status = "unavailable"

    elasticsearch_url = urlparse(ELASTICSEARCH_URL)
    elasticsearch_host = elasticsearch_url.hostname or "elasticsearch"
    elasticsearch_port = elasticsearch_url.port or 9200
    rtmp_port = int(os.getenv("MEDIAMTX_RTMP_PORT", "1935"))
    hls_port = int(os.getenv("MEDIAMTX_HLS_PORT", "8888"))

    rtmp_open, hls_open, elasticsearch_open = await asyncio.gather(
        _tcp_port_open(media_host, rtmp_port),
        _tcp_port_open(media_host, hls_port),
        _tcp_port_open(elasticsearch_host, elasticsearch_port),
    )
    components = {
        "database": database_status,
        "mediamtx_api": media_api_status,
        "mediamtx_rtmp": {
            "status": "healthy" if rtmp_open else "unavailable",
            "host": media_host,
            "port": rtmp_port,
        },
        "mediamtx_hls": {
            "status": "healthy" if hls_open else "unavailable",
            "host": media_host,
            "port": hls_port,
        },
        "redis": redis_status,
        "elasticsearch": {
            "status": "healthy" if elasticsearch_open else "unavailable",
            "host": elasticsearch_host,
            "port": elasticsearch_port,
        },
    }
    component_states = [
        database_status,
        media_api_status,
        "healthy" if rtmp_open else "unavailable",
        "healthy" if hls_open else "unavailable",
        redis_status,
        "healthy" if elasticsearch_open else "unavailable",
    ]
    return {
        "status": "healthy" if all(state == "healthy" for state in component_states) else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mediamtx": {
            "api_url": MEDIAMTX_API_URL,
            "ready_path_count": sum(1 for path in ready_paths if path.get("ready") is True),
            "paths": [
                {
                    "name": path.get("name"),
                    "ready": path.get("ready") is True,
                    "readers": len(path.get("readers") or []),
                }
                for path in ready_paths
            ],
        },
        "components": components,
    }


async def _list_active_streams(db: AsyncSession, limit: int) -> Dict[str, Any]:
    result = await db.execute(
        select(Stream, User)
        .join(User, Stream.user_id == User.id)
        .where(Stream.is_live.is_(True))
        .order_by(Stream.viewers_count.desc(), Stream.created_at.desc())
        .limit(limit)
    )
    items = [
        {
            "channel_id": str(stream.id),
            "title": stream.title,
            "owner": owner.username,
            "viewers_count": stream.viewers_count or 0,
            "is_live": bool(stream.is_live),
            "created_at": stream.created_at.isoformat() if stream.created_at else None,
        }
        for stream, owner in result.all()
    ]
    return {"count": len(items), "streams": items}


async def _search_content(
    db: AsyncSession, query: str, limit: int
) -> Dict[str, Any]:
    needle = query.strip()
    if not needle:
        raise ValueError("query must not be empty")

    matching_streams = await db.execute(
        select(Stream, User)
        .join(User, Stream.user_id == User.id)
        .where(
            or_(
                Stream.title.contains(needle, autoescape=True),
                Stream.description.contains(needle, autoescape=True),
                User.username.contains(needle, autoescape=True),
            )
        )
        .order_by(Stream.created_at.desc())
        .limit(limit)
    )
    matching_recordings = await db.execute(
        select(Recording, Stream.title)
        .join(Stream, Recording.stream_id == Stream.id)
        .where(
            or_(
                Stream.title.contains(needle, autoescape=True),
                Recording.file_path.contains(needle, autoescape=True),
            )
        )
        .order_by(Recording.created_at.desc())
        .limit(limit)
    )
    matching_users = await db.execute(
        select(User.id, User.username)
        .where(User.username.contains(needle, autoescape=True))
        .order_by(User.username)
        .limit(limit)
    )

    streams = [
        {
            "channel_id": str(stream.id),
            "title": stream.title,
            "description": stream.description or "",
            "owner": owner.username,
            "is_live": bool(stream.is_live),
            "viewers_count": stream.viewers_count or 0,
        }
        for stream, owner in matching_streams.all()
    ]
    recordings = [
        {
            "recording_id": str(recording.id),
            "channel_id": str(recording.stream_id),
            "title": title,
            "file_name": _recording_file_name(recording.file_path),
            "duration_seconds": recording.duration_seconds or 0,
            "created_at": recording.created_at.isoformat() if recording.created_at else None,
        }
        for recording, title in matching_recordings.all()
    ]
    users = [
        {"user_id": str(user_id), "username": username}
        for user_id, username in matching_users.all()
    ]
    return {
        "query": needle,
        "counts": {
            "streams": len(streams),
            "recordings": len(recordings),
            "users": len(users),
        },
        "streams": streams,
        "recordings": recordings,
        "users": users,
    }


def _recording_file_name(file_path: str) -> str:
    blob_prefix = "/api/v1/storage/cdn/streamhub-vods/"
    if file_path.startswith(blob_prefix):
        key = file_path.removeprefix(blob_prefix)
        metadata = blob_manager.get_blob_metadata("streamhub-vods", key)
        original_filename = metadata.get("custom", {}).get("original_filename")
        if isinstance(original_filename, str) and original_filename:
            return original_filename
    return file_path.rsplit("/", 1)[-1]


async def _publish_chat_moderation(
    channel_id: int,
    message_ids: list[int],
    action: str,
    username: str,
    reason: str,
) -> Dict[str, Any]:
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    state = {
        "chat_policy_applied": action == "delete",
        "broadcast_delivered": False,
        "errors": [],
    }
    try:
        if action in {"ban", "mute"}:
            policy_key = f"chat:moderation:{channel_id}:{action}:{username.casefold()}"
            try:
                await client.set(
                    policy_key,
                    json.dumps(
                        {
                            "username": username,
                            "reason": reason,
                            "message_ids": message_ids,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                )
                state["chat_policy_applied"] = True
            except Exception as exc:
                logger.exception("Could not apply the chat moderation policy")
                state["errors"].append(f"policy: {exc}")
        if message_ids:
            try:
                await client.publish(
                    f"chat:stream:{channel_id}",
                    json.dumps(
                        {"type": "delete_messages", "message_ids": message_ids},
                        ensure_ascii=False,
                    ),
                )
                state["broadcast_delivered"] = True
            except Exception as exc:
                logger.exception("Could not broadcast chat message deletion")
                state["errors"].append(f"broadcast: {exc}")
        else:
            state["broadcast_delivered"] = True
    finally:
        await client.aclose()
    return state


async def _moderate_chat_message(
    db: AsyncSession, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    channel_raw = arguments.get("channel_id")
    user_raw = arguments.get("user_id")
    action = arguments.get("action")
    reason = str(arguments.get("reason", "")).strip()
    if not isinstance(channel_raw, str) or not channel_raw.isdigit():
        raise ValueError("channel_id must be a numeric string")
    if not isinstance(user_raw, str) or not user_raw.isdigit():
        raise ValueError("user_id must be a numeric string")
    if action not in {"delete", "ban", "mute"}:
        raise ValueError("action must be delete, ban, or mute")
    if not reason:
        raise ValueError("reason must not be empty")

    channel_id, user_id = int(channel_raw), int(user_raw)
    stream = await db.get(Stream, channel_id)
    if stream is None:
        raise ValueError(f"Channel {channel_id} was not found")
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} was not found")

    username = user.username
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.stream_id == channel_id,
            ChatMessage.username == username,
        )
    )
    messages = result.scalars().all()
    message_ids = [message.id for message in messages]
    for message in messages:
        await db.delete(message)
    if message_ids:
        await db.commit()
    try:
        moderation_state = await _publish_chat_moderation(
            channel_id, message_ids, action, username, reason
        )
    except Exception as exc:
        logger.exception("Could not apply or broadcast chat moderation")
        moderation_state = {
            "chat_policy_applied": False if action != "delete" else None,
            "broadcast_delivered": False,
            "errors": [str(exc)],
        }
    if moderation_state["errors"]:
        return {
            "status": "partial_failure",
            "action": action,
            "channel_id": str(channel_id),
            "user_id": str(user_id),
            "username": username,
            "deleted_message_count": len(message_ids),
            "message_ids": message_ids,
            "chat_policy_applied": moderation_state["chat_policy_applied"],
            "broadcast_delivered": moderation_state["broadcast_delivered"],
            "errors": moderation_state["errors"],
        }
    return {
        "status": "success",
        "action": action,
        "channel_id": str(channel_id),
        "user_id": str(user_id),
        "username": username,
        "reason": reason,
        "deleted_message_count": len(message_ids),
        "message_ids": message_ids,
        "chat_policy_applied": moderation_state["chat_policy_applied"],
        "broadcast_delivered": moderation_state["broadcast_delivered"],
    }


async def _set_ai_moderation(stream_id: int, enabled: bool) -> Dict[str, Any]:
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.set(
            f"stream:{stream_id}:ai_moderation", "1" if enabled else "0"
        )
    finally:
        await client.aclose()
    return {"status": "success", "stream_id": stream_id, "enabled": enabled}


async def _legacy_moderate_chat(
    db: AsyncSession, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    stream_id = int(arguments.get("stream_id", 0))
    stream = await db.get(Stream, stream_id)
    if stream is None:
        raise ValueError(f"Channel {stream_id} was not found")
    limit = min(max(int(arguments.get("count", 20)), 1), 50)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.stream_id == stream_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    filter_type = arguments.get("filter_type", "toxic")
    text_pattern = str(arguments.get("text_pattern", "")).strip().casefold()
    messages = result.scalars().all()
    if filter_type == "all_recent":
        matched = messages
    elif filter_type == "pattern" and text_pattern:
        matched = [message for message in messages if text_pattern in message.text.casefold()]
    else:
        matched = [message for message in messages if TOXIC_KEYWORDS_REGEX.search(message.text)]
    ids = [message.id for message in matched]
    for message in matched:
        await db.delete(message)
    if ids:
        await db.commit()
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            await client.publish(
                f"chat:stream:{stream_id}",
                json.dumps({"type": "delete_messages", "message_ids": ids}),
            )
        finally:
            await client.aclose()
    return {"status": "success", "stream_id": stream_id, "deleted_count": len(ids), "deleted_message_ids": ids}


async def execute_mcp_tool(
    name: str, arguments: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    """Execute a listed MCP tool or a legacy action used by the existing UI."""
    if name == "get_platform_status":
        return await _get_platform_telemetry(db)
    if name == "list_active_streams":
        limit = int(arguments.get("limit", 20))
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        return await _list_active_streams(db, limit)
    if name == "search_streams":
        query = arguments.get("query")
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
            raise ValueError("query must contain between 1 and 200 characters")
        return await _search_content(db, query, MAX_SEARCH_RESULTS)
    if name == "moderate_chat" and "channel_id" in arguments:
        return await _moderate_chat_message(db, arguments)

    # Keep actions used by the current StreamHub UI working without advertising
    # unrelated tools to the agent.
    if name == "set_ai_moderation":
        stream_id = int(arguments.get("stream_id", 0))
        if await db.get(Stream, stream_id) is None:
            raise ValueError(f"Channel {stream_id} was not found")
        return await _set_ai_moderation(
            stream_id, bool(arguments.get("enabled", True))
        )
    if name == "moderate_chat" and "stream_id" in arguments:
        return await _legacy_moderate_chat(db, arguments)
    raise ValueError(f"Unknown MCP tool '{name}'")


def _rpc_error(rpc_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": message},
    }


def _validate_tool_arguments(name: str, arguments: Any) -> str | None:
    if not isinstance(arguments, dict):
        return "Tool arguments must be a JSON object"
    if name == "moderate_chat" and "stream_id" in arguments:
        schema = _LEGACY_TOOL_SCHEMAS["moderate_chat_legacy"]
    elif name in _TOOL_BY_NAME:
        schema = _TOOL_BY_NAME[name]["inputSchema"]
    else:
        schema = _LEGACY_TOOL_SCHEMAS[name]
    missing = [key for key in schema.get("required", []) if key not in arguments]
    if missing:
        return f"Missing required argument(s): {', '.join(missing)}"
    unknown = set(arguments) - set(schema["properties"])
    if unknown:
        return f"Unknown argument(s): {', '.join(sorted(unknown))}"
    for key, value in arguments.items():
        definition = schema["properties"][key]
        if definition.get("type") == "string":
            if not isinstance(value, str):
                return f"Argument '{key}' must be a string"
            if len(value) < definition.get("minLength", 0):
                return f"Argument '{key}' is too short"
            if len(value) > definition.get("maxLength", 10**9):
                return f"Argument '{key}' is too long"
            if "enum" in definition and value not in definition["enum"]:
                return f"Argument '{key}' must be one of: {', '.join(definition['enum'])}"
        elif definition.get("type") == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return f"Argument '{key}' must be an integer"
            if not definition.get("minimum", value) <= value <= definition.get("maximum", value):
                return f"Argument '{key}' is outside its allowed range"
        elif definition.get("type") == "boolean" and not isinstance(value, bool):
            return f"Argument '{key}' must be a boolean"
    return None


@router.post("", response_model=None)
async def handle_mcp_jsonrpc(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any] | Response:
    """Handle MCP JSON-RPC 2.0 initialize, ping, tools/list, and tools/call."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _rpc_error(None, -32700, "Parse error")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return _rpc_error(body.get("id") if isinstance(body, dict) else None, -32600, "Invalid Request")

    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _rpc_error(rpc_id, -32600, "Invalid Request")
    if "id" not in body and method.startswith("notifications/"):
        if method == "notifications/initialized":
            return Response(status_code=202)
        return Response(status_code=202)

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
                "instructions": (
                    "Use read tools for platform telemetry, active streams, or "
                    "content search. The moderation tool changes chat state and "
                    "requires an explicit user request and exact IDs."
                ),
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": MCP_TOOLS_DEFINITIONS}}
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or (
            name not in _TOOL_BY_NAME and name not in _LEGACY_TOOL_SCHEMAS
        ):
            return _rpc_error(rpc_id, -32602, "Unknown tool name")
        arguments = params.get("arguments", {})
        validation_error = _validate_tool_arguments(name, arguments)
        if validation_error:
            return _rpc_error(rpc_id, -32602, validation_error)
        try:
            result = await execute_mcp_tool(name, arguments, db)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False),
                        }
                    ],
                    "isError": result.get("status") == "partial_failure",
                },
            }
        except (ValueError, TypeError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }
        except Exception as exc:
            logger.exception("MCP tool execution failed: %s", name)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}],
                    "isError": True,
                },
            }
    return _rpc_error(rpc_id, -32601, f"Method '{method}' not found")


@router.get("/tools")
async def list_tools_direct() -> Dict[str, Any]:
    return {
        "status": "success",
        "protocol": f"Model Context Protocol (MCP) {MCP_PROTOCOL_VERSION}",
        "server": f"{MCP_SERVER_NAME} v{MCP_SERVER_VERSION}",
        "total_tools": len(MCP_TOOLS_DEFINITIONS),
        "read_tools_count": 3,
        "write_tools_count": 1,
        "tools": MCP_TOOLS_DEFINITIONS,
    }


@router.get("/moderation/{stream_id}")
async def get_stream_moderation_status(stream_id: int) -> Dict[str, Any]:
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        value = await client.get(f"stream:{stream_id}:ai_moderation")
    except Exception:
        logger.exception("Could not read AI moderation status")
        raise HTTPException(status_code=503, detail="Moderation status is unavailable")
    finally:
        await client.aclose()
    return {"stream_id": stream_id, "ai_moderation": value != "0"}


@router.get("/sse")
async def mcp_sse_transport(request: Request) -> StreamingResponse:
    session_id = str(uuid.uuid4())

    async def event_generator():
        yield f"event: endpoint\ndata: /api/v1/mcp?session_id={session_id}\n\n"
        while not await request.is_disconnected():
            await asyncio.sleep(15)
            yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
