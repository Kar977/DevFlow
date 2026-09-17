"""Demo-mode GitHub integration — every path must be a no-network stand-in.

Two things are verified here that the rest of the suite can't cover:

1. None of :class:`DemoGitHubApiClient`'s methods, nor
   :class:`DemoGitHubSyncService.handle_callback`, ever open a socket — even
   if a bug reintroduced a call to the real ``httpx.AsyncClient``, every
   test in this module fails loudly instead of quietly reaching the network.
2. The three ``get_*_service`` dependency factories actually switch to the
   demo variants when ``Settings.demo_mode`` is on.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

import devflow_api.core.services.github_app as github_app_module
import devflow_api.core.services.github_sync as github_sync_module
import devflow_api.core.services.org_sync as org_sync_module
import devflow_api.demo.github as demo_github_module
from devflow_api.core.config import Settings
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.services.github_app import get_github_app_service
from devflow_api.core.services.github_sync import get_github_sync_service
from devflow_api.core.services.org_sync import get_org_sync_service
from devflow_api.demo.github import (
    DemoGitHubApiClient,
    DemoGitHubAppService,
    DemoGitHubSyncService,
    DemoInstallationTokenProvider,
)

_TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-prod"
_DEMO_SETTINGS = Settings(secret_key=_TEST_SECRET_KEY, demo_mode=True)


class _NetworkBlockedError(Exception):
    """Raised instead of ever opening a real HTTP connection."""


class _ExplodingAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise _NetworkBlockedError(
            "a demo-mode code path tried to open a real httpx client"
        )


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test below must never construct a real httpx.AsyncClient.

    Both GitHubApiClient._request and oauth.exchange_code_for_token create
    their client via `httpx.AsyncClient(...)`, so patching the attribute on
    the shared `httpx` module covers both call sites.
    """
    monkeypatch.setattr(httpx, "AsyncClient", _ExplodingAsyncClient)


# ===========================================================================
# Fakes (org membership + GitHub connection storage)
# ===========================================================================


class FakeOrgRepo:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))


class FakeConnectionRepo:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, GitHubConnection] = {}

    async def get_by_user_id(self, user_id: uuid.UUID) -> GitHubConnection | None:
        return self.rows.get(user_id)

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        github_user_id: str,
        github_login: str,
        access_token_encrypted: str,
        scopes: str,
    ) -> GitHubConnection:
        conn = GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            access_token_encrypted=access_token_encrypted,
            scopes=scopes,
        )
        self.rows[user_id] = conn
        return conn

    async def update_token(
        self, conn: GitHubConnection, *, access_token_encrypted: str, scopes: str
    ) -> GitHubConnection:
        conn.access_token_encrypted = access_token_encrypted
        conn.scopes = scopes
        return conn


# ===========================================================================
# DemoGitHubApiClient — every method, zero network
# ===========================================================================


@pytest.fixture()
def demo_client() -> DemoGitHubApiClient:
    return DemoGitHubApiClient()


async def test_create_installation_access_token_has_no_network(
    demo_client: DemoGitHubApiClient,
) -> None:
    data = await demo_client.create_installation_access_token("app-jwt", 90_000_001)
    assert "token" in data
    assert "expires_at" in data


async def test_get_installation_has_no_network(
    demo_client: DemoGitHubApiClient,
) -> None:
    data = await demo_client.get_installation("app-jwt", 90_000_001)
    assert data["account"]["login"] == "acme-inc"
    assert data["repository_selection"] == "selected"


async def test_delete_installation_has_no_network(
    demo_client: DemoGitHubApiClient,
) -> None:
    await demo_client.delete_installation("app-jwt", 90_000_001)  # must not raise


async def test_list_installation_repositories_has_no_network(
    demo_client: DemoGitHubApiClient,
) -> None:
    repos = await demo_client.list_installation_repositories("token")
    assert len(repos) >= 1
    required_keys = {"id", "full_name", "private", "default_branch"}
    assert all(required_keys <= r.keys() for r in repos)


async def test_list_repo_pulls_has_no_network(demo_client: DemoGitHubApiClient) -> None:
    pulls = await demo_client.list_repo_pulls("token", "acme-inc", "web-app")
    assert pulls == []


async def test_get_authenticated_user_has_no_network(
    demo_client: DemoGitHubApiClient,
) -> None:
    user = await demo_client.get_authenticated_user("token")
    assert user["login"] == "demo-owner"


async def test_list_pr_reviews_has_no_network(demo_client: DemoGitHubApiClient) -> None:
    reviews = await demo_client.list_pr_reviews("token", "acme-inc", "web-app", 1)
    assert reviews == []


# ===========================================================================
# DemoInstallationTokenProvider — no JWT minting, no network
# ===========================================================================


async def test_token_provider_mints_without_real_credentials() -> None:
    provider = DemoInstallationTokenProvider(api_client=DemoGitHubApiClient())
    assert provider.mint_app_jwt()  # would raise ValueError for real, blank creds
    assert await provider.get_token(90_000_001)


# ===========================================================================
# DemoGitHubAppService — install URL never points at github.com
# ===========================================================================


async def test_get_install_url_stays_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_github_module, "get_settings", lambda: _DEMO_SETTINGS)
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    org_repo = FakeOrgRepo()
    org_repo.seed_member(org_id, user_id, "owner")
    demo_client = DemoGitHubApiClient()
    service = DemoGitHubAppService(
        installation_repo=object(),  # type: ignore[arg-type]
        repository_repo=object(),  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        api_client=demo_client,
        token_provider=DemoInstallationTokenProvider(api_client=demo_client),
    )

    url = await service.get_install_url(org_id=org_id, user_id=user_id)

    assert url.startswith("/integrations/github/setup?")
    assert "github.com" not in url


# ===========================================================================
# DemoGitHubSyncService — OAuth "callback" never exchanges a real code
# ===========================================================================


async def test_authorize_url_stays_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_github_module, "get_settings", lambda: _DEMO_SETTINGS)
    service = DemoGitHubSyncService(
        conn_repo=FakeConnectionRepo(),  # type: ignore[arg-type]
        cipher=None,
        api_client=DemoGitHubApiClient(),
    )

    url = service.authorize_url(user_id=uuid.uuid4())

    assert url.startswith("/integrations/github/callback?")
    assert "github.com" not in url


async def test_handle_callback_creates_connection_without_exchanging_a_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo_github_module, "get_settings", lambda: _DEMO_SETTINGS)
    conn_repo = FakeConnectionRepo()
    service = DemoGitHubSyncService(
        conn_repo=conn_repo,  # type: ignore[arg-type]
        cipher=None,  # a real service would 503 with no cipher — demo skips it
        api_client=DemoGitHubApiClient(),
    )
    user_id = uuid.uuid4()
    from devflow_api.core.integrations.github.oauth import create_oauth_state

    state = create_oauth_state(user_id, secret_key=_DEMO_SETTINGS.secret_key)

    conn = await service.handle_callback(user_id=user_id, code="demo-code", state=state)

    assert conn.github_login == "demo-owner"
    assert conn_repo.rows[user_id] is conn

    # Re-entering the flow updates the existing row rather than duplicating it.
    second = await service.handle_callback(
        user_id=user_id, code="demo-code", state=state
    )
    assert second is conn


# ===========================================================================
# Dependency factories — demo_mode actually switches every one of them
# ===========================================================================


async def test_github_app_service_factory_uses_demo_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(github_app_module, "get_settings", lambda: _DEMO_SETTINGS)

    service = get_github_app_service(session=object())  # type: ignore[arg-type]

    assert isinstance(service, DemoGitHubAppService)
    assert isinstance(service._api_client, DemoGitHubApiClient)  # noqa: SLF001
    assert isinstance(
        service._token_provider,  # noqa: SLF001
        DemoInstallationTokenProvider,
    )


async def test_github_sync_service_factory_uses_demo_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: _DEMO_SETTINGS)

    service = get_github_sync_service(session=object())  # type: ignore[arg-type]

    assert isinstance(service, DemoGitHubSyncService)
    assert isinstance(service._api_client, DemoGitHubApiClient)  # noqa: SLF001


async def test_org_sync_service_factory_uses_demo_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(org_sync_module, "get_settings", lambda: _DEMO_SETTINGS)

    service = get_org_sync_service(session=object())  # type: ignore[arg-type]

    assert isinstance(service._api_client, DemoGitHubApiClient)  # noqa: SLF001
    assert isinstance(
        service._token_provider,  # noqa: SLF001
        DemoInstallationTokenProvider,
    )


async def test_factories_use_real_client_outside_demo_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity check: outside demo mode nothing changed — still the real client."""
    from devflow_api.core.integrations.github.client import GitHubApiClient

    real_settings = Settings(secret_key=_TEST_SECRET_KEY, demo_mode=False)
    monkeypatch.setattr(github_app_module, "get_settings", lambda: real_settings)

    service = get_github_app_service(session=object())  # type: ignore[arg-type]

    assert not isinstance(service, DemoGitHubAppService)
    assert type(service._api_client) is GitHubApiClient  # noqa: SLF001
