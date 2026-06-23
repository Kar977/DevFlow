"""Tests for production fail-closed configuration validation (DF-SBP-002 / TM-006)."""

import pytest
from pydantic import ValidationError

from devflow_api.core.config import Settings


def _prod(**overrides: object) -> dict[str, object]:
    """Return a minimal valid production configuration, with optional overrides."""
    base: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "secret_key": "a" * 32,
        "cors_origins": ["https://app.example.com"],
        "allowed_hosts": ["app.example.com"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Valid production configuration passes
# ---------------------------------------------------------------------------


def test_valid_production_config_passes() -> None:
    s = Settings(**_prod())  # type: ignore[arg-type]
    assert s.environment == "production"


# ---------------------------------------------------------------------------
# debug must be False in production
# ---------------------------------------------------------------------------


def test_production_rejects_debug_true() -> None:
    with pytest.raises(ValidationError, match="debug must be False"):
        Settings(**_prod(debug=True))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# secret_key must be long and not the default
# ---------------------------------------------------------------------------


def test_production_rejects_default_secret_key() -> None:
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(
            **_prod(secret_key="changeme-dev-only-use-random-32-chars-in-prod")  # type: ignore[arg-type]
        )


def test_production_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(**_prod(secret_key="tooshort"))  # type: ignore[arg-type]


def test_production_accepts_long_custom_secret_key() -> None:
    s = Settings(**_prod(secret_key="x" * 32))  # type: ignore[arg-type]
    assert len(s.secret_key) >= 32


# ---------------------------------------------------------------------------
# GitHub secrets required when OAuth is enabled
# ---------------------------------------------------------------------------


def test_production_requires_github_secrets_when_client_id_set() -> None:
    with pytest.raises(ValidationError, match="github_client_secret"):
        Settings(
            **_prod(  # type: ignore[arg-type]
                github_client_id="some-id",
                github_client_secret="",
                github_token_encryption_key="",
            )
        )


def test_production_requires_encryption_key_when_client_id_set() -> None:
    with pytest.raises(ValidationError, match="github_token_encryption_key"):
        Settings(
            **_prod(  # type: ignore[arg-type]
                github_client_id="some-id",
                github_client_secret="some-secret",
                github_token_encryption_key="",
            )
        )


def test_production_accepts_full_github_secrets() -> None:
    s = Settings(
        **_prod(  # type: ignore[arg-type]
            github_client_id="cid",
            github_client_secret="csecret",
            github_token_encryption_key="enckey",
        )
    )
    assert s.github_client_id == "cid"


# ---------------------------------------------------------------------------
# CORS origins must not contain localhost
# ---------------------------------------------------------------------------


def test_production_rejects_localhost_cors() -> None:
    with pytest.raises(ValidationError, match="cors_origins"):
        Settings(
            **_prod(  # type: ignore[arg-type]
                cors_origins=["http://localhost:3000"]
            )
        )


def test_production_rejects_127_cors() -> None:
    with pytest.raises(ValidationError, match="cors_origins"):
        Settings(
            **_prod(  # type: ignore[arg-type]
                cors_origins=["http://127.0.0.1:8000"]
            )
        )


# ---------------------------------------------------------------------------
# allowed_hosts must be set and not wildcard in production
# ---------------------------------------------------------------------------


def test_production_rejects_empty_allowed_hosts() -> None:
    with pytest.raises(ValidationError, match="allowed_hosts"):
        Settings(**_prod(allowed_hosts=[]))  # type: ignore[arg-type]


def test_production_rejects_wildcard_allowed_hosts() -> None:
    with pytest.raises(ValidationError, match="allowed_hosts"):
        Settings(**_prod(allowed_hosts=["*"]))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Local / test environments are never restricted
# ---------------------------------------------------------------------------


def test_local_environment_allows_debug_and_defaults() -> None:
    s = Settings(environment="local", debug=True)
    assert s.debug is True
    assert s.environment == "local"


def test_test_environment_allows_debug() -> None:
    s = Settings(environment="test", debug=True)
    assert s.environment == "test"
