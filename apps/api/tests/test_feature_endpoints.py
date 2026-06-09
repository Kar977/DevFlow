"""Tests for all planned feature status endpoints."""

import pytest
from fastapi.testclient import TestClient

PLANNED_FEATURES = [
    ("/api/v1/metrics", "metrics"),
    ("/api/v1/reports", "reports"),
    ("/api/v1/integrations/github", "github_integration"),
]


@pytest.mark.parametrize("path,feature_name", PLANNED_FEATURES)
def test_feature_endpoint_returns_200(
    client: TestClient, path: str, feature_name: str
) -> None:
    """Every planned feature endpoint should be reachable and return HTTP 200."""
    response = client.get(path)
    assert response.status_code == 200


@pytest.mark.parametrize("path,feature_name", PLANNED_FEATURES)
def test_feature_endpoint_returns_planned_status(
    client: TestClient, path: str, feature_name: str
) -> None:
    """Every planned feature endpoint should declare its status as 'planned'."""
    response = client.get(path)
    body = response.json()

    assert body["feature"] == feature_name
    assert body["status"] == "planned"


@pytest.mark.parametrize("path,feature_name", PLANNED_FEATURES)
def test_feature_endpoint_response_has_required_fields(
    client: TestClient, path: str, feature_name: str
) -> None:
    """Feature status responses must contain exactly 'feature' and 'status' keys."""
    response = client.get(path)
    body = response.json()

    assert "feature" in body
    assert "status" in body


@pytest.mark.parametrize("path,feature_name", PLANNED_FEATURES)
def test_feature_endpoint_content_type_is_json(
    client: TestClient, path: str, feature_name: str
) -> None:
    """Feature endpoints must respond with JSON content type."""
    response = client.get(path)
    assert "application/json" in response.headers["content-type"]
