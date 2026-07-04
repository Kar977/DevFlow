"""GitHub identity-link tests — crypto, webhooks helpers, OAuth connection flow."""

import hashlib
import hmac
import uuid
from collections.abc import Iterator
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


class FakeApiClient:
    async def get_authenticated_user(self, token: str) -> dict[str, Any]:
        return {"id": 4242, "login": "octocat"}


def _connection(user_id: uuid.UUID) -> GitHubConnection:
    return GitHubConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        github_user_id="1",
        github_login="octocat",
        access_token_encrypted="enc",
        scopes="read:user",
        connected_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


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
    conn_repo: FakeConnRepo,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    # Monkeypatch get_settings in the github_sync module so the service uses
    # our known test secret key for OAuth state signing/verification.
    monkeypatch.setattr(github_sync_module, "get_settings", lambda: test_settings)

    service = GitHubSyncService(
        conn_repo=conn_repo,  # type: ignore[arg-type]
        cipher=TokenCipher(FERNET_KEY),
        api_client=FakeApiClient(),  # type: ignore[arg-type]
    )
    app = create_app()
    app.dependency_overrides[get_github_sync_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


# ===========================================================================
# Route / service tests — identity link
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
        return OAuthTokenResult(access_token="gho_abc", scopes="read:user")

    monkeypatch.setattr(github_sync_module, "exchange_code_for_token", fake_exchange)

    valid_state = create_oauth_state(user_id, secret_key=test_settings.secret_key)
    response = client.get(
        f"/api/v1/integrations/github/callback?code=xyz&state={valid_state}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["github_login"] == "octocat"
    assert "access_token" not in body  # token never exposed


def test_callback_rejects_missing_state(client: TestClient) -> None:
    """Callback without `state` param must be rejected (422 missing param)."""
    response = client.get("/api/v1/integrations/github/callback?code=xyz")
    assert response.status_code == 422  # state is required Query(...)


def test_callback_rejects_invalid_state(client: TestClient) -> None:
    """Callback with a tampered or wrong-user state must be rejected (401)."""
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
    conn_repo.seed(_connection(user_id))
    response = client.get("/api/v1/integrations/github/status")
    assert response.status_code == 200
    assert response.json()["github_login"] == "octocat"


def test_status_works_without_encryption_key(
    user_id: uuid.UUID, conn_repo: FakeConnRepo
) -> None:
    """GET /status must return 200 even when no encryption key is configured."""
    service = GitHubSyncService(
        conn_repo=conn_repo,  # type: ignore[arg-type]
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


def test_disconnect_without_connection_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/integrations/github/disconnect")
    assert response.status_code == 404


def test_disconnect_removes_connection(
    client: TestClient, conn_repo: FakeConnRepo, user_id: uuid.UUID
) -> None:
    conn_repo.seed(_connection(user_id))
    response = client.delete("/api/v1/integrations/github/disconnect")
    assert response.status_code == 204


# User-scoped PR sync was replaced by the org-level GitHub App sync — see
# test_org_sync.py.  Webhook handling lives in test_github_app_service.py and
# test_github_app_routes.py.


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
