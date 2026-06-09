"""Project endpoint tests — CRUD within organizations."""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
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
def client(
    user_id: uuid.UUID,
    org_repo: FakeOrganizationRepository,
    project_repo: FakeProjectRepository,
) -> Iterator[TestClient]:
    app = create_app()

    def fake_service() -> ProjectService:
        return ProjectService(project_repo=project_repo, org_repo=org_repo)  # type: ignore[arg-type]

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
) -> Project:
    svc = ProjectService(project_repo=project_repo, org_repo=org_repo)  # type: ignore[arg-type]
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
    assert body["total"] == 1
    assert body["items"][0]["name"] == "API"


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
    assert response.json()["total"] == 1


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
