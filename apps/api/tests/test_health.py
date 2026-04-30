"""Smoke tests for API startup and health endpoints."""

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
