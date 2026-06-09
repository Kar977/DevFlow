"""Cache backends for the metrics layer.

Architecture
------------
``CacheBackend`` is a ``Protocol`` so that:
- Tests inject ``InMemoryCache`` — no real Redis required.
- Production wires ``RedisCache`` via ``get_cache()`` FastAPI dependency.
- ``run_report_generation`` keeps using ``MetricsService(cache=None)`` with no
  changes (background tasks don't need cached responses).

``RedisCache`` wraps every network call in a try/except so a Redis outage
**never** surfaces as an HTTP 500 — the endpoint silently falls back to
computing the result without cache.

Singleton pattern
-----------------
``_get_redis_backend()`` is decorated with ``@lru_cache`` so a single
``redis.asyncio.Redis`` client is reused across requests, matching the
``engine`` / ``async_session_factory`` singleton in ``core/database.py``.
``_shared_memory_cache`` is a module-level instance used when ``redis_url``
is not configured (dev / test environments).
"""

import time
from functools import lru_cache
from typing import Protocol, runtime_checkable

import redis.asyncio as aioredis

from devflow_api.core.config import get_settings

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CacheBackend(Protocol):
    """Minimal async key-value cache interface."""

    async def get(self, key: str) -> str | None:
        """Return the cached value, or ``None`` on miss / expiry / error."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store *value* under *key* for at most *ttl_seconds* seconds."""
        ...


# ---------------------------------------------------------------------------
# InMemoryCache — dev / test / fallback when redis_url is empty
# ---------------------------------------------------------------------------


class InMemoryCache:
    """Thread-safe¹ in-process TTL cache backed by a plain dict.

    ¹ Python's GIL makes dict reads/writes atomic at the bytecode level, which
    is sufficient for the single-threaded async event loop.  Do not use this
    across multiple *processes* (e.g. ``uvicorn --workers N``) — use Redis.
    """

    def __init__(self) -> None:
        # key → (expires_at_monotonic, serialised_value)
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        """Remove all entries.  Useful in tests to force cache misses."""
        self._store.clear()


# ---------------------------------------------------------------------------
# RedisCache — production backend
# ---------------------------------------------------------------------------


class RedisCache:
    """Cache backend backed by a ``redis.asyncio.Redis`` client.

    All network errors are caught and swallowed so the application degrades
    gracefully when Redis is unavailable.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            # redis-py returns str when decode_responses=True, else bytes.
            return raw if isinstance(raw, str) else raw.decode()
        except Exception:  # noqa: BLE001
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return  # Redis rejects non-positive TTLs; just skip caching.
        try:
            await self._client.set(key, value, ex=ttl_seconds)
        except Exception:  # noqa: BLE001
            pass  # Fallback: don't cache on error


# ---------------------------------------------------------------------------
# Dependency / singleton factory
# ---------------------------------------------------------------------------


@lru_cache
def _get_redis_backend() -> RedisCache:
    """Create a single ``RedisCache`` instance for the process lifetime."""
    client: aioredis.Redis = aioredis.Redis.from_url(
        get_settings().redis_url, decode_responses=True
    )
    return RedisCache(client)


# Shared InMemoryCache instance used when redis_url is not configured.
_shared_memory_cache: InMemoryCache = InMemoryCache()


def get_cache() -> CacheBackend:
    """FastAPI dependency — return the active cache backend.

    Returns ``RedisCache`` when ``DEVFLOW_API_REDIS_URL`` is set, otherwise
    falls back to the process-wide ``InMemoryCache`` (suitable for a single
    worker).
    """
    if get_settings().redis_url:
        return _get_redis_backend()
    return _shared_memory_cache
