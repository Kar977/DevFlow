"""GitHubAppService tests — install flow, repo tracking, webhooks, permissions."""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

import devflow_api.core.services.github_app as github_app_module
from devflow_api.core.config import Settings
from devflow_api.core.errors import AppError
from devflow_api.core.integrations.github.oauth import create_install_state
from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.repository import Repository
from devflow_api.core.services.github_app import GitHubAppService

_TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-prod"
WEBHOOK_SECRET = "test-webhook-secret"  # noqa: S105


# ===========================================================================
# Fakes
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


class FakeInstallationRepo:
    def __init__(self) -> None:
        self.rows: dict[int, GitHubInstallation] = {}

    async def upsert(
        self,
        *,
        organization_id: uuid.UUID,
        installation_id: int,
        account_login: str,
        account_type: str,
        account_avatar_url: str | None,
        repository_selection: str,
        created_by: uuid.UUID | None,
    ) -> GitHubInstallation:
        existing = self.rows.get(installation_id)
        if existing:
            existing.account_login = account_login
            existing.account_type = account_type
            existing.account_avatar_url = account_avatar_url
            existing.repository_selection = repository_selection
            return existing
        row = GitHubInstallation(
            id=uuid.uuid4(),
            organization_id=organization_id,
            installation_id=installation_id,
            account_login=account_login,
            account_type=account_type,
            account_avatar_url=account_avatar_url,
            repository_selection=repository_selection,
            suspended_at=None,
            created_by=created_by,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.rows[installation_id] = row
        return row

    async def get_by_id(self, row_id: uuid.UUID) -> GitHubInstallation | None:
        for row in self.rows.values():
            if row.id == row_id:
                return row
        return None

    async def get_by_installation_id(
        self, installation_id: int
    ) -> GitHubInstallation | None:
        return self.rows.get(installation_id)

    async def list_for_org(self, org_id: uuid.UUID) -> list[GitHubInstallation]:
        return [r for r in self.rows.values() if r.organization_id == org_id]

    async def set_suspended_at(
        self, row: GitHubInstallation, suspended_at: datetime | None
    ) -> GitHubInstallation:
        row.suspended_at = suspended_at
        return row

    async def delete(self, row: GitHubInstallation) -> None:
        self.rows.pop(row.installation_id, None)


class FakeRepositoryRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, int], Repository] = {}

    def seed(self, repo: Repository) -> None:
        self.rows[(repo.github_installation_id, repo.github_repo_id)] = repo

    async def upsert(
        self,
        *,
        organization_id: uuid.UUID,
        github_installation_id: uuid.UUID,
        github_repo_id: int,
        full_name: str,
        private: bool,
        default_branch: str | None,
    ) -> Repository:
        key = (github_installation_id, github_repo_id)
        existing = self.rows.get(key)
        if existing:
            existing.full_name = full_name
            existing.private = private
            existing.default_branch = default_branch
            return existing
        row = Repository(
            id=uuid.uuid4(),
            organization_id=organization_id,
            github_installation_id=github_installation_id,
            github_repo_id=github_repo_id,
            full_name=full_name,
            private=private,
            default_branch=default_branch,
            tracked=False,
            last_synced_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.rows[key] = row
        return row

    async def get_by_id_for_org(
        self, repo_id: uuid.UUID, org_id: uuid.UUID
    ) -> Repository | None:
        for row in self.rows.values():
            if row.id == repo_id and row.organization_id == org_id:
                return row
        return None

    async def list_for_org(
        self, org_id: uuid.UUID, *, tracked: bool | None = None
    ) -> list[Repository]:
        rows = [r for r in self.rows.values() if r.organization_id == org_id]
        if tracked is not None:
            rows = [r for r in rows if r.tracked == tracked]
        return rows

    async def set_tracked(self, repo: Repository, tracked: bool) -> Repository:
        repo.tracked = tracked
        return repo

    async def delete_missing(
        self, github_installation_id: uuid.UUID, keep_github_repo_ids: set[int]
    ) -> int:
        to_delete = [
            key
            for key, row in self.rows.items()
            if key[0] == github_installation_id
            and row.github_repo_id not in keep_github_repo_ids
        ]
        for key in to_delete:
            del self.rows[key]
        return len(to_delete)

    async def delete_by_github_repo_ids(
        self, github_installation_id: uuid.UUID, github_repo_ids: set[int]
    ) -> int:
        to_delete = [
            key
            for key, row in self.rows.items()
            if key[0] == github_installation_id
            and row.github_repo_id in github_repo_ids
        ]
        for key in to_delete:
            del self.rows[key]
        return len(to_delete)


class FakeAppApiClient:
    def __init__(
        self,
        *,
        installation: dict[str, Any] | None = None,
        repositories: list[dict[str, Any]] | None = None,
    ) -> None:
        self.installation = installation or {
            "id": 42,
            "account": {
                "login": "octo-org",
                "type": "Organization",
                "avatar_url": "https://avatars/octo-org",
            },
            "repository_selection": "selected",
        }
        self.repositories = repositories if repositories is not None else []
        self.deleted_installations: list[int] = []
        self.delete_raises: Exception | None = None

    async def get_installation(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        return self.installation

    async def list_installation_repositories(
        self, token: str, **_: object
    ) -> list[dict[str, Any]]:
        return self.repositories

    async def delete_installation(self, app_jwt: str, installation_id: int) -> None:
        if self.delete_raises:
            raise self.delete_raises
        self.deleted_installations.append(installation_id)


class FakeTokenProvider:
    def mint_app_jwt(self) -> str:
        return "app.jwt"

    async def get_token(self, installation_id: int) -> str:
        return "ghs_test"


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def admin_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def member_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def org_repo(
    org_id: uuid.UUID, admin_id: uuid.UUID, member_id: uuid.UUID
) -> FakeOrgRepo:
    repo = FakeOrgRepo()
    repo.seed_member(org_id, admin_id, "admin")
    repo.seed_member(org_id, member_id, "member")
    return repo


@pytest.fixture()
def installation_repo() -> FakeInstallationRepo:
    return FakeInstallationRepo()


@pytest.fixture()
def repository_repo() -> FakeRepositoryRepo:
    return FakeRepositoryRepo()


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        secret_key=_TEST_SECRET_KEY,
        github_app_id="12345",
        github_app_slug="devflow-insight",
        github_app_private_key="pem",
        github_webhook_secret=WEBHOOK_SECRET,
    )


@pytest.fixture()
def service_factory(
    org_repo: FakeOrgRepo,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    monkeypatch.setattr(github_app_module, "get_settings", lambda: test_settings)

    def _build(api_client: FakeAppApiClient | None = None) -> GitHubAppService:
        return GitHubAppService(
            installation_repo=installation_repo,  # type: ignore[arg-type]
            repository_repo=repository_repo,  # type: ignore[arg-type]
            org_repo=org_repo,  # type: ignore[arg-type]
            api_client=api_client or FakeAppApiClient(),  # type: ignore[arg-type]
            token_provider=FakeTokenProvider(),  # type: ignore[arg-type]
        )

    return _build


def _seed_installation(
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
    installation_id: int = 42,
) -> GitHubInstallation:
    row = GitHubInstallation(
        id=uuid.uuid4(),
        organization_id=org_id,
        installation_id=installation_id,
        account_login="octo-org",
        account_type="Organization",
        account_avatar_url=None,
        repository_selection="selected",
        suspended_at=None,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    installation_repo.rows[installation_id] = row
    return row


def _sign(body: bytes) -> str:
    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


# ===========================================================================
# Install URL
# ===========================================================================


async def test_install_url_contains_slug_and_state(
    service_factory: Any, org_id: uuid.UUID, admin_id: uuid.UUID
) -> None:
    service = service_factory()
    url = await service.get_install_url(org_id=org_id, user_id=admin_id)
    assert url.startswith(
        "https://github.com/apps/devflow-insight/installations/new?state="
    )


async def test_install_url_rejects_plain_member(
    service_factory: Any, org_id: uuid.UUID, member_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.get_install_url(org_id=org_id, user_id=member_id)
    assert exc_info.value.status_code == 403


async def test_install_url_rejects_non_member(
    service_factory: Any, org_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.get_install_url(org_id=org_id, user_id=uuid.uuid4())
    assert exc_info.value.status_code == 403


async def test_install_url_requires_configured_app(
    service_factory: Any,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        github_app_module,
        "get_settings",
        lambda: Settings(secret_key=_TEST_SECRET_KEY),
    )
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.get_install_url(org_id=org_id, user_id=admin_id)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "github_app_not_configured"


# ===========================================================================
# complete_setup
# ===========================================================================


async def test_complete_setup_links_installation_and_refreshes_repos(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    api = FakeAppApiClient(
        repositories=[
            {
                "id": 1001,
                "full_name": "octo-org/api",
                "private": True,
                "default_branch": "main",
            },
            {
                "id": 1002,
                "full_name": "octo-org/web",
                "private": False,
                "default_branch": "main",
            },
        ]
    )
    service = service_factory(api)
    state = create_install_state(org_id, admin_id, secret_key=_TEST_SECRET_KEY)

    installation = await service.complete_setup(
        user_id=admin_id, installation_id=42, setup_action="install", state=state
    )

    assert installation.organization_id == org_id
    assert installation.account_login == "octo-org"
    assert 42 in installation_repo.rows
    repos = await repository_repo.list_for_org(org_id)
    assert {r.full_name for r in repos} == {"octo-org/api", "octo-org/web"}
    assert all(not r.tracked for r in repos)


async def test_complete_setup_is_idempotent_for_update(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    service = service_factory()
    state = create_install_state(org_id, admin_id, secret_key=_TEST_SECRET_KEY)
    first = await service.complete_setup(
        user_id=admin_id, installation_id=42, setup_action="install", state=state
    )
    second = await service.complete_setup(
        user_id=admin_id, installation_id=42, setup_action="update", state=state
    )
    assert first.id == second.id
    assert len(installation_repo.rows) == 1


async def test_complete_setup_rejects_installation_linked_elsewhere(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_repo: FakeOrgRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    _seed_installation(installation_repo, other_org, installation_id=42)
    service = service_factory()
    state = create_install_state(org_id, admin_id, secret_key=_TEST_SECRET_KEY)
    with pytest.raises(AppError) as exc_info:
        await service.complete_setup(
            user_id=admin_id,
            installation_id=42,
            setup_action="install",
            state=state,
        )
    assert exc_info.value.status_code == 409


async def test_complete_setup_rejects_invalid_state(
    service_factory: Any, admin_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.complete_setup(
            user_id=admin_id,
            installation_id=42,
            setup_action="install",
            state="garbage",
        )
    assert exc_info.value.status_code == 401


async def test_complete_setup_rejects_plain_member(
    service_factory: Any, org_id: uuid.UUID, member_id: uuid.UUID
) -> None:
    service = service_factory()
    state = create_install_state(org_id, member_id, secret_key=_TEST_SECRET_KEY)
    with pytest.raises(AppError) as exc_info:
        await service.complete_setup(
            user_id=member_id,
            installation_id=42,
            setup_action="install",
            state=state,
        )
    assert exc_info.value.status_code == 403


# ===========================================================================
# refresh_repositories
# ===========================================================================


async def test_refresh_preserves_tracked_flag(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    tracked_repo = Repository(
        id=uuid.uuid4(),
        organization_id=org_id,
        github_installation_id=installation.id,
        github_repo_id=1001,
        full_name="octo-org/api",
        private=True,
        default_branch="main",
        tracked=True,
        last_synced_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository_repo.seed(tracked_repo)
    api = FakeAppApiClient(
        repositories=[
            {
                "id": 1001,
                "full_name": "octo-org/api",
                "private": True,
                "default_branch": "main",
            },
            {
                "id": 1002,
                "full_name": "octo-org/new",
                "private": False,
                "default_branch": "main",
            },
        ]
    )
    service = service_factory(api)

    count = await service.refresh_repositories(installation=installation)

    assert count == 2
    rows = await repository_repo.list_for_org(org_id)
    by_name = {r.full_name: r for r in rows}
    assert by_name["octo-org/api"].tracked is True
    assert by_name["octo-org/new"].tracked is False


async def test_refresh_prunes_repos_no_longer_accessible(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    stale = Repository(
        id=uuid.uuid4(),
        organization_id=org_id,
        github_installation_id=installation.id,
        github_repo_id=999,
        full_name="octo-org/gone",
        private=False,
        default_branch="main",
        tracked=True,
        last_synced_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository_repo.seed(stale)
    api = FakeAppApiClient(
        repositories=[
            {
                "id": 1001,
                "full_name": "octo-org/api",
                "private": True,
                "default_branch": "main",
            }
        ]
    )
    service = service_factory(api)

    await service.refresh_repositories(installation=installation)

    rows = await repository_repo.list_for_org(org_id)
    assert {r.full_name for r in rows} == {"octo-org/api"}


# ===========================================================================
# Repo tracking + listing
# ===========================================================================


async def test_set_repository_tracked_toggles(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    repo = await repository_repo.upsert(
        organization_id=org_id,
        github_installation_id=installation.id,
        github_repo_id=1001,
        full_name="octo-org/api",
        private=True,
        default_branch="main",
    )
    service = service_factory()

    updated = await service.set_repository_tracked(
        org_id=org_id, user_id=admin_id, repo_id=repo.id, tracked=True
    )
    assert updated.tracked is True


async def test_set_repository_tracked_rejects_member(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
    member_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    repo = await repository_repo.upsert(
        organization_id=org_id,
        github_installation_id=installation.id,
        github_repo_id=1001,
        full_name="octo-org/api",
        private=True,
        default_branch="main",
    )
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.set_repository_tracked(
            org_id=org_id, user_id=member_id, repo_id=repo.id, tracked=True
        )
    assert exc_info.value.status_code == 403


async def test_set_repository_tracked_unknown_repo_404(
    service_factory: Any, org_id: uuid.UUID, admin_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.set_repository_tracked(
            org_id=org_id, user_id=admin_id, repo_id=uuid.uuid4(), tracked=True
        )
    assert exc_info.value.status_code == 404


async def test_list_repositories_requires_membership(
    service_factory: Any, org_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.list_repositories(org_id=org_id, user_id=uuid.uuid4())
    assert exc_info.value.status_code == 403


async def test_list_installations_visible_to_member(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
    member_id: uuid.UUID,
) -> None:
    _seed_installation(installation_repo, org_id)
    service = service_factory()
    rows = await service.list_installations(org_id=org_id, user_id=member_id)
    assert len(rows) == 1


# ===========================================================================
# disconnect
# ===========================================================================


async def test_disconnect_deletes_row_and_uninstalls(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    api = FakeAppApiClient()
    service = service_factory(api)

    await service.disconnect(
        org_id=org_id, user_id=admin_id, installation_uuid=installation.id
    )

    assert installation_repo.rows == {}
    assert api.deleted_installations == [42]


async def test_disconnect_survives_github_error(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    api = FakeAppApiClient()
    api.delete_raises = RuntimeError("github down")
    service = service_factory(api)

    await service.disconnect(
        org_id=org_id, user_id=admin_id, installation_uuid=installation.id
    )
    assert installation_repo.rows == {}


async def test_disconnect_unknown_installation_404(
    service_factory: Any, org_id: uuid.UUID, admin_id: uuid.UUID
) -> None:
    service = service_factory()
    with pytest.raises(AppError) as exc_info:
        await service.disconnect(
            org_id=org_id, user_id=admin_id, installation_uuid=uuid.uuid4()
        )
    assert exc_info.value.status_code == 404


# ===========================================================================
# Webhooks
# ===========================================================================


async def test_webhook_installation_deleted_removes_row(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
) -> None:
    _seed_installation(installation_repo, org_id)
    service = service_factory()
    body = json.dumps({"action": "deleted", "installation": {"id": 42}}).encode()

    await service.handle_webhook(
        signature=_sign(body), raw_body=body, event="installation"
    )
    assert installation_repo.rows == {}


async def test_webhook_unknown_installation_is_ignored(
    service_factory: Any,
) -> None:
    service = service_factory()
    body = json.dumps({"action": "deleted", "installation": {"id": 777}}).encode()
    # must not raise
    await service.handle_webhook(
        signature=_sign(body), raw_body=body, event="installation"
    )


async def test_webhook_suspend_and_unsuspend(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    org_id: uuid.UUID,
) -> None:
    row = _seed_installation(installation_repo, org_id)
    service = service_factory()

    body = json.dumps({"action": "suspend", "installation": {"id": 42}}).encode()
    await service.handle_webhook(
        signature=_sign(body), raw_body=body, event="installation"
    )
    assert row.suspended_at is not None

    body = json.dumps({"action": "unsuspend", "installation": {"id": 42}}).encode()
    await service.handle_webhook(
        signature=_sign(body), raw_body=body, event="installation"
    )
    assert row.suspended_at is None


async def test_webhook_installation_repositories_added_and_removed(
    service_factory: Any,
    installation_repo: FakeInstallationRepo,
    repository_repo: FakeRepositoryRepo,
    org_id: uuid.UUID,
) -> None:
    installation = _seed_installation(installation_repo, org_id)
    await repository_repo.upsert(
        organization_id=org_id,
        github_installation_id=installation.id,
        github_repo_id=1001,
        full_name="octo-org/old",
        private=False,
        default_branch="main",
    )
    service = service_factory()
    body = json.dumps(
        {
            "action": "added",
            "installation": {"id": 42},
            "repositories_added": [
                {
                    "id": 1002,
                    "full_name": "octo-org/new",
                    "private": True,
                }
            ],
            "repositories_removed": [{"id": 1001, "full_name": "octo-org/old"}],
        }
    ).encode()

    await service.handle_webhook(
        signature=_sign(body), raw_body=body, event="installation_repositories"
    )

    rows = await repository_repo.list_for_org(org_id)
    assert {r.full_name for r in rows} == {"octo-org/new"}


async def test_webhook_invalid_signature_rejected(
    service_factory: Any,
) -> None:
    service = service_factory()
    body = b'{"action": "deleted"}'
    with pytest.raises(AppError) as exc_info:
        await service.handle_webhook(
            signature="sha256=" + "0" * 64, raw_body=body, event="installation"
        )
    assert exc_info.value.status_code == 401
