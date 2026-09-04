"""Smoke tests for API startup, health endpoints, and security headers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from devflow_api.main import create_app


def test_create_app_returns_fastapi_application() -> None:
    """The application factory should produce a FastAPI instance."""
    assert isinstance(create_app(), FastAPI)


def test_health_returns_ok(client: TestClient) -> None:
    """The health endpoint should be available without authentication."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "local"}


def test_api_v1_router_is_mounted(client: TestClient) -> None:
    """The versioned API router should be mounted at the configured prefix."""
    response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json() == {"version": "v1", "status": "ready"}


def test_security_headers_present_on_health(client: TestClient) -> None:
    """Every API response should carry the baseline security headers."""
    response = client.get("/health")

    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers.get(
        "content-security-policy", ""
    )


def test_docs_available_in_local_environment(client: TestClient) -> None:
    """Interactive docs should be accessible in local/dev environments."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_health_exempt_from_trusted_host_check() -> None:
    """/health must stay reachable even when the request Host doesn't match
    allowed_hosts, mirroring Render's internal health-check prober."""
    from devflow_api.core.config import Settings

    prod_settings = Settings(
        environment="production",
        debug=False,
        secret_key="a" * 32,
        cors_origins=["https://app.example.com"],
        allowed_hosts=["api.example.com"],
    )
    prod_client = TestClient(create_app(prod_settings))

    assert prod_client.get("/health").status_code == 200
    assert prod_client.get("/api/v1").status_code == 400


def test_docs_disabled_in_production() -> None:
    """Interactive docs must be unavailable when environment=production."""
    from devflow_api.core.config import Settings

    # "testserver" matches the default TestClient host so TrustedHostMiddleware passes.
    prod_settings = Settings(
        environment="production",
        debug=False,
        secret_key="a" * 32,
        cors_origins=["https://app.example.com"],
        allowed_hosts=["testserver"],
    )
    prod_app = create_app(prod_settings)
    prod_client = TestClient(prod_app)
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/redoc").status_code == 404
    assert prod_client.get("/openapi.json").status_code == 404
