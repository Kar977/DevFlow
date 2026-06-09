"""GitHub integration tests — crypto, webhooks, OAuth, connection flow, sync."""

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import devflow_api.core.services.github_sync as github_sync_module
from devflow_api.core.config import Settings
from devflow_api.core.integrations.github.crypto import TokenCipher
from devflow_api.core.integrations.github.oauth import (
    OAuthTokenResult,
    build_authorize_url,
)
from devflow_api.core.integrations.github.sync import issue_to_task_fields
from devflow_api.core.integrations.github.webhooks import verify_signature
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_sync import (
    GitHubSyncService,
    get_github_sync_service,
)
from devflow_api.main import create_app

FERNET_KEY = Fernet.generate_key().decode()
WEBHOOK_SECRET = "test-webhook-secret"  # noqa: S105

ServiceFactory = Callable[["FakeApiClient"], GitHubSyncService]


# ===========================================================================
# Unit tests — pure helpers
# ===========================================================================


def test_token_cipher_roundtrip() -> None:
    cipher = TokenCipher(FERNET_KEY)
    encrypted = cipher.encrypt("gho_secret_token")
    assert encrypted != "gho_secret_token"
    assert cipher.decrypt(encrypted) == "gho_secret_token"


def test_token_cipher_requires_key() -> None:
    with pytest.raises(ValueError, match="not configured"):
        TokenCipher("")


def test_verify_signature_accepts_valid() -> None:
    body = b'{"action":"opened"}'
    sig = (
        "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    # does not raise
    verify_signature(payload_bytes=body, secret=WEBHOOK_SECRET, signature_header=sig)


def test_verify_signature_rejects_tampered() -> None:
    body = b'{"action":"opened"}'
    bad = "sha256=" + "0" * 64
    with pytest.raises(ValueError, match="mismatch"):
        verify_signature(
            payload_bytes=body, secret=WEBHOOK_SECRET, signature_header=bad
        )


def test_verify_signature_rejects_bad_prefix() -> None:
    with pytest.raises(ValueError, match="prefix"):
        verify_signature(
            payload_bytes=b"{}", secret=WEBHOOK_SECRET, signature_header="md5=x"
        )


def test_build_authorize_url_contains_params() -> None:
    url = build_authorize_url(
        client_id="cid", redirect_uri="http://cb", state="user:nonce"
    )
    assert "github.com/login/oauth/authorize" in url
    assert "client_id=cid" in url
    assert "state=user:nonce" in url


def test_issue_to_task_fields_maps_html_url() -> None:
    fields = issue_to_task_fields(
        {"title": "Fix bug", "body": "details", "html_url": "https://gh/issues/1"}
    )
    assert fields["title"] == "Fix bug"
    assert fields["github_pr_url"] == "https://gh/issues/1"


# ===========================================================================
# Fakes
# ===========================================================================


class FakeConnRepo:
    def __init__(self) -> None:
        self._by_user: dict[uuid.UUID, GitHubConnection] = {}

    async def get_by_user_id(self, user_id: uuid.UUID) -> GitHubConnection | None:
        return self._by_user.get(user_id)

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
            connected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._by_user[user_id] = conn
        return conn

    async def update_token(
        self,
        conn: GitHubConnection,
        *,
        access_token_encrypted: str,
        scopes: str,
    ) -> GitHubConnection:
        conn.access_token_encrypted = access_token_encrypted
        conn.scopes = scopes
        return conn

    async def delete(self, conn: GitHubConnection) -> None:
        self._by_user.pop(conn.user_id, None)

    def seed(self, conn: GitHubConnection) -> None:
        self._by_user[conn.user_id] = conn


class FakeTaskRepo:
    def __init__(self) -> None:
        self._tasks: list[Task] = []

    async def get_by_github_pr_url(
        self, *, project_id: uuid.UUID, github_pr_url: str
    ) -> Task | None:
        return next(
            (
                t
                for t in self._tasks
                if t.project_id == project_id and t.github_pr_url == github_pr_url
            ),
            None,
        )

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
        self._tasks.append(task)
        return task

    def seed(self, task: Task) -> None:
        self._tasks.append(task)


class FakeProjectRepo:
    def __init__(self) -> None:
        self._projects: dict[uuid.UUID, Project] = {}

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return self._projects.get(project_id)

    def seed(self, *, project_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self._projects[project_id] = Project(
            id=project_id,
            org_id=org_id,
            name="API",
            description=None,
            status="active",
            github_repo_url=None,
            created_by=uuid.uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


class FakeOrgRepo:
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
            role="owner",
            joined_at=datetime.now(UTC),
        )


class FakeApiClient:
    def __init__(self, issues: list[dict[str, Any]] | None = None) -> None:
        self._issues = issues or []

    async def get_authenticated_user(self, token: str) -> dict[str, Any]:
        return {"id": 4242, "login": "octocat"}

    async def list_assigned_issues(self, token: str) -> list[dict[str, Any]]:
        return self._issues


# ===========================================================================
# Fixtures
# ===========================================================================


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
def conn_repo() -> FakeConnRepo:
    return FakeConnRepo()


@pytest.fixture()
def task_repo() -> FakeTaskRepo:
    return FakeTaskRepo()


@pytest.fixture()
def project_repo(org_id: uuid.UUID, project_id: uuid.UUID) -> FakeProjectRepo:
    repo = FakeProjectRepo()
    repo.seed(project_id=project_id, org_id=org_id)
    return repo


@pytest.fixture()
def org_repo(org_id: uuid.UUID, user_id: uuid.UUID) -> FakeOrgRepo:
    repo = FakeOrgRepo()
    repo.seed(org_id, user_id)
    return repo


@pytest.fixture()
def api_client() -> FakeApiClient:
    return FakeApiClient()


@pytest.fixture()
def make_service(
    conn_repo: FakeConnRepo,
    task_repo: FakeTaskRepo,
    project_repo: FakeProjectRepo,
    org_repo: FakeOrgRepo,
) -> ServiceFactory:
    def _build(api_client: FakeApiClient) -> GitHubSyncService:
        return GitHubSyncService(
            conn_repo=conn_repo,  # type: ignore[arg-type]
            task_repo=task_repo,  # type: ignore[arg-type]
            project_repo=project_repo,  # type: ignore[arg-type]
            org_repo=org_repo,  # type: ignore[arg-type]
            cipher=TokenCipher(FERNET_KEY),
            api_client=api_client,  # type: ignore[arg-type]
        )

    return _build


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    api_client: FakeApiClient,
    make_service: ServiceFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    # use a configured Settings (webhook secret + encryption key) inside the service
    settings = Settings(
        github_webhook_secret=WEBHOOK_SECRET,
        github_token_encryption_key=FERNET_KEY,
        github_client_id="cid",
    )
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: settings)

    service = make_service(api_client)
    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


# ===========================================================================
# Route / service tests
# ===========================================================================


def test_authorize_returns_url(client: TestClient) -> None:
    response = client.post("/api/v1/integrations/github/authorize")
    assert response.status_code == 200
    assert "github.com/login/oauth/authorize" in response.json()["authorize_url"]


def test_callback_creates_connection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange(**kwargs: Any) -> OAuthTokenResult:
        return OAuthTokenResult(access_token="gho_abc", scopes="repo")

    monkeypatch.setattr(github_sync_module, "exchange_code_for_token", fake_exchange)
    response = client.get("/api/v1/integrations/github/callback?code=xyz")
    assert response.status_code == 200
    body = response.json()
    assert body["github_login"] == "octocat"
    assert "access_token" not in body  # token never exposed


def test_status_when_not_connected_returns_null(client: TestClient) -> None:
    response = client.get("/api/v1/integrations/github/status")
    assert response.status_code == 200
    assert response.json() is None


def test_status_when_connected(
    client: TestClient, conn_repo: FakeConnRepo, user_id: uuid.UUID
) -> None:
    conn_repo.seed(
        GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id="1",
            github_login="octocat",
            access_token_encrypted="enc",
            scopes="repo",
            connected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    response = client.get("/api/v1/integrations/github/status")
    assert response.status_code == 200
    assert response.json()["github_login"] == "octocat"


def test_disconnect_without_connection_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/integrations/github/disconnect")
    assert response.status_code == 404


def test_disconnect_removes_connection(
    client: TestClient, conn_repo: FakeConnRepo, user_id: uuid.UUID
) -> None:
    conn_repo.seed(
        GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id="1",
            github_login="octocat",
            access_token_encrypted="enc",
            scopes="repo",
            connected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    response = client.delete("/api/v1/integrations/github/disconnect")
    assert response.status_code == 204


def test_sync_not_connected_returns_400(
    client: TestClient, project_id: uuid.UUID
) -> None:
    response = client.post(f"/api/v1/integrations/github/sync?project_id={project_id}")
    assert response.status_code == 400


def test_sync_imports_and_dedups(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    conn_repo: FakeConnRepo,
    task_repo: FakeTaskRepo,
    project_repo: FakeProjectRepo,
    org_repo: FakeOrgRepo,
    make_service: ServiceFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(github_token_encryption_key=FERNET_KEY)
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: settings)
    cipher = TokenCipher(FERNET_KEY)
    conn_repo.seed(
        GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id="1",
            github_login="octocat",
            access_token_encrypted=cipher.encrypt("gho_abc"),
            scopes="repo",
            connected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    # one issue already imported -> should be skipped
    task_repo.seed(
        Task(
            id=uuid.uuid4(),
            project_id=project_id,
            title="existing",
            description=None,
            status="backlog",
            priority="medium",
            estimate_minutes=None,
            assignee_id=user_id,
            due_date=None,
            github_pr_url="https://gh/issues/1",
            created_by=user_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    api = FakeApiClient(
        issues=[
            {"title": "i1", "body": None, "html_url": "https://gh/issues/1"},
            {"title": "i2", "body": "b", "html_url": "https://gh/issues/2"},
        ]
    )
    service = make_service(api)

    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.post(f"/api/v1/integrations/github/sync?project_id={project_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["created"] == 1
    assert body["skipped"] == 1


def test_sync_not_member_returns_403(
    user_id: uuid.UUID,
    conn_repo: FakeConnRepo,
    project_repo: FakeProjectRepo,
    make_service: ServiceFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(github_token_encryption_key=FERNET_KEY)
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: settings)
    foreign_project = uuid.uuid4()
    project_repo.seed(project_id=foreign_project, org_id=uuid.uuid4())
    conn_repo.seed(
        GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id="1",
            github_login="octocat",
            access_token_encrypted="enc",
            scopes="repo",
            connected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    service = make_service(FakeApiClient())
    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.post(
            f"/api/v1/integrations/github/sync?project_id={foreign_project}"
        )
    assert response.status_code == 403


def test_webhook_valid_signature_returns_204(client: TestClient) -> None:
    payload = {"action": "opened"}
    body = json.dumps(payload).encode()
    sig = (
        "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    response = client.post(
        "/api/v1/integrations/github/webhooks",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "issues",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 204


def test_webhook_invalid_signature_returns_401(client: TestClient) -> None:
    body = json.dumps({"action": "opened"}).encode()
    response = client.post(
        "/api/v1/integrations/github/webhooks",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "issues",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401
