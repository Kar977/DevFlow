"""Organization endpoint tests — CRUD and membership management."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.errors import AppError
from devflow_api.core.models.organization import Organization
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.user import User
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.organization import (
    OrganizationService,
    get_organization_service,
)
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self._orgs: dict[uuid.UUID, Organization] = {}
        self._members: dict[uuid.UUID, OrganizationMember] = {}

    async def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        created_by: uuid.UUID,
    ) -> Organization:
        now = datetime.now(UTC)
        org = Organization(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            description=description,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._orgs[org.id] = org
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        org = self._orgs.get(org_id)
        if org is None or org.deleted_at is not None:
            return None
        return org

    async def get_by_slug(self, slug: str) -> Organization | None:
        return next(
            (o for o in self._orgs.values() if o.slug == slug and o.deleted_at is None),
            None,
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        member_org_ids = {
            m.org_id for m in self._members.values() if m.user_id == user_id
        }
        return [
            o
            for o in self._orgs.values()
            if o.id in member_org_ids and o.deleted_at is None
        ]

    async def update(
        self,
        org: Organization,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        if name is not None:
            org.name = name
        if description is not None:
            org.description = description
        return org

    async def soft_delete(self, org: Organization, deleted_at: datetime) -> None:
        org.deleted_at = deleted_at
        org.slug = f"{org.slug}-deleted-{uuid.uuid4().hex[:8]}"

    async def add_member(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> OrganizationMember:
        member = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )
        self._members[member.id] = member
        return member

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return next(
            (
                m
                for m in self._members.values()
                if m.org_id == org_id and m.user_id == user_id
            ),
            None,
        )

    async def list_members(self, org_id: uuid.UUID) -> list[OrganizationMember]:
        return [m for m in self._members.values() if m.org_id == org_id]

    async def remove_member(self, member: OrganizationMember) -> None:
        self._members.pop(member.id, None)


class FakeUserRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    def seed(self, user: User) -> None:
        self._store[user.id] = user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(email: str = "owner@example.com") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        full_name="Test User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def owner() -> User:
    return _make_user("owner@example.com")


@pytest.fixture()
def other_user() -> User:
    return _make_user("other@example.com")


@pytest.fixture()
def org_repo() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture()
def user_repo(owner: User, other_user: User) -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(owner)
    repo.seed(other_user)
    return repo


@pytest.fixture()
def client(
    owner: User,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
) -> Iterator[TestClient]:
    app = create_app()

    def fake_service() -> OrganizationService:
        return OrganizationService(org_repo=org_repo, user_repo=user_repo)  # type: ignore[arg-type]

    app.dependency_overrides[get_organization_service] = fake_service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(owner.id)
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper — create an org via the service directly
# ---------------------------------------------------------------------------


async def _create_org(
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner_id: uuid.UUID,
    name: str = "Acme",
) -> Organization:
    svc = OrganizationService(org_repo=org_repo, user_repo=user_repo)  # type: ignore[arg-type]
    return await svc.create_organization(user_id=owner_id, name=name)


# ---------------------------------------------------------------------------
# Tests — create
# ---------------------------------------------------------------------------


def test_create_organization_returns_201(client: TestClient) -> None:
    response = client.post("/api/v1/organizations", json={"name": "Acme"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["slug"] == "acme"


def test_create_organization_slug_conflict_returns_409(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    asyncio.run(_create_org(org_repo, user_repo, owner.id, "Acme"))
    response = client.post("/api/v1/organizations", json={"name": "Acme"})
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Tests — list
# ---------------------------------------------------------------------------


def test_list_organizations_returns_200(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    asyncio.run(_create_org(org_repo, user_repo, owner.id, "Acme"))
    response = client.get("/api/v1/organizations")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Acme"


# ---------------------------------------------------------------------------
# Tests — get
# ---------------------------------------------------------------------------


def test_get_organization_returns_200(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.get(f"/api/v1/organizations/{org.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(org.id)


def test_get_organization_not_member_returns_403(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    other_user: User,
) -> None:
    import asyncio

    # create org owned by other_user, current user (owner fixture) is NOT a member
    org = asyncio.run(_create_org(org_repo, user_repo, other_user.id, "Other Org"))
    response = client.get(f"/api/v1/organizations/{org.id}")
    assert response.status_code == 403


def test_get_organization_nonexistent_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/organizations/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------


def test_update_organization_returns_200(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.patch(
        f"/api/v1/organizations/{org.id}", json={"name": "Acme Updated"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Updated"


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------


def test_delete_organization_returns_204(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.delete(f"/api/v1/organizations/{org.id}")
    assert response.status_code == 204


def test_deleted_organization_is_not_returned_by_get_or_list(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    client.delete(f"/api/v1/organizations/{org.id}")

    assert client.get(f"/api/v1/organizations/{org.id}").status_code == 404
    assert client.get("/api/v1/organizations").json()["items"] == []


def test_deleted_organization_row_is_preserved_not_removed(
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    """soft_delete must mark the row deleted, not drop it — child projects and
    tasks reference the organization and must not be orphaned by a cascade."""
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    asyncio.run(
        OrganizationService(org_repo=org_repo, user_repo=user_repo).delete_organization(  # type: ignore[arg-type]
            org_id=org.id, user_id=owner.id
        )
    )
    assert org.id in org_repo._orgs
    assert org_repo._orgs[org.id].deleted_at is not None


def test_slug_is_reusable_after_organization_is_deleted(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    old = asyncio.run(_create_org(org_repo, user_repo, owner.id, "Acme"))
    client.delete(f"/api/v1/organizations/{old.id}")

    response = client.post("/api/v1/organizations", json={"name": "Acme"})
    assert response.status_code == 201
    assert response.json()["slug"] == "acme"


# ---------------------------------------------------------------------------
# Tests — members
# ---------------------------------------------------------------------------


def test_invite_member_returns_201(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
    other_user: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={"email": other_user.email, "role": "member"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "member"


def test_invite_nonexistent_user_returns_404(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={"email": "nobody@example.com", "role": "member"},
    )
    assert response.status_code == 404


def test_invite_duplicate_member_returns_409(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
    other_user: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    # invite once
    asyncio.run(
        OrganizationService(org_repo=org_repo, user_repo=user_repo).invite_member(  # type: ignore[arg-type]
            org_id=org.id,
            inviter_id=owner.id,
            email=other_user.email,
            role="member",
        )
    )
    response = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={"email": other_user.email, "role": "member"},
    )
    assert response.status_code == 409


def test_list_members_returns_200(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.get(f"/api/v1/organizations/{org.id}/members")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["role"] == "owner"
    assert body["items"][0]["display_name"] == "Test User"


def test_list_members_falls_back_to_email_when_full_name_missing(
    org_repo: FakeOrganizationRepository,
) -> None:
    import asyncio

    now = datetime.now(UTC)
    nameless_user_repo = FakeUserRepository()
    user = User(
        id=uuid.uuid4(),
        email="noname@example.com",
        hashed_password="x",
        full_name=None,
        created_at=now,
        updated_at=now,
    )
    nameless_user_repo.seed(user)
    org = asyncio.run(_create_org(org_repo, nameless_user_repo, user.id))
    svc = OrganizationService(org_repo=org_repo, user_repo=nameless_user_repo)  # type: ignore[arg-type]
    members = asyncio.run(svc.list_members(org_id=org.id, user_id=user.id))
    assert members[0].display_name == "noname@example.com"


def test_remove_member_returns_204(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
    other_user: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    asyncio.run(
        OrganizationService(org_repo=org_repo, user_repo=user_repo).invite_member(  # type: ignore[arg-type]
            org_id=org.id,
            inviter_id=owner.id,
            email=other_user.email,
            role="member",
        )
    )
    response = client.delete(f"/api/v1/organizations/{org.id}/members/{other_user.id}")
    assert response.status_code == 204


def test_remove_owner_returns_403(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
) -> None:
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.delete(f"/api/v1/organizations/{org.id}/members/{owner.id}")
    assert response.status_code == 403


def test_invite_owner_role_by_admin_returns_403(
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
    other_user: User,
) -> None:
    """Admins must not be able to grant the owner role to escalate privileges."""
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    service = OrganizationService(org_repo=org_repo, user_repo=user_repo)  # type: ignore[arg-type]
    asyncio.run(
        service.invite_member(
            org_id=org.id,
            inviter_id=owner.id,
            email=other_user.email,
            role="admin",
        )
    )
    third_user = _make_user("third@example.com")
    user_repo.seed(third_user)

    async def attempt() -> None:
        await service.invite_member(
            org_id=org.id,
            inviter_id=other_user.id,
            email=third_user.email,
            role="owner",
        )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(attempt())
    assert exc_info.value.status_code == 403


def test_invite_owner_role_by_owner_returns_201(
    client: TestClient,
    org_repo: FakeOrganizationRepository,
    user_repo: FakeUserRepository,
    owner: User,
    other_user: User,
) -> None:
    """Owners are allowed to grant the owner role to another member."""
    import asyncio

    org = asyncio.run(_create_org(org_repo, user_repo, owner.id))
    response = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={"email": other_user.email, "role": "owner"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "owner"
