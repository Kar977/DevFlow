"""Report endpoint tests — async report generation and lifecycle."""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.report import Report
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.metrics import MetricsService
from devflow_api.core.services.pr_metrics import PRMetricsService
from devflow_api.core.services.report import (
    ReportService,
    _generate_payload,
    get_report_generator,
    get_report_service,
)
from devflow_api.core.services.report_export import _pdf_text, render_csv, render_pdf
from devflow_api.main import create_app

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeReportRepository:
    def __init__(self) -> None:
        self._reports: dict[uuid.UUID, Report] = {}

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        report_type: str,
        fmt: str,
        organization_id: uuid.UUID | None = None,
    ) -> Report:
        report = Report(
            id=uuid.uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            type=report_type,
            format=fmt,
            status="pending",
            payload=None,
            error_message=None,
            generated_at=None,
            created_at=NOW,
        )
        self._reports[report.id] = report
        return report

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return self._reports.get(report_id)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Report]:
        items = [r for r in self._reports.values() if r.user_id == user_id]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset : offset + limit]

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        return sum(1 for r in self._reports.values() if r.user_id == user_id)

    async def update_status(
        self,
        report: Report,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
        generated_at: datetime | None = None,
    ) -> Report:
        report.status = status
        if payload is not None:
            report.payload = payload
        if error_message is not None:
            report.error_message = error_message
        if generated_at is not None:
            report.generated_at = generated_at
        return report

    async def delete(self, report: Report) -> None:
        self._reports.pop(report.id, None)


# ---------------------------------------------------------------------------
# Fake generator (marks report ready synchronously in the fake repo)
# ---------------------------------------------------------------------------


def make_fake_generator(report_repo: FakeReportRepository) -> Any:
    async def _fake_generator(
        report_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        report_type: str,
        date_from: datetime | None,
        date_to: datetime | None,
        project_id: uuid.UUID | None,
    ) -> None:
        report = await report_repo.get_by_id(report_id)
        if report is not None:
            await report_repo.update_status(
                report,
                status="ready",
                payload={"generated": True},
                generated_at=datetime.now(UTC),
            )

    return _fake_generator


# ---------------------------------------------------------------------------
# Fake project / org repos (for project_status auth tests)
# ---------------------------------------------------------------------------


class FakeProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[uuid.UUID, Project] = {}

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)

    def seed(self, *, project_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self._projects[project_id] = Project(
            id=project_id,
            org_id=org_id,
            name="P",
            description=None,
            status="active",
            github_repo_url=None,
            created_by=uuid.uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


class FakeOrgRepository:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))

    def seed(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role="member",
            joined_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Fake PR repo (for pr_flow_weekly payload tests)
# ---------------------------------------------------------------------------


def _pr(
    *,
    title: str = "PR",
    state: str = "open",
    created_offset_days: int = 0,
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
) -> PullRequest:
    now = datetime.now(UTC)
    created = now - timedelta(days=created_offset_days)
    return PullRequest(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        github_pr_id=uuid.uuid4().int % 100000,
        number=1,
        title=title,
        author_login="dev",
        state=state,
        created_at_github=created,
        merged_at=merged_at,
        closed_at=None,
        first_review_at=first_review_at,
        html_url="https://github.com/owner/repo/pull/1",
        last_synced_at=now,
        created_at=now,
        updated_at=now,
    )


class FakePRRepositoryForReport:
    def __init__(self, prs: list[PullRequest]) -> None:
        self._prs = prs

    async def list_for_org(self, org_id: uuid.UUID, **_: object) -> list[PullRequest]:
        return self._prs


# ---------------------------------------------------------------------------
# Fake repositories for MetricsService (used in _generate_payload tests)
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


class FakeUserRepositoryForReport:
    """No timezone stored — MetricsService._user_tz falls back to UTC."""

    async def get_by_id(self, user_id: uuid.UUID) -> None:
        return None


class FakeStatusChangeRepositoryForReport:
    """Never called by these report types — none of them touch cycle time."""

    async def list_for_tasks(self, task_ids: list[uuid.UUID]) -> list[object]:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def report_repo() -> FakeReportRepository:
    return FakeReportRepository()


@pytest.fixture()
def service(report_repo: FakeReportRepository) -> ReportService:
    return ReportService(report_repo=report_repo)  # type: ignore[arg-type]


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    service: ReportService,
    report_repo: FakeReportRepository,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        yield c


def _make_report(
    service: ReportService,
    *,
    user_id: uuid.UUID,
    report_type: str = "weekly_summary",
) -> Report:
    return asyncio.run(
        service.create_report(
            user_id=user_id,
            report_type=report_type,
            fmt="json",
            project_id=None,
        )
    )


# ---------------------------------------------------------------------------
# Tests — create (POST /api/v1/reports)
# ---------------------------------------------------------------------------


def test_create_report_returns_202(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reports",
        json={"type": "weekly_summary"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["type"] == "weekly_summary"
    assert body["format"] == "json"
    # fake generator runs synchronously in TestClient (BackgroundTasks execute inline)
    assert body["status"] in ("pending", "ready")


def test_create_report_invalid_type_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reports",
        json={"type": "nonsense"},
    )
    assert response.status_code == 422


def test_create_project_status_without_project_id_returns_422(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/reports",
        json={"type": "project_status"},
    )
    assert response.status_code == 422


def test_create_project_status_with_project_id_returns_202(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/reports",
        json={"type": "project_status", "project_id": str(uuid.uuid4())},
    )
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# Tests — list (GET /api/v1/reports)
# ---------------------------------------------------------------------------


def test_list_reports_returns_200(
    client: TestClient,
    service: ReportService,
    user_id: uuid.UUID,
) -> None:
    _make_report(service, user_id=user_id)
    _make_report(service, user_id=user_id)
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert len(body["data"]) == 2


def test_list_reports_empty(client: TestClient) -> None:
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 0
    assert body["data"] == []


def test_list_reports_pagination(
    client: TestClient,
    service: ReportService,
    user_id: uuid.UUID,
) -> None:
    for _ in range(5):
        _make_report(service, user_id=user_id)
    response = client.get("/api/v1/reports?limit=2&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 5
    assert len(body["data"]) == 2


# ---------------------------------------------------------------------------
# Tests — get (GET /api/v1/reports/{id})
# ---------------------------------------------------------------------------


def test_get_report_returns_200(
    client: TestClient,
    service: ReportService,
    user_id: uuid.UUID,
) -> None:
    report = _make_report(service, user_id=user_id)
    response = client.get(f"/api/v1/reports/{report.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(report.id)


def test_get_report_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/reports/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_report_other_user_returns_403(
    client: TestClient,
    service: ReportService,
    other_user_id: uuid.UUID,
) -> None:
    # create a report owned by another user
    report = _make_report(service, user_id=other_user_id)
    response = client.get(f"/api/v1/reports/{report.id}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests — delete (DELETE /api/v1/reports/{id})
# ---------------------------------------------------------------------------


def test_delete_report_returns_204(
    client: TestClient,
    service: ReportService,
    user_id: uuid.UUID,
) -> None:
    report = _make_report(service, user_id=user_id)
    response = client.delete(f"/api/v1/reports/{report.id}")
    assert response.status_code == 204


def test_delete_report_nonexistent_returns_404(client: TestClient) -> None:
    response = client.delete(f"/api/v1/reports/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_report_other_user_returns_403(
    client: TestClient,
    service: ReportService,
    other_user_id: uuid.UUID,
) -> None:
    report = _make_report(service, user_id=other_user_id)
    response = client.delete(f"/api/v1/reports/{report.id}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests — export (GET /api/v1/reports/{id}/export)
# ---------------------------------------------------------------------------


async def _make_ready_report(
    report_repo: FakeReportRepository,
    *,
    user_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> Report:
    report = await report_repo.create(
        user_id=user_id, report_type="weekly_summary", fmt="json"
    )
    default_payload = {
        "tasks_completed": 3,
        "estimation_accuracy": {"sample_size": 2},
    }
    return await report_repo.update_status(
        report,
        status="ready",
        payload=payload or default_payload,
        generated_at=datetime.now(UTC),
    )


def test_export_report_csv_returns_csv_content(
    client: TestClient,
    report_repo: FakeReportRepository,
    user_id: uuid.UUID,
) -> None:
    report = asyncio.run(_make_ready_report(report_repo, user_id=user_id))
    response = client.get(f"/api/v1/reports/{report.id}/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "tasks_completed" in body
    assert "estimation_accuracy.sample_size" in body


def test_export_report_pdf_returns_pdf_bytes(
    client: TestClient,
    report_repo: FakeReportRepository,
    user_id: uuid.UUID,
) -> None:
    report = asyncio.run(_make_ready_report(report_repo, user_id=user_id))
    response = client.get(f"/api/v1/reports/{report.id}/export?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_export_report_not_ready_returns_409(
    client: TestClient,
    service: ReportService,
    user_id: uuid.UUID,
) -> None:
    report = _make_report(service, user_id=user_id)  # still "pending"
    response = client.get(f"/api/v1/reports/{report.id}/export?format=csv")
    assert response.status_code == 409


def test_export_report_invalid_format_returns_422(
    client: TestClient,
    report_repo: FakeReportRepository,
    user_id: uuid.UUID,
) -> None:
    report = asyncio.run(_make_ready_report(report_repo, user_id=user_id))
    response = client.get(f"/api/v1/reports/{report.id}/export?format=xml")
    assert response.status_code == 422


def test_export_report_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/reports/{uuid.uuid4()}/export?format=csv")
    assert response.status_code == 404


def test_export_report_other_user_returns_403(
    client: TestClient,
    report_repo: FakeReportRepository,
    other_user_id: uuid.UUID,
) -> None:
    report = asyncio.run(_make_ready_report(report_repo, user_id=other_user_id))
    response = client.get(f"/api/v1/reports/{report.id}/export?format=csv")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Unit test — _generate_payload (weekly_summary)
# ---------------------------------------------------------------------------


def test_generate_payload_weekly_summary_shape() -> None:
    """_generate_payload returns the expected keys for weekly_summary."""
    metrics_repo = FakeMetricsRepository()
    end = NOW
    start = end - timedelta(days=7)

    # seed a completed task and a work session
    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="T",
        description=None,
        status="done",
        priority="medium",
        estimate_minutes=None,
        assignee_id=uuid.uuid4(),
        due_date=None,
        github_pr_url=None,
        created_by=uuid.uuid4(),
        created_at=start,
        updated_at=end - timedelta(days=1),
    )
    session_obj = WorkSession(
        id=uuid.uuid4(),
        task_id=task.id,
        user_id=task.assignee_id,
        started_at=end - timedelta(days=1),
        ended_at=end - timedelta(days=1) + timedelta(hours=2),
        duration_seconds=120 * 60,
        created_at=end - timedelta(days=1),
    )
    metrics_repo.user_tasks = [task]
    metrics_repo.user_sessions = [session_obj]

    metrics_svc = MetricsService(
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        project_repo=ProjectRepository.__new__(ProjectRepository),
        org_repo=OrganizationRepository.__new__(OrganizationRepository),
        user_repo=FakeUserRepositoryForReport(),  # type: ignore[arg-type]
        status_change_repo=FakeStatusChangeRepositoryForReport(),  # type: ignore[arg-type]
    )

    payload = asyncio.run(
        _generate_payload(
            "weekly_summary",
            user_id=task.assignee_id,  # type: ignore[arg-type]
            date_from=start,
            date_to=end,
            project_id=None,
            metrics=metrics_svc,
        )
    )

    assert "period" in payload
    assert "tasks_completed" in payload
    assert "total_work_hours" in payload
    assert "velocity" in payload
    assert "completion_rate" in payload
    assert "work_days" in payload
    assert "avg_hours_per_day" in payload
    assert payload["tasks_completed"] == 1
    assert payload["total_work_hours"] == 2.0


# ---------------------------------------------------------------------------
# Tests — project_status synchronous authorisation (TM-007)
# ---------------------------------------------------------------------------


def _make_report_service_with_auth(
    report_repo: FakeReportRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrgRepository,
) -> ReportService:
    return ReportService(
        report_repo=report_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
    )


def test_create_project_status_nonexistent_project_returns_404(
    user_id: uuid.UUID,
    report_repo: FakeReportRepository,
) -> None:
    """project_status report for an unknown project_id must return 404 immediately."""
    project_repo = FakeProjectRepository()  # empty — no projects seeded
    org_repo = FakeOrgRepository()
    service = _make_report_service_with_auth(report_repo, project_repo, org_repo)

    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/reports",
            json={"type": "project_status", "project_id": str(uuid.uuid4())},
        )
    assert response.status_code == 404


def test_create_project_status_non_member_returns_403(
    user_id: uuid.UUID,
    report_repo: FakeReportRepository,
) -> None:
    """project_status report for a project the user is NOT a member of returns 403."""
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_repo = FakeProjectRepository()
    project_repo.seed(project_id=project_id, org_id=org_id)
    org_repo = FakeOrgRepository()
    # user_id is NOT seeded into org_repo → no membership

    service = _make_report_service_with_auth(report_repo, project_repo, org_repo)

    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/reports",
            json={"type": "project_status", "project_id": str(project_id)},
        )
    assert response.status_code == 403


def test_create_project_status_as_member_returns_202(
    user_id: uuid.UUID,
    report_repo: FakeReportRepository,
) -> None:
    """project_status report for an accessible project returns 202."""
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_repo = FakeProjectRepository()
    project_repo.seed(project_id=project_id, org_id=org_id)
    org_repo = FakeOrgRepository()
    org_repo.seed(org_id, user_id)  # user IS a member

    service = _make_report_service_with_auth(report_repo, project_repo, org_repo)

    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/reports",
            json={"type": "project_status", "project_id": str(project_id)},
        )
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# Tests — pr_flow_weekly synchronous authorisation (audit gap #9)
# ---------------------------------------------------------------------------


def test_create_pr_flow_weekly_without_organization_id_returns_422(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/reports", json={"type": "pr_flow_weekly"})
    assert response.status_code == 422


def test_create_pr_flow_weekly_non_member_returns_403(
    user_id: uuid.UUID,
    report_repo: FakeReportRepository,
) -> None:
    org_id = uuid.uuid4()
    project_repo = FakeProjectRepository()
    org_repo = FakeOrgRepository()  # user_id NOT seeded → no membership
    service = _make_report_service_with_auth(report_repo, project_repo, org_repo)

    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/reports",
            json={"type": "pr_flow_weekly", "organization_id": str(org_id)},
        )
    assert response.status_code == 403


def test_create_pr_flow_weekly_as_member_returns_202(
    user_id: uuid.UUID,
    report_repo: FakeReportRepository,
) -> None:
    org_id = uuid.uuid4()
    project_repo = FakeProjectRepository()
    org_repo = FakeOrgRepository()
    org_repo.seed(org_id, user_id)
    service = _make_report_service_with_auth(report_repo, project_repo, org_repo)

    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    app.dependency_overrides[get_report_generator] = lambda: make_fake_generator(
        report_repo
    )
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/reports",
            json={"type": "pr_flow_weekly", "organization_id": str(org_id)},
        )
    assert response.status_code == 202
    assert response.json()["organization_id"] == str(org_id)


# ---------------------------------------------------------------------------
# Unit test — _generate_payload (pr_flow_weekly)
# ---------------------------------------------------------------------------


def test_generate_payload_pr_flow_weekly_shape() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    org_repo = FakeOrgRepository()
    org_repo.seed(org_id, user_id)
    pr_metrics_svc = PRMetricsService(
        pr_repo=FakePRRepositoryForReport([_pr(state="open", created_offset_days=10)]),  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        conn_repo=None,  # type: ignore[arg-type]
        user_repo=None,  # type: ignore[arg-type]
    )
    metrics_svc = MetricsService(
        metrics_repo=FakeMetricsRepository(),  # type: ignore[arg-type]
        project_repo=ProjectRepository.__new__(ProjectRepository),
        org_repo=OrganizationRepository.__new__(OrganizationRepository),
        # pr_flow_weekly never touches user-scoped productivity metrics, so
        # user_repo.get_by_id / status_change_repo.list_for_tasks are never
        # actually called here.
        user_repo=None,  # type: ignore[arg-type]
        status_change_repo=None,  # type: ignore[arg-type]
    )

    payload = asyncio.run(
        _generate_payload(
            "pr_flow_weekly",
            user_id=user_id,
            date_from=None,
            date_to=None,
            project_id=None,
            organization_id=org_id,
            metrics=metrics_svc,
            pr_metrics=pr_metrics_svc,
        )
    )

    assert payload["stale_pr_count"] == 1
    assert isinstance(payload["bottlenecks"]["stale_open"], list)
    assert payload["bottlenecks"]["stale_open"][0]["number"] == 1


def test_generate_payload_pr_flow_weekly_without_pr_metrics_raises() -> None:
    metrics_svc = MetricsService(
        metrics_repo=FakeMetricsRepository(),  # type: ignore[arg-type]
        project_repo=ProjectRepository.__new__(ProjectRepository),
        org_repo=OrganizationRepository.__new__(OrganizationRepository),
        # pr_flow_weekly never touches user-scoped productivity metrics, so
        # user_repo.get_by_id / status_change_repo.list_for_tasks are never
        # actually called here.
        user_repo=None,  # type: ignore[arg-type]
        status_change_repo=None,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="pr_flow_weekly"):
        asyncio.run(
            _generate_payload(
                "pr_flow_weekly",
                user_id=uuid.uuid4(),
                date_from=None,
                date_to=None,
                project_id=None,
                organization_id=uuid.uuid4(),
                metrics=metrics_svc,
                pr_metrics=None,
            )
        )


# ---------------------------------------------------------------------------
# Export — list-of-dicts payloads and PDF non-latin1 handling
# ---------------------------------------------------------------------------


def _report_with_payload(payload: dict[str, Any]) -> Report:
    return Report(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        type="pr_flow_weekly",
        format="json",
        status="ready",
        payload=payload,
        error_message=None,
        generated_at=datetime.now(UTC),
        created_at=NOW,
    )


def test_export_csv_renders_list_of_dicts_as_indexed_rows() -> None:
    report = _report_with_payload(
        {
            "bottlenecks": {
                "stale_open": [
                    {"number": 42, "title": "Fix things"},
                ]
            }
        }
    )
    csv_text = render_csv(report)
    assert "bottlenecks.stale_open[0].number" in csv_text
    assert "42" in csv_text
    assert "bottlenecks.stale_open[0].title" in csv_text


def test_export_csv_still_joins_scalar_lists() -> None:
    report = _report_with_payload({"tags": ["a", "b", "c"]})
    csv_text = render_csv(report)
    assert "a, b, c" in csv_text


def test_export_pdf_handles_non_latin1_characters() -> None:
    report = _report_with_payload(
        {"bottlenecks": {"stale_open": [{"title": "Poprawka ąćę — 🚀"}]}}
    )
    pdf_bytes = render_pdf(report)
    assert pdf_bytes.startswith(b"%PDF")


def test_export_pdf_truncates_overlong_values() -> None:
    long_value = "x" * 200
    result = _pdf_text(long_value)
    assert len(result) == 90
    assert result.endswith("...")
