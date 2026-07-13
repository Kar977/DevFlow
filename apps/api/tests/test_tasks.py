"""Task + time-tracking endpoint tests — CRUD and work sessions."""

import asyncio
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
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, Task] = {}

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
    ) -> Task:
        if title is not None:
            task.title = title
        if not isinstance(description, Unset):
            task.description = description
        if status is not None:
            task.status = status
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
    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, WorkSession] = {}

    async def create(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID, started_at: datetime
    ) -> WorkSession:
        session = WorkSession(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            started_at=started_at,
            ended_at=None,
            duration_minutes=None,
            created_at=datetime.now(UTC),
        )
        self._sessions[session.id] = session
        return session

    async def get_active_for_user(self, user_id: uuid.UUID) -> WorkSession | None:
        return next(
            (
                s
                for s in self._sessions.values()
                if s.user_id == user_id and s.ended_at is None
            ),
            None,
        )

    async def get_by_id(self, session_id: uuid.UUID) -> WorkSession | None:
        return self._sessions.get(session_id)

    async def list_for_task(self, task_id: uuid.UUID) -> list[WorkSession]:
        return [s for s in self._sessions.values() if s.task_id == task_id]

    async def stop(
        self, session: WorkSession, *, ended_at: datetime, duration_minutes: int
    ) -> WorkSession:
        session.ended_at = ended_at
        session.duration_minutes = duration_minutes
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
            duration_minutes=None,
            created_at=datetime.now(UTC),
        )
        self._sessions[session.id] = session
        return session


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
def task_repo() -> FakeTaskRepository:
    return FakeTaskRepository()


@pytest.fixture()
def session_repo() -> FakeWorkSessionRepository:
    return FakeWorkSessionRepository()


@pytest.fixture()
def service(
    task_repo: FakeTaskRepository,
    session_repo: FakeWorkSessionRepository,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
) -> TaskService:
    return TaskService(
        task_repo=task_repo,  # type: ignore[arg-type]
        work_session_repo=session_repo,  # type: ignore[arg-type]
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
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
    assert response.json()["total"] == 1


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
    assert response.json()["total"] == 0


def test_list_tasks_missing_project_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/tasks")
    assert response.status_code == 422


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


def test_update_task_invalid_status_returns_422(
    client: TestClient,
    service: TaskService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    task = _make_task(service, project_id=project_id, user_id=user_id)
    response = client.patch(f"/api/v1/tasks/{task.id}", json={"status": "nope"})
    assert response.status_code == 422


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
    assert body["duration_minutes"] == 90


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
    assert response.json()["total"] == 1
