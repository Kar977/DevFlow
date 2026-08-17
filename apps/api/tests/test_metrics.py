"""Metrics endpoint tests — productivity aggregates over tasks/work sessions."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.models.task_status_change import TaskStatusChange
from devflow_api.core.models.user import User
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.metrics import MetricsService, get_metrics_service
from devflow_api.main import create_app

NOW = datetime.now(UTC)


def _task(
    *,
    status: str = "done",
    project_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    estimate_minutes: int | None = None,
    due_date: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Task:
    moment = NOW - timedelta(days=1)
    return Task(
        id=uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
        title="T",
        description=None,
        status=status,
        priority="medium",
        estimate_minutes=estimate_minutes,
        assignee_id=assignee_id,
        due_date=due_date,
        github_pr_url=None,
        created_by=uuid.uuid4(),
        created_at=created_at or moment,
        updated_at=updated_at or moment,
        completed_at=completed_at,
    )


def _session(
    *,
    task_id: uuid.UUID | None = None,
    user_id: uuid.UUID,
    started_at: datetime,
    duration_minutes: int | None,
) -> WorkSession:
    duration_seconds = duration_minutes * 60 if duration_minutes is not None else None
    return WorkSession(
        id=uuid.uuid4(),
        task_id=task_id or uuid.uuid4(),
        user_id=user_id,
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=duration_minutes or 0),
        duration_seconds=duration_seconds,
        created_at=started_at,
    )


def _status_change(
    *,
    task_id: uuid.UUID,
    from_status: str | None,
    to_status: str,
    changed_by: uuid.UUID | None,
    changed_at: datetime,
) -> TaskStatusChange:
    return TaskStatusChange(
        id=uuid.uuid4(),
        task_id=task_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        changed_at=changed_at,
    )


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeMetricsRepository:
    def __init__(self) -> None:
        self.user_tasks: list[Task] = []
        self.user_sessions: list[WorkSession] = []
        self.project_tasks: dict[uuid.UUID, list[Task]] = {}

    async def get_tasks_for_user(self, user_id: uuid.UUID) -> list[Task]:
        return self.user_tasks

    async def get_work_sessions_for_user(self, user_id: uuid.UUID) -> list[WorkSession]:
        return self.user_sessions

    async def get_tasks_for_project(self, project_id: uuid.UUID) -> list[Task]:
        return self.project_tasks.get(project_id, [])


class FakeProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[uuid.UUID, Project] = {}

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)

    def seed_project(self, *, project_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self._projects[project_id] = Project(
            id=project_id,
            org_id=org_id,
            name="API",
            description=None,
            status="active",
            github_repo_url=None,
            created_by=uuid.uuid4(),
            created_at=NOW,
            updated_at=NOW,
        )


class FakeUserRepository:
    def __init__(self, *, timezone: str | None = None) -> None:
        self._timezone = timezone

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        return User(
            id=user_id,
            email="user@example.com",
            hashed_password="x",
            timezone=self._timezone,
            created_at=NOW,
            updated_at=NOW,
        )


class FakeTaskStatusChangeRepository:
    def __init__(self) -> None:
        self.rows: list[TaskStatusChange] = []

    async def list_for_tasks(self, task_ids: list[uuid.UUID]) -> list[TaskStatusChange]:
        wanted = set(task_ids)
        return [r for r in self.rows if r.task_id in wanted]


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role="owner",
            joined_at=NOW,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def metrics_repo() -> FakeMetricsRepository:
    return FakeMetricsRepository()


@pytest.fixture()
def project_repo(org_id: uuid.UUID, project_id: uuid.UUID) -> FakeProjectRepository:
    repo = FakeProjectRepository()
    repo.seed_project(project_id=project_id, org_id=org_id)
    return repo


@pytest.fixture()
def org_repo(org_id: uuid.UUID, user_id: uuid.UUID) -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed_member(org_id, user_id)
    return repo


@pytest.fixture()
def user_repo() -> FakeUserRepository:
    """Default: no timezone set — every existing test keeps UTC bucketing."""
    return FakeUserRepository(timezone=None)


@pytest.fixture()
def status_change_repo() -> FakeTaskStatusChangeRepository:
    return FakeTaskStatusChangeRepository()


@pytest.fixture()
def service(
    metrics_repo: FakeMetricsRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
) -> MetricsService:
    return MetricsService(
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        user_repo=user_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
    )


@pytest.fixture()
def client(user_id: uuid.UUID, service: MetricsService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_summary_counts_completed_and_hours(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = [_task(status="done"), _task(status="done")]
    metrics_repo.user_sessions = [
        _session(
            user_id=user_id, started_at=NOW - timedelta(days=1), duration_minutes=120
        )
    ]
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["tasks_completed"]["value"] == 2
    assert body["active_hours"]["value"] == 2.0


def test_summary_uses_completed_at_not_updated_at(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    """A done task edited long after completion must not re-enter the window
    just because updated_at moved — that is exactly the bug completed_at
    fixes."""
    metrics_repo.user_tasks = [
        _task(
            status="done",
            completed_at=NOW - timedelta(days=45),  # outside the 30d window
            updated_at=NOW,  # edited today, e.g. reassigned
        )
    ]
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    assert response.json()["tasks_completed"]["value"] == 0


def test_metrics_fall_back_to_updated_at_when_completed_at_null(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    """Legacy rows written before the completed_at column existed must keep
    behaving exactly as before: updated_at is the completion instant."""
    metrics_repo.user_tasks = [
        _task(status="done", completed_at=None, updated_at=NOW - timedelta(days=1))
    ]
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    assert response.json()["tasks_completed"]["value"] == 1


def test_velocity_returns_total_and_average(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    metrics_repo.user_tasks = [_task(status="done") for _ in range(3)]
    response = client.get("/api/v1/metrics/velocity")
    assert response.status_code == 200
    body = response.json()
    assert body["total_done"] == 3
    assert body["weeks"] >= 1


def test_velocity_weekly_sums_to_total_done(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    metrics_repo.user_tasks = [
        _task(status="done", updated_at=NOW - timedelta(days=1)),
        _task(status="done", updated_at=NOW - timedelta(days=8)),
        _task(status="done", updated_at=NOW - timedelta(days=8)),
    ]
    response = client.get("/api/v1/metrics/velocity")
    assert response.status_code == 200
    body = response.json()
    weekly_total = sum(point["tasks_completed"] for point in body["weekly"])
    assert weekly_total == body["total_done"]


def test_velocity_weekly_is_zero_filled_for_empty_weeks(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    metrics_repo.user_tasks = []
    response = client.get(
        "/api/v1/metrics/velocity",
        params={
            "date_from": (NOW - timedelta(days=21)).date().isoformat(),
            "date_to": NOW.date().isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["weekly"]) >= 3
    assert all(point["tasks_completed"] == 0 for point in body["weekly"])
    week_starts = [point["week_start"] for point in body["weekly"]]
    assert week_starts == sorted(week_starts)


def test_velocity_weekly_buckets_by_iso_week(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    # Two tasks completed in the same ISO week must land in the same bucket.
    # Anchored to *last* week's Monday (not this week's) so both points stay
    # safely in the past regardless of which weekday the suite runs on.
    monday_last_week = NOW - timedelta(days=NOW.weekday() + 7)
    metrics_repo.user_tasks = [
        _task(status="done", updated_at=monday_last_week),
        _task(status="done", updated_at=monday_last_week + timedelta(days=2)),
    ]
    response = client.get("/api/v1/metrics/velocity")
    assert response.status_code == 200
    body = response.json()
    expected_week = monday_last_week.date().isoformat()
    bucket = next(p for p in body["weekly"] if p["week_start"] == expected_week)
    assert bucket["tasks_completed"] == 2


def test_velocity_weekly_buckets_by_completed_at(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    """Bucketing must key off completed_at, not updated_at, once the task
    has been edited after completion."""
    monday_last_week = NOW - timedelta(days=NOW.weekday() + 7)
    monday_two_weeks_ago = monday_last_week - timedelta(days=7)
    metrics_repo.user_tasks = [
        _task(
            status="done",
            completed_at=monday_two_weeks_ago,
            updated_at=monday_last_week,  # would land in the wrong bucket
        ),
    ]
    response = client.get("/api/v1/metrics/velocity")
    assert response.status_code == 200
    body = response.json()
    expected_week = monday_two_weeks_ago.date().isoformat()
    bucket = next(p for p in body["weekly"] if p["week_start"] == expected_week)
    assert bucket["tasks_completed"] == 1
    other_week = monday_last_week.date().isoformat()
    other_bucket = next(p for p in body["weekly"] if p["week_start"] == other_week)
    assert other_bucket["tasks_completed"] == 0


def test_time_tracking_buckets_daily_hours(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_sessions = [
        _session(
            user_id=user_id, started_at=NOW - timedelta(days=2), duration_minutes=60
        ),
        _session(
            user_id=user_id, started_at=NOW - timedelta(days=1), duration_minutes=30
        ),
    ]
    response = client.get("/api/v1/metrics/time-tracking")
    assert response.status_code == 200
    body = response.json()
    assert body["total_hours"] == 1.5
    assert len(body["daily"]) == 2


def test_completion_rate(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    created = NOW - timedelta(days=2)
    metrics_repo.user_tasks = [
        _task(status="done", created_at=created),
        _task(status="done", created_at=created),
        _task(status="cancelled", created_at=created),
        _task(status="in_progress", created_at=created),
    ]
    response = client.get("/api/v1/metrics/completion-rate")
    assert response.status_code == 200
    body = response.json()
    assert body["done"] == 2
    assert body["cancelled"] == 1
    assert body["open"] == 1
    assert body["completion_rate"] == 50.0


def test_estimation_accuracy_classifies_ratios(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_id: uuid.UUID,
) -> None:
    accurate_task = _task(status="done", estimate_minutes=100)
    under_task = _task(status="done", estimate_minutes=100)
    metrics_repo.user_tasks = [accurate_task, under_task]
    metrics_repo.user_sessions = [
        _session(
            task_id=accurate_task.id,
            user_id=user_id,
            started_at=NOW - timedelta(days=1),
            duration_minutes=90,
        ),
        _session(
            task_id=under_task.id,
            user_id=user_id,
            started_at=NOW - timedelta(days=1),
            duration_minutes=150,
        ),
    ]
    response = client.get("/api/v1/metrics/estimation-accuracy")
    assert response.status_code == 200
    body = response.json()
    assert body["sample_size"] == 2
    assert body["accurate_count"] == 1
    assert body["under_estimated_count"] == 1


def test_streaks_counts_consecutive_days(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    today = NOW
    metrics_repo.user_tasks = [
        _task(status="done", updated_at=today),
        _task(status="done", updated_at=today - timedelta(days=1)),
        _task(status="done", updated_at=today - timedelta(days=2)),
    ]
    response = client.get("/api/v1/metrics/streaks")
    assert response.status_code == 200
    body = response.json()
    assert body["current_streak"] == 3
    assert body["longest_streak"] == 3


def test_streaks_use_completed_at(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    """A done task's streak day must follow completed_at, not a later
    updated_at from an unrelated edit."""
    today = NOW
    metrics_repo.user_tasks = [
        _task(status="done", completed_at=today, updated_at=today),
        _task(
            status="done",
            completed_at=today - timedelta(days=1),
            updated_at=today,  # edited today, but completed yesterday
        ),
    ]
    response = client.get("/api/v1/metrics/streaks")
    assert response.status_code == 200
    body = response.json()
    assert body["current_streak"] == 2
    assert body["longest_streak"] == 2


def test_project_metrics_health(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    project_id: uuid.UUID,
) -> None:
    metrics_repo.project_tasks[project_id] = [
        _task(status="in_progress", due_date=NOW - timedelta(days=1)),  # overdue
        _task(status="done"),
        _task(status="todo"),
    ]
    response = client.get(f"/api/v1/metrics/projects/{project_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total_tasks"] == 3
    assert body["overdue_tasks"] == 1
    assert body["open_tasks"] == 2
    assert body["health"] in ("healthy", "at_risk", "critical")


def test_project_metrics_exclude_cancelled_from_overdue(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    project_id: uuid.UUID,
) -> None:
    metrics_repo.project_tasks[project_id] = [
        _task(status="cancelled", due_date=NOW - timedelta(days=1)),
        _task(status="in_progress", due_date=NOW - timedelta(days=1)),
    ]
    response = client.get(f"/api/v1/metrics/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["overdue_tasks"] == 1


def test_project_metrics_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/metrics/projects/{uuid.uuid4()}")
    assert response.status_code == 404


def test_project_metrics_not_member_returns_403(
    client: TestClient,
    project_repo: FakeProjectRepository,
) -> None:
    foreign_project = uuid.uuid4()
    project_repo.seed_project(project_id=foreign_project, org_id=uuid.uuid4())
    response = client.get(f"/api/v1/metrics/projects/{foreign_project}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Regression: a `date_to` of today must include work done today.
#
# Before this fix, `date_to="<today>"` resolved to midnight at the START of
# today (a naive datetime coerced to UTC), so a session started minutes ago
# fell *after* the window and silently vanished from every panel.
# ---------------------------------------------------------------------------


def test_time_tracking_date_to_today_includes_a_session_started_just_now(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_sessions = [
        _session(
            user_id=user_id, started_at=NOW - timedelta(minutes=5), duration_minutes=40
        )
    ]
    response = client.get(
        "/api/v1/metrics/time-tracking",
        params={"date_to": NOW.date().isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["total_hours"] > 0


def test_summary_date_to_today_includes_a_task_completed_just_now(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    metrics_repo.user_tasks = [_task(status="done", completed_at=NOW)]
    response = client.get(
        "/api/v1/metrics/summary",
        params={"date_to": NOW.date().isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["tasks_completed"]["value"] == 1


# ---------------------------------------------------------------------------
# Half-open window: a task/session landing exactly on `start` must count
# once, in the current period only — not double-counted into "previous".
# ---------------------------------------------------------------------------


def test_summary_task_completed_exactly_at_window_start_counts_once(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
) -> None:
    date_from = (NOW - timedelta(days=10)).date()
    date_to = NOW.date()
    # Window start is local midnight of date_from; land a completion exactly
    # there so it's a boundary case for the half-open comparison.
    boundary = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
    metrics_repo.user_tasks = [_task(status="done", completed_at=boundary)]
    response = client.get(
        "/api/v1/metrics/summary",
        params={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tasks_completed"]["value"] == 1
    assert body["tasks_completed"]["prev_value"] == 0


# ---------------------------------------------------------------------------
# Timezone-aware bucketing
# ---------------------------------------------------------------------------


def test_time_tracking_buckets_by_local_date_not_utc_date(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_repo: FakeUserRepository,
    user_id: uuid.UUID,
) -> None:
    """A Warsaw user's late-evening session (23:30 UTC = 01:30 CEST) must be
    bucketed on the local day it happened, not the UTC day."""
    user_repo._timezone = "Europe/Warsaw"
    started_at = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)
    metrics_repo.user_sessions = [
        _session(user_id=user_id, started_at=started_at, duration_minutes=30)
    ]
    response = client.get(
        "/api/v1/metrics/time-tracking",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
    )
    assert response.status_code == 200
    daily = response.json()["daily"]
    assert len(daily) == 1
    assert daily[0]["day"] == "2026-08-17"


def test_metrics_unset_timezone_behaves_like_utc(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_repo: FakeUserRepository,
    user_id: uuid.UUID,
) -> None:
    """Deploy-safety regression: a user who never set a timezone (the
    default for every pre-existing row) must bucket identically to UTC."""
    user_repo._timezone = None
    started_at = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)
    metrics_repo.user_sessions = [
        _session(user_id=user_id, started_at=started_at, duration_minutes=30)
    ]
    response = client.get(
        "/api/v1/metrics/time-tracking",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
    )
    assert response.status_code == 200
    daily = response.json()["daily"]
    assert daily[0]["day"] == "2026-08-16"


def test_metrics_garbage_stored_timezone_falls_back_to_utc(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    user_repo: FakeUserRepository,
    user_id: uuid.UUID,
) -> None:
    """A corrupt/garbage stored timezone must degrade to UTC, never 500."""
    user_repo._timezone = "Not/AZone"
    metrics_repo.user_sessions = [
        _session(
            user_id=user_id, started_at=NOW - timedelta(hours=1), duration_minutes=15
        )
    ]
    response = client.get("/api/v1/metrics/time-tracking")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Cycle time (per-status dwell time + currently-stuck tasks)
# ---------------------------------------------------------------------------


def test_cycle_time_computes_average_hours_per_stage(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
) -> None:
    task = _task(status="in_progress")
    metrics_repo.project_tasks[project_id] = [task]

    actor = uuid.uuid4()
    t0 = NOW - timedelta(hours=10)
    status_change_repo.rows = [
        _status_change(
            task_id=task.id,
            from_status=None,
            to_status="backlog",
            changed_by=actor,
            changed_at=t0,
        ),
        _status_change(
            task_id=task.id,
            from_status="backlog",
            to_status="todo",
            changed_by=actor,
            changed_at=t0 + timedelta(hours=2),
        ),
        _status_change(
            task_id=task.id,
            from_status="todo",
            to_status="in_progress",
            changed_by=actor,
            changed_at=t0 + timedelta(hours=7),
        ),
    ]

    response = client.get(f"/api/v1/metrics/projects/{project_id}/cycle-time")
    assert response.status_code == 200
    stages = {s["status"]: s for s in response.json()["stages"]}
    assert stages["backlog"] == {
        "status": "backlog",
        "average_hours": 2.0,
        "sample_size": 1,
    }
    assert stages["todo"] == {"status": "todo", "average_hours": 5.0, "sample_size": 1}
    # No completed transition out of in_progress yet — it's still open.
    assert "in_progress" not in stages


def test_cycle_time_excludes_backfilled_transition_from_average(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
) -> None:
    """A task whose only history is the 0017 migration backfill (a synthetic
    "backlog" creation row and a synthetic "-> done" row with
    changed_by=None) must not have its whole pre-migration lifetime
    misattributed as time spent in "backlog"."""
    task = _task(status="done")
    metrics_repo.project_tasks[project_id] = [task]
    creator = uuid.uuid4()
    t0 = NOW - timedelta(days=100)
    status_change_repo.rows = [
        _status_change(
            task_id=task.id,
            from_status=None,
            to_status="backlog",
            changed_by=creator,
            changed_at=t0,
        ),
        _status_change(
            task_id=task.id,
            from_status=None,
            to_status="done",
            changed_by=None,  # the migration backfill's fingerprint
            changed_at=t0 + timedelta(hours=100),
        ),
    ]

    response = client.get(f"/api/v1/metrics/projects/{project_id}/cycle-time")
    assert response.status_code == 200
    body = response.json()
    assert body["stages"] == []
    assert body["stuck"] == []  # "done" is terminal — never stuck


def test_cycle_time_stuck_lists_non_terminal_tasks_longest_first(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
) -> None:
    task_a = _task(status="in_progress")
    task_b = _task(status="review")
    task_c = _task(status="done")
    metrics_repo.project_tasks[project_id] = [task_a, task_b, task_c]
    actor = uuid.uuid4()
    status_change_repo.rows = [
        _status_change(
            task_id=task_a.id,
            from_status="todo",
            to_status="in_progress",
            changed_by=actor,
            changed_at=NOW - timedelta(hours=10),
        ),
        _status_change(
            task_id=task_b.id,
            from_status="in_progress",
            to_status="review",
            changed_by=actor,
            changed_at=NOW - timedelta(hours=30),
        ),
        _status_change(
            task_id=task_c.id,
            from_status="review",
            to_status="done",
            changed_by=actor,
            changed_at=NOW - timedelta(hours=5),
        ),
    ]

    response = client.get(f"/api/v1/metrics/projects/{project_id}/cycle-time")
    assert response.status_code == 200
    stuck = response.json()["stuck"]
    assert [s["task_id"] for s in stuck] == [str(task_b.id), str(task_a.id)]
    assert stuck[0]["status"] == "review"
    assert stuck[0]["hours_in_status"] == 30.0


def test_cycle_time_stuck_capped_at_five(
    client: TestClient,
    metrics_repo: FakeMetricsRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
) -> None:
    tasks = [_task(status="in_progress") for _ in range(7)]
    metrics_repo.project_tasks[project_id] = tasks
    actor = uuid.uuid4()
    status_change_repo.rows = [
        _status_change(
            task_id=t.id,
            from_status="todo",
            to_status="in_progress",
            changed_by=actor,
            changed_at=NOW - timedelta(hours=i + 1),
        )
        for i, t in enumerate(tasks)
    ]

    response = client.get(f"/api/v1/metrics/projects/{project_id}/cycle-time")
    assert response.status_code == 200
    stuck = response.json()["stuck"]
    assert len(stuck) == 5
    hours = [s["hours_in_status"] for s in stuck]
    assert hours == sorted(hours, reverse=True)


def test_cycle_time_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/metrics/projects/{uuid.uuid4()}/cycle-time")
    assert response.status_code == 404


def test_cycle_time_not_member_returns_403(
    client: TestClient,
    project_repo: FakeProjectRepository,
) -> None:
    foreign_project = uuid.uuid4()
    project_repo.seed_project(project_id=foreign_project, org_id=uuid.uuid4())
    response = client.get(f"/api/v1/metrics/projects/{foreign_project}/cycle-time")
    assert response.status_code == 403
