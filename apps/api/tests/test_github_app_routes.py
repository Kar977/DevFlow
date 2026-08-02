"""Route tests for GitHub App endpoints — wiring, params, status codes."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.repository import Repository
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_app import get_github_app_service
from devflow_api.main import create_app

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _installation() -> GitHubInstallation:
    return GitHubInstallation(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        installation_id=42,
        account_login="octo-org",
        account_type="Organization",
        account_avatar_url=None,
        repository_selection="selected",
        suspended_at=None,
        created_by=USER_ID,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _repository(tracked: bool = False) -> Repository:
    return Repository(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        github_installation_id=uuid.uuid4(),
        github_repo_id=1001,
        full_name="octo-org/api",
        private=True,
        default_branch="main",
        tracked=tracked,
        last_synced_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class StubAppService:
    def __init__(self) -> None:
        self.calls: dict[str, Any] = {}

    async def get_install_url(self, *, org_id: uuid.UUID, user_id: uuid.UUID) -> str:
        self.calls["get_install_url"] = (org_id, user_id)
        return "https://github.com/apps/devflow/installations/new?state=abc"

    async def complete_setup(
        self,
        *,
        user_id: uuid.UUID,
        installation_id: int,
        setup_action: str,
        state: str,
    ) -> GitHubInstallation:
        self.calls["complete_setup"] = (installation_id, setup_action, state)
        return _installation()

    async def list_installations(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[GitHubInstallation]:
        return [_installation()]

    async def disconnect(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, installation_uuid: uuid.UUID
    ) -> None:
        self.calls["disconnect"] = installation_uuid

    async def refresh_installation_repositories(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, installation_uuid: uuid.UUID
    ) -> int:
        return 3

    async def list_repositories(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        tracked: bool | None = None,
    ) -> list[Repository]:
        self.calls["list_repositories"] = tracked
        return [_repository()]

    async def set_repository_tracked(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        repo_id: uuid.UUID,
        tracked: bool,
    ) -> Repository:
        self.calls["set_repository_tracked"] = (repo_id, tracked)
        return _repository(tracked=tracked)

    async def handle_webhook(
        self, *, signature: str, raw_body: bytes, event: str
    ) -> None:
        self.calls["webhook_event"] = event


@pytest.fixture()
def stub() -> StubAppService:
    return StubAppService()


@pytest.fixture()
def client(stub: StubAppService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_github_app_service] = lambda: stub
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        yield c


def test_install_url_endpoint(client: TestClient, stub: StubAppService) -> None:
    response = client.post(
        "/api/v1/integrations/github/app/install-url",
        json={"organization_id": str(ORG_ID)},
    )
    assert response.status_code == 200
    assert "installations/new" in response.json()["install_url"]
    assert stub.calls["get_install_url"] == (ORG_ID, USER_ID)


def test_setup_endpoint(client: TestClient, stub: StubAppService) -> None:
    response = client.post(
        "/api/v1/integrations/github/app/setup",
        json={"installation_id": 42, "setup_action": "install", "state": "abc"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["account_login"] == "octo-org"
    assert body["installation_id"] == 42
    assert stub.calls["complete_setup"] == (42, "install", "abc")


def test_list_installations_endpoint(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/integrations/github/app/installations?organization_id={ORG_ID}"
    )
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["account_login"] == "octo-org"


def test_delete_installation_endpoint(client: TestClient, stub: StubAppService) -> None:
    installation_uuid = uuid.uuid4()
    response = client.delete(
        f"/api/v1/integrations/github/app/installations/{installation_uuid}"
        f"?organization_id={ORG_ID}"
    )
    assert response.status_code == 204
    assert stub.calls["disconnect"] == installation_uuid


def test_refresh_repos_endpoint(client: TestClient) -> None:
    installation_uuid = uuid.uuid4()
    response = client.post(
        f"/api/v1/integrations/github/app/installations/{installation_uuid}"
        f"/refresh-repos?organization_id={ORG_ID}"
    )
    assert response.status_code == 200
    assert response.json()["repos"] == 3


def test_list_repositories_endpoint(client: TestClient, stub: StubAppService) -> None:
    response = client.get(f"/api/v1/repositories?organization_id={ORG_ID}&tracked=true")
    assert response.status_code == 200
    items = response.json()["data"]
    assert items[0]["full_name"] == "octo-org/api"
    assert stub.calls["list_repositories"] is True


def test_patch_repository_tracked_endpoint(
    client: TestClient, stub: StubAppService
) -> None:
    repo_id = uuid.uuid4()
    response = client.patch(
        f"/api/v1/repositories/{repo_id}?organization_id={ORG_ID}",
        json={"tracked": True},
    )
    assert response.status_code == 200
    assert response.json()["tracked"] is True
    assert stub.calls["set_repository_tracked"] == (repo_id, True)


def test_webhook_passes_event_header(client: TestClient, stub: StubAppService) -> None:
    response = client.post(
        "/api/v1/integrations/github/webhooks",
        content=b"{}",
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "installation",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 204
    assert stub.calls["webhook_event"] == "installation"
