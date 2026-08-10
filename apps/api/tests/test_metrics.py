"""Metrics endpoint tests — productivity aggregates over tasks/work sessions."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
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
def service(
    metrics_repo: FakeMetricsRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
) -> MetricsService:
    return MetricsService(
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
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
            "date_from": (NOW - timedelta(days=21)).isoformat(),
            "date_to": NOW.isoformat(),
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
