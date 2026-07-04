"""GitHub integration tests — crypto, webhooks, OAuth, connection flow, sync."""

import hashlib
import hmac
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
    create_oauth_state,
)
from devflow_api.core.integrations.github.sync import issue_to_task_fields
from devflow_api.core.integrations.github.webhooks import verify_signature
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.models.sync_run import SyncRun
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_sync import (
    GitHubSyncService,
    get_github_sync_service,
)
from devflow_api.main import create_app

# Secret key used in fixtures that exercise OAuth state generation/verification.
_TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-prod"

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
        client_id="cid",
        redirect_uri="http://cb",
        state="user:nonce",
        scopes="read:user",
    )
    assert "github.com/login/oauth/authorize" in url
    assert "client_id=cid" in url
    assert "state=user%3Anonce" in url  # URL-encoded via urlencode
    assert "scope=read%3Auser" in url


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


class FakePRRepo:
    def __init__(self) -> None:
        self._prs: dict[tuple[uuid.UUID, int], PullRequest] = {}

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        github_pr_id: int,
        github_repo_full_name: str,
        number: int,
        title: str,
        author_login: str,
        state: str,
        created_at_github: datetime,
        merged_at: datetime | None,
        closed_at: datetime | None,
        html_url: str,
        last_synced_at: datetime,
    ) -> PullRequest:
        now = datetime.now(UTC)
        pr = PullRequest(
            id=uuid.uuid4(),
            user_id=user_id,
            github_pr_id=github_pr_id,
            github_repo_full_name=github_repo_full_name,
            number=number,
            title=title,
            author_login=author_login,
            state=state,
            created_at_github=created_at_github,
            merged_at=merged_at,
            closed_at=closed_at,
            first_review_at=None,
            html_url=html_url,
            last_synced_at=last_synced_at,
            created_at=now,
            updated_at=now,
        )
        key = (user_id, github_pr_id)
        if key in self._prs:
            pr.id = self._prs[key].id
        self._prs[key] = pr
        return pr

    async def set_first_review_at(
        self, pr: PullRequest, first_review_at: datetime
    ) -> PullRequest:
        if pr.first_review_at is None:
            pr.first_review_at = first_review_at
        return pr

    @property
    def prs(self) -> list[PullRequest]:
        return list(self._prs.values())


class FakeReviewRepo:
    def __init__(self) -> None:
        self._reviews: list[PullRequestReview] = []

    async def upsert(
        self,
        *,
        pull_request_id: uuid.UUID,
        github_review_id: int,
        reviewer_login: str,
        state: str,
        submitted_at: datetime,
    ) -> PullRequestReview:
        now = datetime.now(UTC)
        review = PullRequestReview(
            id=uuid.uuid4(),
            pull_request_id=pull_request_id,
            github_review_id=github_review_id,
            reviewer_login=reviewer_login,
            state=state,
            submitted_at=submitted_at,
            created_at=now,
            updated_at=now,
        )
        self._reviews.append(review)
        return review

    @property
    def reviews(self) -> list[PullRequestReview]:
        return list(self._reviews)


class FakeSyncRunRepo:
    def __init__(self) -> None:
        self._runs: list[SyncRun] = []

    async def create(self, *, user_id: uuid.UUID) -> SyncRun:
        now = datetime.now(UTC)
        run = SyncRun(
            id=uuid.uuid4(),
            user_id=user_id,
            status="running",
            prs_synced=0,
            reviews_synced=0,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self._runs.append(run)
        return run

    async def complete(
        self, run: SyncRun, *, prs_synced: int, reviews_synced: int
    ) -> SyncRun:
        run.status = "completed"
        run.prs_synced = prs_synced
        run.reviews_synced = reviews_synced
        run.finished_at = datetime.now(UTC)
        return run

    async def fail(self, run: SyncRun, *, error_message: str) -> SyncRun:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        return run

    @property
    def runs(self) -> list[SyncRun]:
        return list(self._runs)


class FakeApiClient:
    def __init__(
        self,
        prs: list[dict[str, Any]] | None = None,
        reviews: list[dict[str, Any]] | None = None,
    ) -> None:
        self._prs = prs or []
        self._reviews = reviews or []

    async def get_authenticated_user(self, token: str) -> dict[str, Any]:
        return {"id": 4242, "login": "octocat"}

    async def list_assigned_issues(self, token: str) -> list[dict[str, Any]]:
        return self._prs

    async def list_assigned_prs(self, token: str) -> list[dict[str, Any]]:
        return self._prs

    async def list_authored_prs(self, token: str) -> list[dict[str, Any]]:
        return []

    async def list_pr_reviews(
        self, token: str, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        return self._reviews


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def conn_repo() -> FakeConnRepo:
    return FakeConnRepo()


@pytest.fixture()
def pr_repo() -> FakePRRepo:
    return FakePRRepo()


@pytest.fixture()
def review_repo() -> FakeReviewRepo:
    return FakeReviewRepo()


@pytest.fixture()
def sync_run_repo() -> FakeSyncRunRepo:
    return FakeSyncRunRepo()


@pytest.fixture()
def api_client() -> FakeApiClient:
    return FakeApiClient()


@pytest.fixture()
def make_service(
    conn_repo: FakeConnRepo,
    pr_repo: FakePRRepo,
    review_repo: FakeReviewRepo,
    sync_run_repo: FakeSyncRunRepo,
) -> ServiceFactory:
    def _build(api_client: FakeApiClient) -> GitHubSyncService:
        return GitHubSyncService(
            conn_repo=conn_repo,  # type: ignore[arg-type]
            pr_repo=pr_repo,  # type: ignore[arg-type]
            review_repo=review_repo,  # type: ignore[arg-type]
            sync_run_repo=sync_run_repo,  # type: ignore[arg-type]
            cipher=TokenCipher(FERNET_KEY),
            api_client=api_client,  # type: ignore[arg-type]
        )

    return _build


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        github_webhook_secret=WEBHOOK_SECRET,
        github_token_encryption_key=FERNET_KEY,
        github_client_id="cid",
        secret_key=_TEST_SECRET_KEY,
    )


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    api_client: FakeApiClient,
    make_service: ServiceFactory,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    # Monkeypatch get_settings in the github_sync module so the service uses
    # our known test secret key for OAuth state signing/verification.
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: test_settings)

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
    client: TestClient,
    user_id: uuid.UUID,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_exchange(**kwargs: Any) -> OAuthTokenResult:
        return OAuthTokenResult(access_token="gho_abc", scopes="repo")

    monkeypatch.setattr(github_sync_module, "exchange_code_for_token", fake_exchange)

    valid_state = create_oauth_state(user_id, secret_key=test_settings.secret_key)
    response = client.get(
        f"/api/v1/integrations/github/callback?code=xyz&state={valid_state}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["github_login"] == "octocat"
    assert "access_token" not in body  # token never exposed


def test_callback_rejects_missing_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Callback without `state` param must be rejected (422 missing required param)."""

    async def fake_exchange(**kwargs: Any) -> OAuthTokenResult:
        return OAuthTokenResult(access_token="gho_abc", scopes="repo")

    monkeypatch.setattr(github_sync_module, "exchange_code_for_token", fake_exchange)
    response = client.get("/api/v1/integrations/github/callback?code=xyz")
    assert response.status_code == 422  # state is required Query(...)


def test_callback_rejects_invalid_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Callback with a tampered or wrong-user state must be rejected (401)."""

    async def fake_exchange(**kwargs: Any) -> OAuthTokenResult:
        return OAuthTokenResult(access_token="gho_abc", scopes="repo")

    monkeypatch.setattr(github_sync_module, "exchange_code_for_token", fake_exchange)
    response = client.get(
        "/api/v1/integrations/github/callback?code=xyz&state=tampered:invalid:state:0000"
    )
    assert response.status_code == 401


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


def test_sync_not_connected_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/integrations/github/sync")
    assert response.status_code == 400


def test_sync_creates_prs_and_reviews(
    user_id: uuid.UUID,
    conn_repo: FakeConnRepo,
    pr_repo: FakePRRepo,
    review_repo: FakeReviewRepo,
    sync_run_repo: FakeSyncRunRepo,
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
    prs_data = [
        {
            "number": 42,
            "title": "Fix bug",
            "user": {"login": "octocat"},
            "state": "open",
            "created_at": "2026-06-01T10:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/owner/repo/pull/42",
            "repository_url": "https://api.github.com/repos/owner/repo",
            "pull_request": {"merged_at": None},
        }
    ]
    reviews_data = [
        {
            "id": 101,
            "user": {"login": "reviewer1"},
            "state": "APPROVED",
            "submitted_at": "2026-06-02T10:00:00Z",
        }
    ]
    api = FakeApiClient(prs=prs_data, reviews=reviews_data)
    service = make_service(api)

    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.post("/api/v1/integrations/github/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["prs_synced"] == 1
    assert body["reviews_synced"] == 1
    assert len(pr_repo.prs) == 1
    assert len(review_repo.reviews) == 1
    assert len(sync_run_repo.runs) == 1
    assert sync_run_repo.runs[0].status == "completed"


def test_status_works_without_encryption_key(
    user_id: uuid.UUID,
    conn_repo: FakeConnRepo,
    pr_repo: FakePRRepo,
    review_repo: FakeReviewRepo,
    sync_run_repo: FakeSyncRunRepo,
) -> None:
    """GET /status must return 200 even when no encryption key is configured."""
    service = GitHubSyncService(
        conn_repo=conn_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        review_repo=review_repo,  # type: ignore[arg-type]
        sync_run_repo=sync_run_repo,  # type: ignore[arg-type]
        cipher=None,
        api_client=FakeApiClient(),  # type: ignore[arg-type]
    )
    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.get("/api/v1/integrations/github/status")
    assert response.status_code == 200
    assert response.json() is None


def test_sync_without_encryption_key_returns_503(
    user_id: uuid.UUID,
    conn_repo: FakeConnRepo,
    pr_repo: FakePRRepo,
    review_repo: FakeReviewRepo,
    sync_run_repo: FakeSyncRunRepo,
) -> None:
    """POST /sync returns 503 github_not_configured when cipher is absent."""
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
    service = GitHubSyncService(
        conn_repo=conn_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        review_repo=review_repo,  # type: ignore[arg-type]
        sync_run_repo=sync_run_repo,  # type: ignore[arg-type]
        cipher=None,
        api_client=FakeApiClient(),  # type: ignore[arg-type]
    )
    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.post("/api/v1/integrations/github/sync")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "github_not_configured"


# Webhook signature handling moved to GitHubAppService — see
# test_github_app_service.py and test_github_app_routes.py.


def test_webhook_oversized_body_returns_413(client: TestClient) -> None:
    """Webhook payloads exceeding 1 MiB must be rejected before HMAC processing."""
    # 1 MiB + 1 byte triggers the Content-Length guard.
    large_body = b"x" * (1 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/integrations/github/webhooks",
        content=large_body,
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(large_body)),
        },
    )
    assert response.status_code == 413
