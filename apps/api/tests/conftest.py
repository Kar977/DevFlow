"""Shared pytest fixtures for the API test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from devflow_api.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Yield a FastAPI test client for the application."""
    with TestClient(create_app()) as test_client:
        yield test_client
