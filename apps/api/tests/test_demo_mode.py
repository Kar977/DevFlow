"""Tests for the demo-mode read-only guarantee (DemoReadOnlyMiddleware)."""

import uuid

from fastapi import status
from fastapi.testclient import TestClient

from devflow_api.core.config import Settings
from devflow_api.core.errors import AppError
from devflow_api.core.services.auth import get_auth_service
from devflow_api.main import create_app


class _FakeAuthService:
    """Stands in for AuthService so login tests never touch a real database.

    Only exercises the demo-mode routing decision (was the request let
    through to the route handler at all?), not real authentication.
    """

    async def login(self, *, email: str, password: str) -> tuple[str, str]:
        raise AppError(
            code="invalid_credentials",
            message="Invalid email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


def _demo_client(**overrides: object) -> TestClient:
    settings = Settings(demo_mode=True, **overrides)  # type: ignore[arg-type]
    app = create_app(settings)
    app.dependency_overrides[get_auth_service] = lambda: _FakeAuthService()
    return TestClient(app)


def test_health_and_status_pass_through_in_demo_mode() -> None:
    """Read-only, unauthenticated endpoints stay reachable in demo mode."""
    client = _demo_client()

    assert client.get("/health").status_code == 200
    assert client.get("/api/v1").status_code == 200


def test_login_is_not_blocked_in_demo_mode() -> None:
    """POST /auth/login must reach the route handler, not the 403 guard.

    Invalid credentials still fail with the route's own error, proving the
    request was not rejected by the middleware.
    """
    client = _demo_client()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password"},
    )

    assert response.status_code != 403
    assert response.json()["error"]["code"] != "demo_read_only"


def test_refresh_and_logout_are_not_blocked_in_demo_mode() -> None:
    """POST /auth/refresh and /auth/logout must reach their route handlers."""
    client = _demo_client()

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code != 403

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code != 403


def test_register_is_blocked_in_demo_mode() -> None:
    """Registration must be rejected — every visitor shares the demo account."""
    client = _demo_client()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "a-valid-password-123"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "demo_read_only"


def test_mutating_methods_are_blocked_on_arbitrary_routes() -> None:
    """PATCH/DELETE/POST on any non-exempt route are rejected with 403."""
    client = _demo_client()

    task_id = uuid.uuid4()

    assert client.post("/api/v1/organizations", json={"name": "x"}).status_code == 403
    assert client.patch(f"/api/v1/tasks/{task_id}", json={}).status_code == 403
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 403
    assert client.post("/api/v1/metrics/trends/recompute").status_code == 403


def test_blocked_response_uses_the_standard_error_envelope() -> None:
    """The 403 body matches core.errors.error_payload's shape exactly."""
    client = _demo_client()

    response = client.post("/api/v1/organizations", json={"name": "x"})

    assert response.status_code == 403
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == "demo_read_only"
    assert body["error"]["details"] == {}


def test_similar_but_distinct_path_is_still_blocked() -> None:
    """Matching is by exact path, not by prefix — a lookalike path is blocked."""
    client = _demo_client()

    response = client.post("/api/v1/auth/login-lookalike")

    assert response.status_code in (403, 404)
    if response.status_code == 403:
        assert response.json()["error"]["code"] == "demo_read_only"


def test_no_blocking_when_demo_mode_is_disabled() -> None:
    """Outside demo mode, the middleware isn't installed and nothing is blocked
    by it — the route's own validation runs instead (422 for a missing body)."""
    client = TestClient(create_app(Settings(demo_mode=False)))

    response = client.post("/api/v1/organizations")

    assert response.status_code != 403


def test_docs_available_in_production_demo_mode() -> None:
    """Interactive docs stay enabled in demo mode even with environment=production,
    since the read-only guarantee makes the schema safe to expose."""
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="a" * 32,
        cors_origins=["https://demo.example.com"],
        allowed_hosts=["testserver"],
        demo_mode=True,
    )
    client = TestClient(create_app(settings))

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
