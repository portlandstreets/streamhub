import asyncio
import fnmatch
import json
import logging
import os
import re
import socket
import time
import urllib.parse
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("core.cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
# Local fallback if redis host is not reachable (e.g. localhost testing)
LOCAL_REDIS_URL = os.getenv("LOCAL_REDIS_URL", "redis://localhost:6379/0")


def is_redis_reachable(url: str, timeout: float = 0.2) -> bool:
    """Quick socket check before attempting aioredis initialization to avoid blocking DNS retries."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"

        # On Windows host, non-IP hosts like 'redis' stall on NetBIOS/DNS resolution
        if os.name == "nt" and not re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
            return False

        port = parsed.port or 6379
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False


class CacheManager:
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_memory_fallback: bool = False
        self._memory_cache: dict[str, tuple[float, str]] = {}
        self.hits: int = 0
        self.misses: int = 0
        self._last_connect_attempt: float = 0.0
        self._connect_retry_delay: float = 30.0  # seconds backoff between reconnect attempts

    async def get_client(self) -> Optional[aioredis.Redis]:
        if self.redis_client is not None:
            return self.redis_client

        if self.use_memory_fallback:
            return None

        now = time.time()
        self._last_connect_attempt = now

        for url in (REDIS_URL, LOCAL_REDIS_URL):
            reachable = is_redis_reachable(url, 0.2)
            if not reachable:
                continue

            try:
                client = aioredis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                    retry_on_timeout=False,
                )
                await client.ping()
                self.redis_client = client
                self.use_memory_fallback = False
                logger.info("Connected to Redis cache at %s", url)
                return self.redis_client
            except Exception as ex:
                logger.warning("Could not ping Redis at %s: %s", url, ex)
                try:
                    await client.aclose()
                except Exception:
                    pass
                continue

        self.use_memory_fallback = True
        return None

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve cached JSON object by key."""
        client = await self.get_client()
        raw_val = None

        if client and not self.use_memory_fallback:
            try:
                raw_val = await client.get(key)
            except Exception as ex:
                logger.warning("Redis error on get(%s): %s. Falling back to memory.", key, ex)
                self.use_memory_fallback = True

        if raw_val is None and self.use_memory_fallback:
            entry = self._memory_cache.get(key)
            if entry:
                expire_at, val = entry
                if time.time() < expire_at:
                    raw_val = val
                else:
                    self._memory_cache.pop(key, None)

        if raw_val is not None:
            self.hits += 1
            try:
                return json.loads(raw_val)
            except Exception:
                return raw_val

        self.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: int = 15) -> bool:
        """Store value as JSON with a time-to-live (TTL) in seconds."""
        serialized = json.dumps(value, default=str) if not isinstance(value, str) else value
        client = await self.get_client()

        if client and not self.use_memory_fallback:
            try:
                await client.set(key, serialized, ex=ttl)
                return True
            except Exception as ex:
                logger.warning("Redis error on set(%s): %s. Storing in memory.", key, ex)
                self.use_memory_fallback = True

        self._memory_cache[key] = (time.time() + ttl, serialized)
        return True

    async def delete(self, *keys: str) -> None:
        """Delete specific keys."""
        if not keys:
            return
        client = await self.get_client()
        if client and not self.use_memory_fallback:
            try:
                await client.delete(*keys)
            except Exception as ex:
                logger.warning("Redis error on delete: %s", ex)

        for k in keys:
            self._memory_cache.pop(k, None)

    async def delete_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching a pattern (e.g. 'cache:streams:*')."""
        client = await self.get_client()
        if client and not self.use_memory_fallback:
            try:
                matched_keys = []
                async for key in client.scan_iter(match=pattern):
                    matched_keys.append(key)
                if matched_keys:
                    await client.delete(*matched_keys)
            except Exception as ex:
                logger.warning("Redis scan_iter error: %s", ex)

        # Invalidate in memory cache
        matching = [k for k in self._memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
        for k in matching:
            self._memory_cache.pop(k, None)

    async def invalidate_stream(self, stream_id: Optional[int] = None) -> None:
        """Invalidate stream list and specific stream caches."""
        await self.delete_pattern("cache:streams:*")
        if stream_id is not None:
            await self.delete_pattern(f"cache:stream:{stream_id}:*")
            await self.delete(f"cache:stream:{stream_id}")

    async def invalidate_recordings(self, stream_id: int) -> None:
        """Invalidate recordings cache for a stream."""
        await self.delete_pattern(f"cache:stream:{stream_id}:recordings*")
        await self.delete(f"cache:stream:{stream_id}:recordings")

    async def invalidate_settings(self, stream_id: int) -> None:
        """Invalidate 1:1 settings cache for a stream."""
        await self.delete(f"cache:stream:{stream_id}:settings")
        await self.delete(f"cache:stream:{stream_id}")

    async def flush_all(self) -> None:
        """Flush all API cache entries."""
        await self.delete_pattern("cache:*")
        self._memory_cache.clear()
        self.hits = 0
        self.misses = 0

    async def get_stats(self) -> dict[str, Any]:
        """Return cache performance statistics."""
        total = self.hits + self.misses
        hit_ratio = f"{(self.hits / total * 100):.2f}%" if total > 0 else "0.00%"
        cached_keys = []

        client = await self.get_client()
        backend = "redis"
        if client and not self.use_memory_fallback:
            try:
                async for key in client.scan_iter(match="cache:*"):
                    cached_keys.append(key)
            except Exception:
                backend = "in-memory (redis degraded)"
        else:
            backend = "in-memory"
            now = time.time()
            cached_keys = [k for k, (exp, _) in self._memory_cache.items() if exp > now]

        return {
            "backend": backend,
            "status": "healthy",
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total,
            "hit_ratio": hit_ratio,
            "cached_keys_count": len(cached_keys),
            "cached_keys": cached_keys[:20],
        }

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


# Global singleton cache instance
cache = CacheManager()
