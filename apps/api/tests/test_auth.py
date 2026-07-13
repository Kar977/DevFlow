"""Auth endpoint tests — register, login, refresh, logout, me."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization import Organization
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.refresh_token import RefreshToken
from devflow_api.core.models.user import User
from devflow_api.core.security import hash_token
from devflow_api.core.services.auth import AuthService, get_auth_service
from devflow_api.core.services.organization import OrganizationService
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeUserRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, User] = {}

    async def exists_by_email(self, email: str) -> bool:
        return any(u.email == email for u in self._store.values())

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
    ) -> User:
        now = datetime.now(UTC)
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            created_at=now,
            updated_at=now,
        )
        self._store[user.id] = user
        return user

    async def update(
        self,
        user: User,
        *,
        full_name: str | None,
        avatar_url: str | None,
    ) -> User:
        user.full_name = full_name
        user.avatar_url = avatar_url
        return user


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self._orgs: dict[uuid.UUID, Organization] = {}
        self._members: list[OrganizationMember] = []

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        member_org_ids = {m.org_id for m in self._members if m.user_id == user_id}
        return [o for o in self._orgs.values() if o.id in member_org_ids]

    async def get_by_slug(self, slug: str) -> Organization | None:
        return next((o for o in self._orgs.values() if o.slug == slug), None)

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

    async def add_member(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> OrganizationMember:
        now = datetime.now(UTC)
        member = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=now,
        )
        self._members.append(member)
        return member


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self._store: dict[str, RefreshToken] = {}

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self._store[token_hash] = token
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self._store.get(token_hash)

    async def revoke(self, token: RefreshToken, revoked_at: datetime) -> None:
        token.revoked_at = revoked_at

    async def revoke_all_for_user(
        self, user_id: uuid.UUID, revoked_at: datetime
    ) -> None:
        for token in self._store.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = revoked_at


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def token_repo() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def org_repo() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def org_service(org_repo: FakeOrganizationRepository) -> OrganizationService:
    return OrganizationService(
        org_repo=org_repo,  # type: ignore[arg-type]
        user_repo=FakeUserRepository(),  # type: ignore[arg-type]
    )


@pytest.fixture
def auth_service(
    user_repo: FakeUserRepository,
    token_repo: FakeRefreshTokenRepository,
    org_service: OrganizationService,
) -> AuthService:
    return AuthService(
        user_repo=user_repo,  # type: ignore[arg-type]
        token_repo=token_repo,  # type: ignore[arg-type]
        org_service=org_service,
    )


@pytest.fixture
def auth_client(auth_service: AuthService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


def test_register_creates_user(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "dev@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "dev@example.com"
    assert "id" in body
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(auth_client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "secret123"}
    auth_client.post("/api/v1/auth/register", json=payload)
    resp = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_short_password_returns_422(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_returns_access_token(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    assert body["token_type"] == "bearer"


def test_login_sets_httponly_refresh_cookie(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie_header.lower()
    # Non-production environments must not require HTTPS for local dev.
    assert "secure" not in set_cookie_header.lower()


def test_login_sets_secure_cookie_in_production(
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import devflow_api.api.v1.auth.routes as auth_routes_module
    from devflow_api.core.config import Settings

    prod_settings = Settings(
        environment="production",
        secret_key="x" * 40,
        allowed_hosts=["example.com"],
    )
    monkeypatch.setattr(auth_routes_module, "get_settings", lambda: prod_settings)

    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    assert resp.status_code == 200
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "secure" in set_cookie_header.lower()


def test_login_wrong_password_returns_401(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password1"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


def test_refresh_returns_new_access_token_and_rotates_cookie(
    auth_client: TestClient,
) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    old_refresh_token = auth_client.cookies.get("refresh_token")

    resp = auth_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    # Rotation: a fresh refresh cookie is issued, distinct from the one used.
    assert auth_client.cookies.get("refresh_token") != old_refresh_token


def test_refresh_rotates_and_old_token_is_rejected(
    auth_client: TestClient,
    token_repo: FakeRefreshTokenRepository,
) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    old_refresh_token = auth_client.cookies.get("refresh_token")
    assert old_refresh_token is not None

    first = auth_client.post("/api/v1/auth/refresh")
    assert first.status_code == 200

    # Re-using the now-rotated-away token must fail. The client jar now
    # holds the new cookie, so present the old one explicitly.
    auth_client.cookies.set("refresh_token", old_refresh_token)
    second = auth_client.post("/api/v1/auth/refresh")
    assert second.status_code == 401


def test_refresh_reuse_detection_revokes_all_tokens(
    auth_client: TestClient,
) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    old_refresh_token = auth_client.cookies.get("refresh_token")
    assert old_refresh_token is not None

    auth_client.post("/api/v1/auth/refresh")
    new_refresh_token = auth_client.cookies.get("refresh_token")
    assert new_refresh_token is not None

    # Reusing the already-rotated token is treated as a theft signal: it
    # must revoke the whole token family, including the freshly issued one.
    auth_client.cookies.set("refresh_token", old_refresh_token)
    reuse = auth_client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401

    auth_client.cookies.set("refresh_token", new_refresh_token)
    blocked = auth_client.post("/api/v1/auth/refresh")
    assert blocked.status_code == 401


def test_refresh_invalid_token_returns_401(auth_client: TestClient) -> None:
    auth_client.cookies.set("refresh_token", "notavalidtoken")
    resp = auth_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_refresh_missing_cookie_returns_401(auth_client: TestClient) -> None:
    resp = auth_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_refresh_revoked_token_returns_401(
    auth_client: TestClient,
    token_repo: FakeRefreshTokenRepository,
) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    raw_token = auth_client.cookies.get("refresh_token")
    assert raw_token is not None
    stored = token_repo._store[hash_token(raw_token)]
    stored.revoked_at = datetime.now(UTC)

    resp = auth_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_refresh_expired_token_returns_401(
    auth_client: TestClient,
    token_repo: FakeRefreshTokenRepository,
) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    )
    raw_token = auth_client.cookies.get("refresh_token")
    assert raw_token is not None
    stored = token_repo._store[hash_token(raw_token)]
    stored.expires_at = datetime.now(UTC) - timedelta(days=1)

    resp = auth_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def _register_and_login(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"email": "u@example.com", "password": "password1"},
    )
    result: dict[str, str] = client.post(
        "/api/v1/auth/login",
        json={"email": "u@example.com", "password": "password1"},
    ).json()
    return result


def test_logout_revokes_refresh_token(auth_client: TestClient) -> None:
    tokens = _register_and_login(auth_client)
    access = tokens["access_token"]
    refresh = auth_client.cookies.get("refresh_token")
    assert refresh is not None

    resp = auth_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204

    # subsequent refresh must fail (logout revoked this token server-side;
    # re-present it explicitly since the client jar had it cleared)
    auth_client.cookies.set("refresh_token", refresh)
    resp2 = auth_client.post("/api/v1/auth/refresh")
    assert resp2.status_code == 401


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


def test_get_me_returns_profile(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password1"},
    )
    tokens = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password1"},
    ).json()

    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_get_me_without_token_returns_401(auth_client: TestClient) -> None:
    resp = auth_client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------


def test_update_me_changes_full_name(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "patch@example.com", "password": "password1"},
    )
    tokens = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "patch@example.com", "password": "password1"},
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = auth_client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Alice Dev"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Alice Dev"


# ---------------------------------------------------------------------------
# Auto-org on login
# ---------------------------------------------------------------------------


def test_login_creates_personal_org(
    user_repo: FakeUserRepository,
    token_repo: FakeRefreshTokenRepository,
    org_repo: FakeOrganizationRepository,
    org_service: OrganizationService,
) -> None:
    """First login for a new user creates exactly one personal workspace."""
    svc = AuthService(
        user_repo=user_repo,  # type: ignore[arg-type]
        token_repo=token_repo,  # type: ignore[arg-type]
        org_service=org_service,
    )

    import asyncio

    async def run() -> None:
        await svc.register(email="new@example.com", password="password1")
        assert len(org_repo._orgs) == 0, "register must not create an org"

        await svc.login(email="new@example.com", password="password1")
        orgs = list(org_repo._orgs.values())
        assert len(orgs) == 1
        assert orgs[0].slug.startswith("personal-")
        assert "Workspace" in orgs[0].name

    asyncio.run(run())


def test_login_idempotent_org(
    user_repo: FakeUserRepository,
    token_repo: FakeRefreshTokenRepository,
    org_repo: FakeOrganizationRepository,
    org_service: OrganizationService,
) -> None:
    """Repeated logins must not create duplicate personal orgs."""
    svc = AuthService(
        user_repo=user_repo,  # type: ignore[arg-type]
        token_repo=token_repo,  # type: ignore[arg-type]
        org_service=org_service,
    )

    import asyncio

    async def run() -> None:
        await svc.register(email="repeat@example.com", password="password1")
        await svc.login(email="repeat@example.com", password="password1")
        await svc.login(email="repeat@example.com", password="password1")
        assert len(org_repo._orgs) == 1

    asyncio.run(run())
