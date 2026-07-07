"""
Two-tier cache: Redis (production) → in-memory dict (local/fallback).
Usage:
    cache = get_cache()
    await cache.get("key")
    await cache.set("key", value, ttl=60)
"""
import json, time, asyncio
from typing import Any, Optional
from utils.logger import get_logger

log = get_logger("cache")

# ─── In-Memory Fallback ────────────────────────────────────────────────────────
class InMemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        expires_at = time.monotonic() + ttl if ttl else 0
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def flush(self) -> None:
        self._store.clear()

    async def ping(self) -> bool:
        return True


# ─── Redis Cache ───────────────────────────────────────────────────────────────
class RedisCache:
    def __init__(self, redis_client):
        self._r = redis_client

    async def get(self, key: str) -> Optional[Any]:
        try:
            raw = await self._r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            log.warning("redis.get.failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        try:
            serialized = json.dumps(value, default=str)
            await self._r.setex(key, ttl, serialized)
        except Exception as e:
            log.warning("redis.set.failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            await self._r.delete(key)
        except Exception as e:
            log.warning("redis.delete.failed", key=key, error=str(e))

    async def flush(self) -> None:
        try:
            await self._r.flushdb()
        except Exception as e:
            log.warning("redis.flush.failed", error=str(e))

    async def ping(self) -> bool:
        try:
            return await self._r.ping()
        except Exception:
            return False


# ─── Cache Factory ─────────────────────────────────────────────────────────────
_cache_instance: Optional[InMemoryCache | RedisCache] = None


async def get_cache() -> InMemoryCache | RedisCache:
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    try:
        import redis.asyncio as aioredis
        from config import settings
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        if await r.ping():
            log.info("cache.backend", backend="redis", url=settings.REDIS_URL)
            _cache_instance = RedisCache(r)
            return _cache_instance
    except Exception as e:
        log.warning("cache.redis.unavailable", error=str(e), fallback="in-memory")

    log.info("cache.backend", backend="in-memory")
    _cache_instance = InMemoryCache()
    return _cache_instance


def cache_key(*parts) -> str:
    return ":".join(str(p) for p in parts)
