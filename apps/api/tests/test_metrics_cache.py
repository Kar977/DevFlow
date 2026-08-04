"""Tests for the Redis/in-memory cache layer and MetricsService cache integration.

Tests are organised in three groups:
1. InMemoryCache unit tests  (direct async, no HTTP)
2. RedisCache fallback tests (broken Redis client stub, no real Redis needed)
3. MetricsService + cache integration tests (counting-fake repos, no HTTP)
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from devflow_api.core.cache import CacheBackend, InMemoryCache, RedisCache
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.services.metrics import MetricsService

NOW = datetime.now(UTC)

# ---------------------------------------------------------------------------
# InMemoryCache — unit tests
# ---------------------------------------------------------------------------


async def test_in_memory_cache_miss_returns_none() -> None:
    cache = InMemoryCache()
    assert await cache.get("nonexistent") is None


async def test_in_memory_cache_set_and_get() -> None:
    cache = InMemoryCache()
    await cache.set("key", "value", ttl_seconds=60)
    assert await cache.get("key") == "value"


async def test_in_memory_cache_different_keys_are_independent() -> None:
    cache = InMemoryCache()
    await cache.set("a", "1", ttl_seconds=60)
    await cache.set("b", "2", ttl_seconds=60)
    assert await cache.get("a") == "1"
    assert await cache.get("b") == "2"


async def test_in_memory_cache_expired_entry_returns_none() -> None:
    """TTL=0 means the entry expires at the exact moment it is set."""
    cache = InMemoryCache()
    await cache.set("key", "value", ttl_seconds=0)
    # expires_at = time.time() + 0 = time.time(); time.time() >= expires_at is True
    assert await cache.get("key") is None


async def test_in_memory_cache_clear_removes_all_entries() -> None:
    cache = InMemoryCache()
    await cache.set("a", "1", ttl_seconds=60)
    await cache.set("b", "2", ttl_seconds=60)
    cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None


async def test_in_memory_cache_delete_matching_removes_matched_keys() -> None:
    cache = InMemoryCache()
    await cache.set("metrics:summary:u1:x", "a", ttl_seconds=60)
    await cache.set("metrics:velocity:u1:y", "b", ttl_seconds=60)
    await cache.set("metrics:summary:u2:z", "c", ttl_seconds=60)

    await cache.delete_matching("u1")

    assert await cache.get("metrics:summary:u1:x") is None
    assert await cache.get("metrics:velocity:u1:y") is None
    assert await cache.get("metrics:summary:u2:z") == "c"


async def test_in_memory_cache_delete_matching_no_match_is_noop() -> None:
    cache = InMemoryCache()
    await cache.set("metrics:summary:u1:x", "a", ttl_seconds=60)

    await cache.delete_matching("nonexistent")

    assert await cache.get("metrics:summary:u1:x") == "a"


async def test_in_memory_cache_satisfies_protocol() -> None:
    """InMemoryCache is structurally compatible with CacheBackend Protocol."""
    cache: CacheBackend = InMemoryCache()
    await cache.set("k", "v", ttl_seconds=5)
    assert await cache.get("k") == "v"


# ---------------------------------------------------------------------------
# RedisCache — fallback tests (no real Redis, uses a broken-client stub)
# ---------------------------------------------------------------------------


class _BrokenRedis:
    """Stub that always raises ConnectionError — simulates Redis being down."""

    async def get(self, key: str) -> None:
        raise ConnectionError("Redis unavailable")

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,  # noqa: A002
    ) -> None:
        raise ConnectionError("Redis unavailable")


async def test_redis_cache_get_returns_none_on_connection_error() -> None:
    cache = RedisCache(_BrokenRedis())  # type: ignore[arg-type]
    result = await cache.get("some-key")
    assert result is None


async def test_redis_cache_set_is_noop_on_connection_error() -> None:
    cache = RedisCache(_BrokenRedis())  # type: ignore[arg-type]
    # Must not raise even when Redis is down
    await cache.set("some-key", "value", ttl_seconds=60)


class _BrokenRedisScan:
    """Stub whose scan_iter raises — simulates Redis being down mid-SCAN."""

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        raise ConnectionError("Redis unavailable")
        yield  # pragma: no cover — makes this an async generator function


async def test_redis_cache_delete_matching_is_noop_on_connection_error() -> None:
    cache = RedisCache(_BrokenRedisScan())  # type: ignore[arg-type]
    # Must not raise even when Redis is down
    await cache.delete_matching("whatever")


class _FakeRedisScan:
    """Stub with in-memory SCAN + DEL semantics, for testing delete_matching."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self.deleted: list[str] = []

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        needle = match.strip("*")
        for key in self._keys:
            if needle in key:
                yield key

    async def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)


async def test_redis_cache_delete_matching_deletes_matched_keys() -> None:
    client = _FakeRedisScan(
        ["metrics:summary:u1:x", "metrics:velocity:u1:y", "metrics:summary:u2:z"]
    )
    cache = RedisCache(client)  # type: ignore[arg-type]

    await cache.delete_matching("u1")

    assert set(client.deleted) == {"metrics:summary:u1:x", "metrics:velocity:u1:y"}


async def test_redis_cache_delete_matching_no_match_deletes_nothing() -> None:
    client = _FakeRedisScan(["metrics:summary:u1:x"])
    cache = RedisCache(client)  # type: ignore[arg-type]

    await cache.delete_matching("nonexistent")

    assert client.deleted == []


# ---------------------------------------------------------------------------
# Fake repos for MetricsService integration tests
# ---------------------------------------------------------------------------


class _CountingMetricsRepo:
    """Fake MetricsRepository that counts how many times each method is called."""

    def __init__(self) -> None:
        self.user_tasks: list[Task] = []
        self.user_sessions: list[WorkSession] = []
        self.project_tasks: dict[uuid.UUID, list[Task]] = {}
        self.get_tasks_calls = 0
        self.get_sessions_calls = 0

    async def get_tasks_for_user(self, user_id: uuid.UUID) -> list[Task]:
        self.get_tasks_calls += 1
        return self.user_tasks

    async def get_work_sessions_for_user(self, user_id: uuid.UUID) -> list[WorkSession]:
        self.get_sessions_calls += 1
        return self.user_sessions

    async def get_tasks_for_project(self, project_id: uuid.UUID) -> list[Task]:
        return self.project_tasks.get(project_id, [])


class _FakeProjectRepo:
    def __init__(self, org_id: uuid.UUID, project_id: uuid.UUID) -> None:
        self._projects: dict[uuid.UUID, Project] = {
            project_id: Project(
                id=project_id,
                org_id=org_id,
                name="Test Project",
                description=None,
                status="active",
                github_repo_url=None,
                created_by=uuid.uuid4(),
                created_at=NOW,
                updated_at=NOW,
            )
        }

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)


class _FakeOrgRepo:
    def __init__(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {
            (org_id, user_id): OrganizationMember(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                role="owner",
                joined_at=NOW,
            )
        }

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def uid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def counting_repo() -> _CountingMetricsRepo:
    return _CountingMetricsRepo()


def _make_service(
    repo: _CountingMetricsRepo,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    cache: InMemoryCache | None = None,
    ttl_seconds: int = 60,
) -> MetricsService:
    return MetricsService(
        metrics_repo=repo,  # type: ignore[arg-type]
        project_repo=_FakeProjectRepo(org_id, project_id),  # type: ignore[arg-type]
        org_repo=_FakeOrgRepo(org_id, user_id),  # type: ignore[arg-type]
        cache=cache,
        ttl_seconds=ttl_seconds,
    )


# ---------------------------------------------------------------------------
# MetricsService + cache — integration tests
# ---------------------------------------------------------------------------


async def test_cache_hit_avoids_second_repo_call(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Calling get_summary twice with the same args hits the repo only once."""
    cache = InMemoryCache()
    service = _make_service(counting_repo, uid, org_id, project_id, cache=cache)

    result1 = await service.get_summary(user_id=uid)
    result2 = await service.get_summary(user_id=uid)

    assert result1 == result2
    assert counting_repo.get_tasks_calls == 1


async def test_different_user_ids_produce_separate_cache_entries(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Different user_ids are different cache keys — both hit the repo."""
    cache = InMemoryCache()
    service = _make_service(counting_repo, uid, org_id, project_id, cache=cache)

    other_user = uuid.uuid4()
    await service.get_summary(user_id=uid)
    await service.get_summary(user_id=other_user)

    assert counting_repo.get_tasks_calls == 2


async def test_cleared_cache_triggers_recompute(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """After cache.clear(), the next call recomputes (hits the repo again)."""
    cache = InMemoryCache()
    service = _make_service(counting_repo, uid, org_id, project_id, cache=cache)

    await service.get_summary(user_id=uid)
    assert counting_repo.get_tasks_calls == 1

    cache.clear()

    await service.get_summary(user_id=uid)
    assert counting_repo.get_tasks_calls == 2


async def test_expired_ttl_triggers_recompute(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """TTL=0 means entries expire immediately; every call hits the repo."""
    cache = InMemoryCache()
    service = _make_service(
        counting_repo, uid, org_id, project_id, cache=cache, ttl_seconds=0
    )

    await service.get_summary(user_id=uid)
    await service.get_summary(user_id=uid)

    assert counting_repo.get_tasks_calls == 2


async def test_no_cache_always_calls_repo(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """MetricsService(cache=None) computes on every call (existing behaviour)."""
    service = _make_service(counting_repo, uid, org_id, project_id, cache=None)

    await service.get_summary(user_id=uid)
    await service.get_summary(user_id=uid)

    assert counting_repo.get_tasks_calls == 2


async def test_velocity_cache_hit(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """get_velocity is also cached — repo called only once for same args."""
    cache = InMemoryCache()
    service = _make_service(counting_repo, uid, org_id, project_id, cache=cache)

    await service.get_velocity(user_id=uid)
    await service.get_velocity(user_id=uid)

    assert counting_repo.get_tasks_calls == 1


async def test_streaks_cache_hit(
    counting_repo: _CountingMetricsRepo,
    uid: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """get_streaks is cached (no date params — key is user_id only)."""
    cache = InMemoryCache()
    service = _make_service(counting_repo, uid, org_id, project_id, cache=cache)

    await service.get_streaks(user_id=uid)
    await service.get_streaks(user_id=uid)

    assert counting_repo.get_tasks_calls == 1
