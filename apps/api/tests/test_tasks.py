"""Task + time-tracking endpoint tests — CRUD and work sessions."""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.cache import InMemoryCache
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import OVERDUE_EXCLUDED_STATUSES, Task
from devflow_api.core.models.task_status_change import TaskStatusChange
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.task import TaskService, get_task_service
from devflow_api.core.unset import UNSET, Unset
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))

    def seed_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID, role: str = "member"
    ) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )


class FakeProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[uuid.UUID, Project] = {}

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)

    def seed_project(self, *, project_id: uuid.UUID, org_id: uuid.UUID) -> Project:
        now = datetime.now(UTC)
        project = Project(
            id=project_id,
            org_id=org_id,
            name="API",
            description=None,
            status="active",
            github_repo_url=None,
            created_by=uuid.uuid4(),
            created_at=now,
            updated_at=now,
        )
        self._projects[project_id] = project
        return project


class FakeTaskRepository:
    def __init__(self, project_repo: FakeProjectRepository) -> None:
        self._tasks: dict[uuid.UUID, Task] = {}
        self._project_repo = project_repo

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        title: str,
        description: str | None,
        priority: str,
        estimate_minutes: int | None,
        assignee_id: uuid.UUID | None,
        due_date: datetime | None,
        github_pr_url: str | None,
        created_by: uuid.UUID,
    ) -> Task:
        now = datetime.now(UTC)
        task = Task(
            id=uuid.uuid4(),
            project_id=project_id,
            title=title,
            description=description,
            status="backlog",
            priority=priority,
            estimate_minutes=estimate_minutes,
            assignee_id=assignee_id,
            due_date=due_date,
            github_pr_url=github_pr_url,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task.id] = task
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        return self._tasks.get(task_id)

    async def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
        limit: int,
        offset: int,
    ) -> list[Task]:
        items = [t for t in self._tasks.values() if t.project_id == project_id]
        if status is not None:
            items = [t for t in items if t.status == status]
        if assignee_id is not None:
            items = [t for t in items if t.assignee_id == assignee_id]
        return items[offset : offset + limit]

    async def count_for_project(
        self,
        project_id: uuid.UUID,
        *,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> int:
        items = [t for t in self._tasks.values() if t.project_id == project_id]
        if status is not None:
            items = [t for t in items if t.status == status]
        if assignee_id is not None:
            items = [t for t in items if t.assignee_id == assignee_id]
        return len(items)

    async def _overdue_for_user(
        self, *, user_id: uuid.UUID, org_id: uuid.UUID, now: datetime
    ) -> list[Task]:
        items = []
        for t in self._tasks.values():
            if t.assignee_id != user_id:
                continue
            if t.due_date is None or t.due_date >= now:
                continue
            if t.status in OVERDUE_EXCLUDED_STATUSES:
                continue
            project = await self._project_repo.get_by_id(t.project_id)
            if project is None or project.org_id != org_id:
                continue
            items.append(t)
        items.sort(key=lambda t: t.due_date)  # type: ignore[arg-type,return-value]
        return items

    async def list_overdue_for_user(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        now: datetime,
        limit: int,
        offset: int,
    ) -> list[Task]:
        items = await self._overdue_for_user(user_id=user_id, org_id=org_id, now=now)
        return items[offset : offset + limit]

    async def count_overdue_for_user(
        self, *, user_id: uuid.UUID, org_id: uuid.UUID, now: datetime
    ) -> int:
        items = await self._overdue_for_user(user_id=user_id, org_id=org_id, now=now)
        return len(items)

    async def update(
        self,
        task: Task,
        *,
        title: str | None = None,
        description: str | None | Unset = UNSET,
        status: str | None = None,
        priority: str | None = None,
        estimate_minutes: int | None | Unset = UNSET,
        assignee_id: uuid.UUID | None | Unset = UNSET,
        due_date: datetime | None | Unset = UNSET,
        github_pr_url: str | None | Unset = UNSET,
        completed_at: datetime | None | Unset = UNSET,
    ) -> Task:
        if title is not None:
            task.title = title
        if not isinstance(description, Unset):
            task.description = description
        if status is not None:
            task.status = status
        if not isinstance(completed_at, Unset):
            task.completed_at = completed_at
        if priority is not None:
            task.priority = priority
        if not isinstance(estimate_minutes, Unset):
            task.estimate_minutes = estimate_minutes
        if not isinstance(assignee_id, Unset):
            task.assignee_id = assignee_id
        if not isinstance(due_date, Unset):
            task.due_date = due_date
        if not isinstance(github_pr_url, Unset):
            task.github_pr_url = github_pr_url
        return task

    async def delete(self, task: Task) -> None:
        self._tasks.pop(task.id, None)


class FakeWorkSessionRepository:
    def __init__(self, task_repo: FakeTaskRepository) -> None:
        self._sessions: dict[uuid.UUID, WorkSession] = {}
        self._task_repo = task_repo

    async def create(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID, started_at: datetime
    ) -> WorkSession:
        session = WorkSession(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            started_at=started_at,
            ended_at=None,
            duration_seconds=None,
            created_at=datetime.now(UTC),
        )
        self._sessions[session.id] = session
        return session

    async def get_active_for_user(self, user_id: uuid.UUID) -> WorkSession | None:
        # Mirrors the real repo's `ORDER BY started_at DESC LIMIT 1`: even if
        # duplicate open sessions exist (pre-index data, a race), this must
        # return the most recent one rather than raising or picking arbitrarily.
        open_sessions = [
            s
            for s in self._sessions.values()
            if s.user_id == user_id and s.ended_at is None
        ]
        if not open_sessions:
            return None
        return max(open_sessions, key=lambda s: s.started_at)

    async def get_active_with_task(
        self, user_id: uuid.UUID
    ) -> tuple[WorkSession, str] | None:
        active = await self.get_active_for_user(user_id)
        if active is None:
            return None
        task = await self._task_repo.get_by_id(active.task_id)
        return active, task.title if task is not None else ""

    async def get_by_id(self, session_id: uuid.UUID) -> WorkSession | None:
        return self._sessions.get(session_id)

    async def list_for_task(self, task_id: uuid.UUID) -> list[WorkSession]:
        return [s for s in self._sessions.values() if s.task_id == task_id]

    async def tracked_seconds_for_tasks(
        self, task_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        totals: dict[uuid.UUID, int] = {}
        for session in self._sessions.values():
            if session.task_id not in task_ids or not session.duration_seconds:
                continue
            totals[session.task_id] = (
                totals.get(session.task_id, 0) + session.duration_seconds
            )
        return totals

    async def stop(
        self, session: WorkSession, *, ended_at: datetime, duration_seconds: int
    ) -> WorkSession:
        session.ended_at = ended_at
        session.duration_seconds = duration_seconds
        return session

    def seed_active(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID, started_at: datetime
    ) -> WorkSession:
        session = WorkSession(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            started_at=started_at,
            ended_at=None,
            duration_seconds=None,
            created_at=datetime.now(UTC),
        )
        self._sessions[session.id] = session
        return session

    def seed_completed(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        started_at: datetime,
        duration_seconds: int,
    ) -> WorkSession:
        session = WorkSession(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            started_at=started_at,
            ended_at=started_at + timedelta(seconds=duration_seconds),
            duration_seconds=duration_seconds,
            created_at=datetime.now(UTC),
        )
        self._sessions[session.id] = session
        return session


class FakeTaskStatusChangeRepository:
    def __init__(self) -> None:
        self.records: list[TaskStatusChange] = []

    async def record(
        self,
        *,
        task_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        changed_by: uuid.UUID | None,
        changed_at: datetime,
    ) -> TaskStatusChange:
        change = TaskStatusChange(
            id=uuid.uuid4(),
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            changed_at=changed_at,
        )
        self.records.append(change)
        return change


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
def org_repo(user_id: uuid.UUID, org_id: uuid.UUID) -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed_member(org_id, user_id, role="owner")
    return repo


@pytest.fixture()
def project_repo(org_id: uuid.UUID, project_id: uuid.UUID) -> FakeProjectRepository:
    repo = FakeProjectRepository()
    repo.seed_project(project_id=project_id, org_id=org_id)
    return repo


@pytest.fixture()
def task_repo(project_repo: FakeProjectRepository) -> FakeTaskRepository:
    return FakeTaskRepository(project_repo)


@pytest.fixture()
def session_repo(task_repo: FakeTaskRepository) -> FakeWorkSessionRepository:
    return FakeWorkSessionRepository(task_repo)


@pytest.fixture()
def status_change_repo() -> FakeTaskStatusChangeRepository:
    return FakeTaskStatusChangeRepository()


@pytest.fixture()
def service(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
) -> TaskService:
    return TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
        long_running_session_hours=6,
    )


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    service: TaskService,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_task_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


def _make_task(
    service: TaskService,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str = "Task",
) -> Task:
    return asyncio.run(
        service.create_task(project_id=project_id, user_id=user_id, title=title)
    )


# ---------------------------------------------------------------------------
# Tests — create
# ---------------------------------------------------------------------------


def test_create_task_returns_201(client: TestClient, project_id: uuid.UUID) -> None:
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": str(project_id), "title": "Write tests"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write tests"
    assert body["status"] == "backlog"
    assert body["priority"] == "medium"


def test_create_task_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": str(uuid.uuid4()), "title": "X"},
    )
    assert response.status_code == 404


def test_create_task_not_member_returns_403(
    client: TestClient,
    project_repo: FakeProjectRepository,
) -> None:
    # project in an org the current user is not a member of
    foreign_project = uuid.uuid4()
    project_repo.seed_project(project_id=foreign_project, org_id=uuid.uuid4())
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": str(foreign_project), "title": "X"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests — list
# ---------------------------------------------------------------------------


def test_list_tasks_returns_200(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    _make_task(service, project_id=project_id, user_id=user_id)
    response = client.get(f"/api/v1/tasks?project_id={project_id}")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_list_tasks_filtered_by_status(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    _make_task(service, project_id=project_id, user_id=user_id)
    # all seeded tasks are 'backlog'; filtering by 'done' yields none
    response = client.get(f"/api/v1/tasks?project_id={project_id}&status=done")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 0


def test_list_tasks_missing_project_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/tasks")
    assert response.status_code == 422


def test_list_tasks_returns_accumulated_tracked_seconds(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Multiple start/stop cycles on a task must sum, not overwrite, in the list."""
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_completed(
        task_id=task.id,
        user_id=user_id,
        started_at=datetime.now(UTC) - timedelta(hours=2),
        duration_seconds=600,
    )
    session_repo.seed_completed(
        task_id=task.id,
        user_id=user_id,
        started_at=datetime.now(UTC) - timedelta(hours=1),
        duration_seconds=300,
    )
    response = client.get(f"/api/v1/tasks?project_id={project_id}")
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["tracked_seconds"] == 900


# ---------------------------------------------------------------------------
# Tests — overdue
# ---------------------------------------------------------------------------


def _make_overdue(
    service: TaskService,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    assignee_id: uuid.UUID,
    due_date: datetime,
    title: str = "Overdue task",
) -> Task:
    return asyncio.run(
        service.create_task(
            project_id=project_id,
            user_id=user_id,
            title=title,
            assignee_id=assignee_id,
            due_date=due_date,
        )
    )


def test_list_overdue_tasks_returns_only_mine(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    org_repo: FakeOrganizationRepository,
) -> None:
    other_user = uuid.uuid4()
    org_repo.seed_member(org_id, other_user, role="member")
    now = datetime.now(UTC)
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="mine, overdue",
    )
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=other_user,
        due_date=now - timedelta(days=1),
        title="theirs, overdue",
    )
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now + timedelta(days=1),
        title="mine, future",
    )
    asyncio.run(
        service.create_task(
            project_id=project_id,
            user_id=user_id,
            title="mine, no due date",
            assignee_id=user_id,
        )
    )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "mine, overdue"


def test_list_overdue_tasks_excludes_done_and_cancelled(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    now = datetime.now(UTC)
    done_task = _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="done",
    )
    asyncio.run(
        service.update_task(task_id=done_task.id, user_id=user_id, status="done")
    )
    cancelled_task = _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="cancelled",
    )
    asyncio.run(
        service.update_task(
            task_id=cancelled_task.id, user_id=user_id, status="cancelled"
        )
    )
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="still open",
    )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_list_overdue_tasks_orders_most_overdue_first(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    now = datetime.now(UTC)
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="1 day late",
    )
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=3),
        title="3 days late",
    )
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=2),
        title="2 days late",
    )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")

    titles = [item["title"] for item in response.json()["data"]]
    assert titles == ["3 days late", "2 days late", "1 day late"]


def test_list_overdue_tasks_respects_limit(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    now = datetime.now(UTC)
    for i in range(7):
        _make_overdue(
            service,
            project_id=project_id,
            user_id=user_id,
            assignee_id=user_id,
            due_date=now - timedelta(days=i + 1),
            title=f"task {i}",
        )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}&limit=3")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 3
    assert body["meta"]["total"] == 7


def test_list_overdue_tasks_excludes_other_organizations(
    client: TestClient,
    service: TaskService,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    other_org_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    project_repo.seed_project(project_id=other_project_id, org_id=other_org_id)
    org_repo.seed_member(other_org_id, user_id, role="owner")
    now = datetime.now(UTC)
    _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="in my org",
    )
    _make_overdue(
        service,
        project_id=other_project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
        title="in other org",
    )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "in my org"


def test_list_overdue_tasks_non_member_org_returns_403(client: TestClient) -> None:
    response = client.get(f"/api/v1/tasks/overdue?organization_id={uuid.uuid4()}")
    assert response.status_code == 403


def test_list_overdue_tasks_route_not_shadowed_by_task_id(
    client: TestClient, org_id: uuid.UUID
) -> None:
    """Regression lock: `/overdue` must be declared above `/{task_id}` in
    routes.py, or FastAPI tries to parse "overdue" as a task UUID and this
    would 422 instead of reaching the handler."""
    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")
    assert response.status_code == 200


def test_list_overdue_tasks_missing_organization_id_returns_422(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/tasks/overdue")
    assert response.status_code == 422


def test_list_overdue_tasks_includes_tracked_seconds(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    now = datetime.now(UTC)
    task = _make_overdue(
        service,
        project_id=project_id,
        user_id=user_id,
        assignee_id=user_id,
        due_date=now - timedelta(days=1),
    )
    session_repo.seed_completed(
        task_id=task.id,
        user_id=user_id,
        started_at=now - timedelta(hours=2),
        duration_seconds=600,
    )

    response = client.get(f"/api/v1/tasks/overdue?organization_id={org_id}")

    assert response.status_code == 200
    assert response.json()["data"][0]["tracked_seconds"] == 600


# ---------------------------------------------------------------------------
# Tests — get / update / delete
# ---------------------------------------------------------------------------


def test_get_task_returns_200(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.get(f"/api/v1/tasks/{task.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(task.id)


def test_get_task_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_task_status_returns_200(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_created_task_has_null_completed_at(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.get(f"/api/v1/tasks/{task.id}")
    assert response.json()["completed_at"] is None


def test_update_task_to_done_sets_completed_at(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})
    assert response.status_code == 200
    assert response.json()["completed_at"] is not None


def test_update_task_out_of_done_clears_completed_at(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["completed_at"] is None


def test_update_task_repeated_done_keeps_original_completed_at(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    first = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})
    first_completed_at = first.json()["completed_at"]
    second = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})
    assert second.status_code == 200
    assert second.json()["completed_at"] == first_completed_at


def test_update_task_title_only_leaves_completed_at_unchanged(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    done = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})
    completed_at = done.json()["completed_at"]
    renamed = client.patch(f"/api/v1/tasks/{task.id}", json={"title": "Renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["completed_at"] == completed_at


def test_update_task_invalid_status_returns_422(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "nope"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests — status transition history
# ---------------------------------------------------------------------------


def test_create_task_records_initial_status_change(
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)

    assert len(status_change_repo.records) == 1
    change = status_change_repo.records[0]
    assert change.task_id == task.id
    assert change.from_status is None
    assert change.to_status == "backlog"
    assert change.changed_by == user_id
    assert change.changed_at == task.created_at


def test_update_task_records_status_transition(
    client: TestClient,
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    status_change_repo.records.clear()  # drop the creation-time row

    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "in_progress"})

    assert response.status_code == 200
    assert len(status_change_repo.records) == 1
    change = status_change_repo.records[0]
    assert change.task_id == task.id
    assert change.from_status == "backlog"
    assert change.to_status == "in_progress"
    assert change.changed_by == user_id


def test_update_task_without_status_field_records_nothing(
    client: TestClient,
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    status_change_repo.records.clear()

    response = client.patch(f"/api/v1/tasks/{task.id}", json={"title": "Renamed"})

    assert response.status_code == 200
    assert status_change_repo.records == []


def test_update_task_with_unchanged_status_records_nothing(
    client: TestClient,
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    status_change_repo.records.clear()

    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "backlog"})

    assert response.status_code == 200
    assert status_change_repo.records == []


def test_status_change_timestamp_matches_completed_at(
    client: TestClient,
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    status_change_repo.records.clear()

    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "done"})

    completed_at = response.json()["completed_at"]
    change = status_change_repo.records[-1]
    assert change.to_status == "done"
    assert change.changed_at.isoformat().replace("+00:00", "Z") == completed_at


def test_failed_update_records_no_status_change(
    client: TestClient,
    service: TaskService,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    status_change_repo.records.clear()
    other_user_id = uuid.uuid4()  # not a member of the project's organization

    response = client.patch(
        f"/api/v1/tasks/{task.id}",
        json={"status": "in_progress", "assignee_id": str(other_user_id)},
    )

    assert response.status_code == 422
    assert status_change_repo.records == []


def test_update_task_can_unassign(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """PATCH with assignee_id: null must clear the field, not leave it unchanged."""
    task = _make_task(service, project_id=project_id, user_id=user_id)
    assign_response = client.patch(
        f"/api/v1/tasks/{task.id}", json={"assignee_id": str(user_id)}
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assignee_id"] == str(user_id)

    unassign_response = client.patch(
        f"/api/v1/tasks/{task.id}", json={"assignee_id": None}
    )
    assert unassign_response.status_code == 200
    assert unassign_response.json()["assignee_id"] is None


def test_update_task_omitting_field_leaves_it_unchanged(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A PATCH that omits a field must not clear it (distinct from explicit null)."""
    task = asyncio.run(
        service.create_task(
            project_id=project_id,
            user_id=user_id,
            title="Task",
            estimate_minutes=45,
        )
    )
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"title": "Renamed"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["estimate_minutes"] == 45


def test_delete_task_returns_204(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.delete(f"/api/v1/tasks/{task.id}")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Tests — assignee membership validation (TM-001)
# ---------------------------------------------------------------------------


def test_create_task_with_org_member_assignee_returns_201(
    client: TestClient,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    org_repo: FakeOrganizationRepository,
) -> None:
    """Assigning to a user who IS an org member must succeed."""
    assignee_id = uuid.uuid4()
    org_repo.seed_member(org_id, assignee_id)
    response = client.post(
        "/api/v1/tasks",
        json={
            "project_id": str(project_id),
            "title": "Assigned task",
            "assignee_id": str(assignee_id),
        },
    )
    assert response.status_code == 201
    assert response.json()["assignee_id"] == str(assignee_id)


def test_create_task_with_non_member_assignee_returns_422(
    client: TestClient,
    project_id: uuid.UUID,
) -> None:
    """Assigning to a user who is NOT an org member must be rejected."""
    response = client.post(
        "/api/v1/tasks",
        json={
            "project_id": str(project_id),
            "title": "Bad assignee",
            "assignee_id": str(uuid.uuid4()),  # random UUID — not a member
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_assignee"


def test_update_task_with_non_member_assignee_returns_422(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Updating assignee to a non-org-member must be rejected."""
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.patch(
        f"/api/v1/tasks/{task.id}",
        json={"assignee_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_assignee"


# ---------------------------------------------------------------------------
# Tests — work sessions
# ---------------------------------------------------------------------------


def test_start_session_returns_201(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.post(f"/api/v1/tasks/{task.id}/start")
    assert response.status_code == 201
    body = response.json()
    assert body["task_id"] == str(task.id)
    assert body["ended_at"] is None


def test_start_session_when_active_returns_409(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_active(
        task_id=task.id, user_id=user_id, started_at=datetime.now(UTC)
    )
    response = client.post(f"/api/v1/tasks/{task.id}/start")
    assert response.status_code == 409


def test_start_session_when_active_reports_blocking_task_in_details(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """The 409 must name the task with the active session, so the UI can offer
    a "stop and switch" action instead of a bare, unexplained failure."""
    active_task = _make_task(
        service, project_id=project_id, user_id=user_id, title="Active task"
    )
    other_task = _make_task(
        service, project_id=project_id, user_id=user_id, title="Other task"
    )
    active_session = session_repo.seed_active(
        task_id=active_task.id, user_id=user_id, started_at=datetime.now(UTC)
    )
    response = client.post(f"/api/v1/tasks/{other_task.id}/start")
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["active_task_id"] == str(active_task.id)
    assert details["active_session_id"] == str(active_session.id)


def test_stop_session_computes_duration(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_active(
        task_id=task.id,
        user_id=user_id,
        started_at=datetime.now(UTC) - timedelta(minutes=90),
    )
    response = client.post(f"/api/v1/tasks/{task.id}/stop")
    assert response.status_code == 200
    body = response.json()
    assert body["ended_at"] is not None
    assert body["duration_seconds"] == 90 * 60


def test_stop_session_sub_minute_interval_is_not_lost(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A short start/stop cycle (<1 min) must still record real seconds, not 0."""
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_active(
        task_id=task.id,
        user_id=user_id,
        started_at=datetime.now(UTC) - timedelta(seconds=45),
    )
    response = client.post(f"/api/v1/tasks/{task.id}/stop")
    assert response.status_code == 200
    body = response.json()
    assert body["duration_seconds"] >= 45
    assert body["duration_seconds"] < 60


def test_stop_session_without_active_returns_404(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.post(f"/api/v1/tasks/{task.id}/stop")
    assert response.status_code == 404


def test_list_sessions_returns_200(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_active(
        task_id=task.id, user_id=user_id, started_at=datetime.now(UTC)
    )
    response = client.get(f"/api/v1/tasks/{task.id}/sessions")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Tests — active session lookup
# ---------------------------------------------------------------------------


def test_get_active_session_returns_null_when_none(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/sessions/active")
    assert response.status_code == 200
    assert response.json()["data"] is None


def test_get_active_session_returns_session_with_task_title(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(
        service, project_id=project_id, user_id=user_id, title="Fix the bug"
    )
    started_at = datetime.now(UTC) - timedelta(minutes=5)
    session_repo.seed_active(task_id=task.id, user_id=user_id, started_at=started_at)

    response = client.get("/api/v1/tasks/sessions/active")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["task_id"] == str(task.id)
    assert data["task_title"] == "Fix the bug"


# ---------------------------------------------------------------------------
# Tests — long-running session warning
# ---------------------------------------------------------------------------


def test_active_session_reports_elapsed_seconds(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    started_at = datetime.now(UTC) - timedelta(minutes=5)
    session_repo.seed_active(task_id=task.id, user_id=user_id, started_at=started_at)

    response = client.get("/api/v1/tasks/sessions/active")

    data = response.json()["data"]
    # Allow a little slack for wall-clock time elapsed during the test itself.
    assert 295 <= data["elapsed_seconds"] <= 320


def test_active_session_returns_threshold_seconds(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    session_repo.seed_active(
        task_id=task.id, user_id=user_id, started_at=datetime.now(UTC)
    )

    response = client.get("/api/v1/tasks/sessions/active")

    # The `service` fixture is built with long_running_session_hours=6.
    assert response.json()["data"]["long_running_threshold_seconds"] == 6 * 3600


def test_active_session_not_flagged_below_threshold(
    client: TestClient,
    service: TaskService,
    session_repo: FakeWorkSessionRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    started_at = datetime.now(UTC) - timedelta(hours=1)
    session_repo.seed_active(task_id=task.id, user_id=user_id, started_at=started_at)

    response = client.get("/api/v1/tasks/sessions/active")

    assert response.json()["data"]["is_long_running"] is False


def test_active_session_flags_long_running_past_threshold(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    svc = TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
        long_running_session_hours=1,
    )
    task = asyncio.run(
        svc.create_task(project_id=project_id, user_id=user_id, title="t")
    )
    started_at = datetime.now(UTC) - timedelta(hours=2)
    session_repo.seed_active(task_id=task.id, user_id=user_id, started_at=started_at)

    result = asyncio.run(svc.get_active_session(user_id=user_id))

    assert result is not None
    assert result.is_long_running is True
    assert result.long_running_threshold_seconds == 3600


def test_active_session_handles_naive_started_at(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A naive `started_at` (no tzinfo) must not raise when compared against
    an aware `datetime.now(UTC)` — regression guard for the `_as_utc` coercion
    that `get_active_session` shares with `stop_session`."""
    svc = TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
    )
    task = asyncio.run(
        svc.create_task(project_id=project_id, user_id=user_id, title="t")
    )
    naive_started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    session_repo.seed_active(
        task_id=task.id, user_id=user_id, started_at=naive_started_at
    )

    result = asyncio.run(svc.get_active_session(user_id=user_id))

    assert result is not None
    assert result.elapsed_seconds >= 0


def test_get_active_for_user_survives_duplicate_open_sessions() -> None:
    """A partial unique index now prevents two open sessions per user at the
    DB level, but the repo query must stay defensive: `scalar_one_or_none()`
    would raise `MultipleResultsFound` on stale/pre-index duplicate rows and
    permanently 500 the timer for that user. It must return one row instead."""
    task_repo = FakeTaskRepository(FakeProjectRepository())
    repo = FakeWorkSessionRepository(task_repo)
    user_id = uuid.uuid4()
    repo.seed_active(
        task_id=uuid.uuid4(),
        user_id=user_id,
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    newer = repo.seed_active(
        task_id=uuid.uuid4(), user_id=user_id, started_at=datetime.now(UTC)
    )

    active = asyncio.run(repo.get_active_for_user(user_id))

    assert active is not None
    assert active.id == newer.id


# ---------------------------------------------------------------------------
# Tests — metrics cache invalidation
# ---------------------------------------------------------------------------


def test_update_task_to_done_invalidates_assignee_metrics_cache(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    cache = InMemoryCache()
    svc = TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
        cache=cache,
    )
    task = asyncio.run(
        svc.create_task(
            project_id=project_id, user_id=user_id, title="t", assignee_id=user_id
        )
    )
    key = f"metrics:velocity:{user_id}:None:None"
    asyncio.run(cache.set(key, '{"cached": true}', ttl_seconds=60))

    asyncio.run(svc.update_task(task_id=task.id, user_id=user_id, status="done"))

    assert asyncio.run(cache.get(key)) is None


def test_update_task_to_non_done_status_does_not_invalidate_cache(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    cache = InMemoryCache()
    svc = TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
        cache=cache,
    )
    task = asyncio.run(
        svc.create_task(
            project_id=project_id, user_id=user_id, title="t", assignee_id=user_id
        )
    )
    key = f"metrics:velocity:{user_id}:None:None"
    asyncio.run(cache.set(key, '{"cached": true}', ttl_seconds=60))

    asyncio.run(svc.update_task(task_id=task.id, user_id=user_id, status="in_progress"))

    assert asyncio.run(cache.get(key)) == '{"cached": true}'


def test_stop_session_invalidates_user_metrics_cache(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    status_change_repo: FakeTaskStatusChangeRepository,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    cache = InMemoryCache()
    svc = TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        status_change_repo=status_change_repo,  # type: ignore[arg-type]
        cache=cache,
    )
    task = asyncio.run(
        svc.create_task(project_id=project_id, user_id=user_id, title="t")
    )
    session_repo.seed_active(
        task_id=task.id, user_id=user_id, started_at=datetime.now(UTC)
    )
    key = f"metrics:time_tracking:{user_id}:None:None"
    asyncio.run(cache.set(key, '{"cached": true}', ttl_seconds=60))

    asyncio.run(svc.stop_session(task_id=task.id, user_id=user_id))

    assert asyncio.run(cache.get(key)) is None
