"""Generic cache-aside helper shared by metrics-style services.

Extracted from ``MetricsService._cached`` so ``PRMetricsService`` (and any
future service) can reuse the same cache-aside behavior without depending on
a `MetricsService` instance. ``MetricsService._cached`` now delegates here.
"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from devflow_api.core.cache import CacheBackend


async def cached[T: BaseModel](
    cache: CacheBackend | None,
    key: str,
    model_cls: type[T],
    ttl_seconds: int,
    compute: Callable[[], Awaitable[T]],
) -> T:
    """Return a cached result, or compute, store, and return a fresh one.

    Falls back to computing without caching when ``cache is None`` or when
    any cache operation raises an exception.
    """
    if cache is None:
        return await compute()

    raw = await cache.get(key)
    if raw is not None:
        return model_cls.model_validate_json(raw)

    result = await compute()
    await cache.set(key, result.model_dump_json(), ttl_seconds)
    return result
