"""Project endpoint tests — CRUD within organizations."""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.project import ProjectService, get_project_service
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

    def member_org_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        return {oid for (oid, uid) in self._members if uid == user_id}


class FakeProjectRepository:
    def __init__(self, org_repo: FakeOrganizationRepository) -> None:
        self._org_repo = org_repo
        self._projects: dict[uuid.UUID, Project] = {}

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by: uuid.UUID,
        github_repo_url: str | None,
    ) -> Project:
        now = datetime.now(UTC)
        project = Project(
            id=uuid.uuid4(),
            org_id=org_id,
            name=name,
            description=description,
            status="active",
            github_repo_url=github_repo_url,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._projects[project.id] = project
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)

    async def list_for_org(
        self, org_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[Project]:
        items = [p for p in self._projects.values() if p.org_id == org_id]
        return items[offset : offset + limit]

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[Project]:
        org_ids = self._org_repo.member_org_ids(user_id)
        items = [p for p in self._projects.values() if p.org_id in org_ids]
        return items[offset : offset + limit]

    async def count_for_org(self, org_id: uuid.UUID) -> int:
        return len([p for p in self._projects.values() if p.org_id == org_id])

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        org_ids = self._org_repo.member_org_ids(user_id)
        return len([p for p in self._projects.values() if p.org_id in org_ids])

    async def update(
        self,
        project: Project,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        github_repo_url: str | None = None,
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        if github_repo_url is not None:
            project.github_repo_url = github_repo_url
        return project

    async def archive(self, project: Project) -> None:
        project.status = "archived"


class FakeTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, Task] = {}

    def seed(self, task: Task) -> None:
        self._tasks[task.id] = task

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

    async def count_overdue_for_project(
        self, project_id: uuid.UUID, *, now: datetime
    ) -> int:
        return len(
            [
                t
                for t in self._tasks.values()
                if t.project_id == project_id
                and t.due_date is not None
                and t.due_date < now
                and t.status != "done"
            ]
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
def org_repo(user_id: uuid.UUID, org_id: uuid.UUID) -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed_member(org_id, user_id, role="owner")
    return repo


@pytest.fixture()
def project_repo(org_repo: FakeOrganizationRepository) -> FakeProjectRepository:
    return FakeProjectRepository(org_repo)


@pytest.fixture()
def task_repo() -> FakeTaskRepository:
    return FakeTaskRepository()


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    org_repo: FakeOrganizationRepository,
    project_repo: FakeProjectRepository,
    task_repo: FakeTaskRepository,
) -> Iterator[TestClient]:
    app = create_app()

    def fake_service() -> ProjectService:
        return ProjectService(
            project_repo=project_repo,  # type: ignore[arg-type]
            org_repo=org_repo,  # type: ignore[arg-type]
            task_repo=task_repo,  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_project_service] = fake_service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


async def _create_project(
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str = "API",
    task_repo: FakeTaskRepository | None = None,
) -> Project:
    svc = ProjectService(
        project_repo=project_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        task_repo=task_repo or FakeTaskRepository(),  # type: ignore[arg-type]
    )
    return await svc.create_project(org_id=org_id, user_id=user_id, name=name)


# ---------------------------------------------------------------------------
# Tests — create
# ---------------------------------------------------------------------------


def test_create_project_returns_201(client: TestClient, org_id: uuid.UUID) -> None:
    response = client.post(
        "/api/v1/projects", json={"org_id": str(org_id), "name": "API"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "API"
    assert body["status"] == "active"
    assert body["org_id"] == str(org_id)


def test_create_project_not_org_member_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"org_id": str(uuid.uuid4()), "name": "API"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests — list
# ---------------------------------------------------------------------------


def test_list_projects_returns_200(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    asyncio.run(_create_project(project_repo, org_repo, org_id=org_id, user_id=user_id))
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"total": 1, "limit": 50, "offset": 0}
    assert body["data"][0]["name"] == "API"


def test_list_projects_filtered_by_org_returns_200(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    asyncio.run(_create_project(project_repo, org_repo, org_id=org_id, user_id=user_id))
    response = client.get(f"/api/v1/projects?org_id={org_id}")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


# ---------------------------------------------------------------------------
# Tests — get
# ---------------------------------------------------------------------------


def test_get_project_returns_200(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    project = asyncio.run(
        _create_project(project_repo, org_repo, org_id=org_id, user_id=user_id)
    )
    response = client.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(project.id)


def test_get_project_returns_stats(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    task_repo: FakeTaskRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    project = asyncio.run(
        _create_project(
            project_repo, org_repo, org_id=org_id, user_id=user_id, task_repo=task_repo
        )
    )
    now = datetime.now(UTC)

    def make_task(status: str, due_date: datetime | None = None) -> Task:
        return Task(
            id=uuid.uuid4(),
            project_id=project.id,
            title="t",
            status=status,
            priority="medium",
            due_date=due_date,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )

    overdue_date = now - timedelta(days=1)
    task_repo.seed(make_task("done"))
    task_repo.seed(make_task("todo"))
    task_repo.seed(make_task("cancelled"))
    task_repo.seed(make_task("in_progress", due_date=overdue_date))  # overdue
    task_repo.seed(make_task("done", due_date=overdue_date))  # not overdue: done

    response = client.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats == {
        "total_tasks": 5,
        "open_tasks": 2,
        "overdue_tasks": 1,
        "completion_rate": 40.0,
    }


def test_get_project_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_project_not_member_returns_403(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
) -> None:
    # project belongs to an org the current user is NOT a member of
    other_org = uuid.uuid4()
    other_user = uuid.uuid4()
    org_repo.seed_member(other_org, other_user, role="owner")
    project = asyncio.run(
        _create_project(project_repo, org_repo, org_id=other_org, user_id=other_user)
    )
    response = client.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------


def test_update_project_returns_200(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    project = asyncio.run(
        _create_project(project_repo, org_repo, org_id=org_id, user_id=user_id)
    )
    response = client.patch(f"/api/v1/projects/{project.id}", json={"name": "API v2"})
    assert response.status_code == 200
    assert response.json()["name"] == "API v2"


# ---------------------------------------------------------------------------
# Tests — delete (archive)
# ---------------------------------------------------------------------------


def test_delete_project_archives_and_returns_204(
    client: TestClient,
    project_repo: FakeProjectRepository,
    org_repo: FakeOrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    project = asyncio.run(
        _create_project(project_repo, org_repo, org_id=org_id, user_id=user_id)
    )
    response = client.delete(f"/api/v1/projects/{project.id}")
    assert response.status_code == 204
    assert project_repo._projects[project.id].status == "archived"
