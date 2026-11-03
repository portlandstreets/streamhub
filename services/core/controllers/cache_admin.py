from fastapi import APIRouter, status

from cache import cache

router = APIRouter(prefix="/api/cache", tags=["Cache"])


@router.get("/stats")
async def get_cache_stats():
    """Return cache performance statistics including backend, hits, misses, hit ratio, and active keys."""
    return await cache.get_stats()


@router.post("/flush", status_code=status.HTTP_200_OK)
@router.delete("", status_code=status.HTTP_200_OK)
async def flush_cache():
    """Flush all API cache entries and reset hit/miss counters."""
    await cache.flush_all()
    return {"status": "cleared", "message": "All API cache keys flushed successfully"}
