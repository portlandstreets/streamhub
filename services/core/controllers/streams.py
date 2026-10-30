from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from cache import cache
from database import get_db
from dependencies import get_current_user
from models import Stream, User
from search import search_engine
from schemas import (
    StreamCreate,
    StreamRead,
    StreamSettingsRead,
    StreamSettingsUpdate,
    StreamUpdate,
)
from services import (
    create_stream,
    delete_stream,
    ensure_stream_owner,
    get_or_create_stream_settings,
    get_stream_or_404,
    update_stream,
    update_stream_settings,
)

router = APIRouter(prefix="/api/streams", tags=["Streams"])


def stream_response(stream: Stream, owner: User) -> dict:
    created_at = stream.created_at
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "id": stream.id,
        "title": stream.title,
        "description": stream.description,
        "is_live": stream.is_live,
        "viewers_count": stream.viewers_count,
        "user_id": stream.user_id,
        "owner": owner.username,
        "playback_url": f"http://localhost:8888/live/{owner.stream_key}/index.m3u8",
        "thumbnail_url": stream.thumbnail_url
        or f"http://localhost:8000/static/storage/thumbnails/{owner.stream_key}.jpg",
        "created_at": created_at,
    }


# --- B1 Pagination API (Supports skip / limit / nextLink & OData $skip / $top) ---
@router.get("")
async def list_streams(
    request: Request,
    response: Response,
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of items to return"),
    top: Optional[int] = Query(default=None, alias="$top", ge=1, le=100, description="OData $top alias for limit"),
    odata_skip: Optional[int] = Query(default=None, alias="$skip", ge=0, description="OData $skip alias for skip"),
    live_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if odata_skip is not None:
        skip = odata_skip
    if top is not None:
        limit = top

    cache_key = f"cache:streams:live={live_only}:skip={skip}:limit={limit}"
    cached = await cache.get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Cache-Key"] = cache_key
        return cached

    # 1. Total matching count
    count_query = select(func.count(Stream.id))
    if live_only:
        count_query = count_query.where(Stream.is_live.is_(True))
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0

    # 2. Paginated rows
    query = select(Stream, User).join(User, Stream.user_id == User.id)
    if live_only:
        query = query.where(Stream.is_live.is_(True))
    query = query.order_by(Stream.is_live.desc(), Stream.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = [stream_response(stream, owner) for stream, owner in result.all()]

    # 3. Next and Prev links (supports both standard REST nextLink and OData @odata.nextLink)
    is_odata = (top is not None) or (odata_skip is not None)
    next_link = None
    if skip + limit < total_count:
        if is_odata:
            next_link = str(request.url.include_query_params(**{"$skip": skip + limit, "$top": limit}))
        else:
            next_link = str(request.url.include_query_params(skip=skip + limit, limit=limit))

    prev_link = None
    if skip > 0:
        prev_skip = max(0, skip - limit)
        if is_odata:
            prev_link = str(request.url.include_query_params(**{"$skip": prev_skip, "$top": limit}))
        else:
            prev_link = str(request.url.include_query_params(skip=prev_skip, limit=limit))

    data = {
        "items": items,
        "value": items,
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "nextLink": next_link,
        "prevLink": prev_link,
        "@odata.count": total_count,
        "@odata.nextLink": next_link,
    }

    await cache.set(cache_key, data, ttl=10)
    response.headers["X-Cache"] = "MISS"
    response.headers["X-Cache-Key"] = cache_key
    return data


async def sync_search_index(db: AsyncSession) -> int:
    """Sync all streams from DB into search index."""
    result = await db.execute(select(Stream, User).join(User, Stream.user_id == User.id))
    rows = result.all()
    for s, u in rows:
        await search_engine.index_stream(
            s.id,
            {
                "id": s.id,
                "title": s.title,
                "description": s.description or "",
                "owner": u.username,
                "is_live": s.is_live,
                "viewers_count": s.viewers_count,
                "thumbnail_url": s.thumbnail_url,
                "created_at": s.created_at.isoformat() if hasattr(s.created_at, "isoformat") else str(s.created_at),
            },
        )
    return len(rows)


# --- B4 Enterprise Full-Text Search Endpoint (Elasticsearch / Lucene) ---
@router.get("/search")
async def fulltext_search(
    q: str = Query(default="", description="Search query string"),
    fuzzy: bool = Query(default=True, description="Enable fuzzy typo-tolerant matching"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query_str = q.strip()
    if not query_str:
        return {
            "query": "",
            "total_hits": 0,
            "took_ms": 0.0,
            "engine": "Elasticsearch / Lucene",
            "results": [],
        }

    # Ensure search engine has initial index populated
    if len(search_engine.embedded_lucene.documents) == 0:
        await sync_search_index(db)

    search_result = await search_engine.search(query_str, fuzzy=fuzzy, limit=limit)
    return search_result


@router.get("/search/status")
async def search_status(db: AsyncSession = Depends(get_db)):
    if len(search_engine.embedded_lucene.documents) == 0:
        await sync_search_index(db)
    return await search_engine.get_status()


@router.post("/search/reindex")
async def search_reindex(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await sync_search_index(db)
    status_info = await search_engine.get_status()
    return {"message": f"Successfully reindexed {count} streams", "status": status_info}


# --- F2 Autocomplete Endpoint (Supports high-volume search, min 3 chars, Select2 compatible) ---
@router.get("/autocomplete")
async def autocomplete_streams(
    q: str = Query(default="", description="Search query string"),
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    query_str = q.strip()
    # F2 Requirement: Start searching after at least 3 characters have been entered
    if len(query_str) < 3:
        return {
            "results": [],
            "total": 0,
            "min_chars": 3,
            "message": "Minimum 3 characters required to trigger autocomplete search",
            "pagination": {"more": False},
        }

    # First, attempt fuzzy/fulltext search through Elasticsearch / Lucene
    if len(search_engine.embedded_lucene.documents) == 0:
        await sync_search_index(db)

    es_res = await search_engine.search(query_str, fuzzy=True, limit=limit)
    if es_res.get("results"):
        results = [
            {
                "id": r["id"],
                "text": f"{r['title']} (@{r['owner']})",
                "title": r["title"],
                "owner": r["owner"],
                "description": r["description"],
                "is_live": r["is_live"],
                "viewers_count": r.get("viewers_count", 0),
                "thumbnail_url": r.get("thumbnail_url"),
                "score": r.get("score"),
                "highlights": r.get("highlights", {}),
            }
            for r in es_res["results"]
        ]
        return {
            "results": results,
            "total": es_res.get("total_hits", len(results)),
            "pagination": {"more": False},
            "query": query_str,
            "engine": es_res.get("engine", "Search Engine"),
            "debounce_ms": 300,
            "min_chars": 3,
        }

    # Fallback to database query if needed
    search_filter = or_(
        Stream.title.ilike(f"%{query_str}%"),
        Stream.description.ilike(f"%{query_str}%"),
        User.username.ilike(f"%{query_str}%"),
    )
    offset = (page - 1) * limit

    # High-volume indexed search supporting millions of rows via pagination
    stmt = (
        select(Stream, User)
        .join(User, Stream.user_id == User.id)
        .where(search_filter)
        .order_by(Stream.is_live.desc(), Stream.viewers_count.desc(), Stream.title.asc())
        .offset(offset)
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    rows = result.all()
    has_more = len(rows) > limit
    items = rows[:limit]

    results = [
        {
            "id": s.id,
            "text": f"{s.title} (@{u.username})",
            "title": s.title,
            "owner": u.username,
            "description": s.description or "",
            "is_live": s.is_live,
            "viewers_count": s.viewers_count,
            "thumbnail_url": s.thumbnail_url or f"http://localhost:8000/static/storage/thumbnails/{u.stream_key}.jpg",
        }
        for s, u in items
    ]

    return {
        "results": results,
        "total": len(results),
        "pagination": {"more": has_more},
        "query": query_str,
        "debounce_ms": 300,
        "min_chars": 3,
    }


@router.get("/{stream_id}", response_model=StreamRead)
async def read_stream(stream_id: int, response: Response, db: AsyncSession = Depends(get_db)):
    cache_key = f"cache:stream:{stream_id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Cache-Key"] = cache_key
        return cached

    result = await db.execute(
        select(Stream, User)
        .join(User, Stream.user_id == User.id)
        .where(Stream.id == stream_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    data = stream_response(*row)

    await cache.set(cache_key, data, ttl=15)
    response.headers["X-Cache"] = "MISS"
    response.headers["X-Cache-Key"] = cache_key
    return data


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_stream(
    data: StreamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stream = await create_stream(data, current_user, db)
    await cache.invalidate_stream()
    await search_engine.index_stream(
        stream.id,
        {
            "id": stream.id,
            "title": stream.title,
            "description": stream.description or "",
            "owner": current_user.username,
            "is_live": stream.is_live,
            "viewers_count": stream.viewers_count,
            "thumbnail_url": stream.thumbnail_url,
        },
    )
    return {"id": stream.id, "title": stream.title, "user_id": stream.user_id}


@router.put("/{stream_id}")
async def edit_stream(
    stream_id: int,
    data: StreamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stream = await get_stream_or_404(stream_id, db)
    ensure_stream_owner(stream, current_user)
    updated = await update_stream(stream, data, db)
    await cache.invalidate_stream(stream_id)
    await search_engine.index_stream(
        updated.id,
        {
            "id": updated.id,
            "title": updated.title,
            "description": updated.description or "",
            "owner": current_user.username,
            "is_live": updated.is_live,
            "viewers_count": updated.viewers_count,
            "thumbnail_url": updated.thumbnail_url,
        },
    )
    return {"id": updated.id, "title": updated.title, "user_id": updated.user_id}


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_stream(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stream = await get_stream_or_404(stream_id, db)
    ensure_stream_owner(stream, current_user)
    await delete_stream(stream, db)
    await cache.invalidate_stream(stream_id)
    await search_engine.remove_stream(stream_id)


# --- 1:1 StreamSettings Endpoints ---
@router.get("/{stream_id}/settings", response_model=StreamSettingsRead)
async def read_stream_settings(stream_id: int, response: Response, db: AsyncSession = Depends(get_db)):
    cache_key = f"cache:stream:{stream_id}:settings"
    cached = await cache.get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Cache-Key"] = cache_key
        return cached

    stream = await get_stream_or_404(stream_id, db)
    settings = await get_or_create_stream_settings(stream, db)
    data = {
        "id": settings.id,
        "stream_id": settings.stream_id,
        "low_latency_enabled": settings.low_latency_enabled,
        "chat_enabled": settings.chat_enabled,
        "allow_recordings": settings.allow_recordings,
        "max_resolution": settings.max_resolution,
        "created_at": settings.created_at.isoformat() if hasattr(settings.created_at, "isoformat") else settings.created_at,
    }
    await cache.set(cache_key, data, ttl=30)
    response.headers["X-Cache"] = "MISS"
    response.headers["X-Cache-Key"] = cache_key
    return settings


@router.put("/{stream_id}/settings", response_model=StreamSettingsRead)
async def edit_stream_settings(
    stream_id: int,
    data: StreamSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stream = await get_stream_or_404(stream_id, db)
    ensure_stream_owner(stream, current_user)
    settings = await get_or_create_stream_settings(stream, db)
    updated = await update_stream_settings(settings, data, db)
    await cache.invalidate_settings(stream_id)
    return updated
