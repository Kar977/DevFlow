"""GitHub App auth tests — app JWT, installation tokens, install state, config."""

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from devflow_api.core.config import Settings
from devflow_api.core.integrations.github.app_auth import (
    InstallationTokenProvider,
    create_app_jwt,
)
from devflow_api.core.integrations.github.oauth import (
    create_install_state,
    verify_install_state,
)

_TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-prod"

_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY_PEM = _rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
PUBLIC_KEY_PEM = (
    _rsa_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


# ===========================================================================
# App JWT
# ===========================================================================


def test_create_app_jwt_contains_expected_claims() -> None:
    token = create_app_jwt(app_id="12345", private_key_pem=PRIVATE_KEY_PEM)
    decoded = jwt.decode(token, PUBLIC_KEY_PEM, algorithms=["RS256"])
    now = int(time.time())
    assert decoded["iss"] == "12345"
    # iat is backdated to tolerate clock skew
    assert decoded["iat"] <= now - 30
    assert now < decoded["exp"] <= now + 600


def test_create_app_jwt_requires_app_id() -> None:
    with pytest.raises(ValueError, match="not configured"):
        create_app_jwt(app_id="", private_key_pem=PRIVATE_KEY_PEM)


def test_create_app_jwt_requires_private_key() -> None:
    with pytest.raises(ValueError, match="not configured"):
        create_app_jwt(app_id="12345", private_key_pem="")


# ===========================================================================
# InstallationTokenProvider
# ===========================================================================


class FakeAppApiClient:
    def __init__(self, *, expires_in_seconds: int = 3600) -> None:
        self.calls = 0
        self._expires_in = expires_in_seconds

    async def create_installation_access_token(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        self.calls += 1
        expires_at = datetime.now(UTC) + timedelta(seconds=self._expires_in)
        return {
            "token": f"ghs_token_{installation_id}_{self.calls}",
            "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def _make_provider(api: FakeAppApiClient) -> InstallationTokenProvider:
    return InstallationTokenProvider(
        api_client=api,  # type: ignore[arg-type]
        app_id="12345",
        private_key_pem=PRIVATE_KEY_PEM,
    )


async def test_token_provider_mints_and_caches() -> None:
    api = FakeAppApiClient()
    provider = _make_provider(api)
    first = await provider.get_token(42)
    second = await provider.get_token(42)
    assert first == second
    assert api.calls == 1


async def test_token_provider_caches_per_installation() -> None:
    api = FakeAppApiClient()
    provider = _make_provider(api)
    token_a = await provider.get_token(1)
    token_b = await provider.get_token(2)
    assert token_a != token_b
    assert api.calls == 2


async def test_token_provider_refreshes_near_expiry() -> None:
    api = FakeAppApiClient(expires_in_seconds=30)
    provider = _make_provider(api)
    await provider.get_token(42)
    await provider.get_token(42)
    assert api.calls == 2


def test_token_provider_mints_decodable_app_jwt() -> None:
    provider = _make_provider(FakeAppApiClient())
    decoded = jwt.decode(provider.mint_app_jwt(), PUBLIC_KEY_PEM, algorithms=["RS256"])
    assert decoded["iss"] == "12345"


async def test_token_provider_requires_credentials() -> None:
    api = FakeAppApiClient()
    provider = InstallationTokenProvider(
        api_client=api,  # type: ignore[arg-type]
        app_id="",
        private_key_pem="",
    )
    with pytest.raises(ValueError, match="not configured"):
        await provider.get_token(42)


# ===========================================================================
# Install state (HMAC-signed, carries org + user)
# ===========================================================================


def test_install_state_roundtrip() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = create_install_state(org_id, user_id, secret_key=_TEST_SECRET_KEY)
    assert verify_install_state(state, user_id, secret_key=_TEST_SECRET_KEY) == org_id


def test_install_state_rejects_tampered_signature() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = create_install_state(org_id, user_id, secret_key=_TEST_SECRET_KEY)
    tampered = state[:-4] + ("0000" if state[-4:] != "0000" else "1111")
    with pytest.raises(ValueError, match="signature"):
        verify_install_state(tampered, user_id, secret_key=_TEST_SECRET_KEY)


def test_install_state_rejects_wrong_user() -> None:
    org_id = uuid.uuid4()
    state = create_install_state(org_id, uuid.uuid4(), secret_key=_TEST_SECRET_KEY)
    with pytest.raises(ValueError, match="user"):
        verify_install_state(state, uuid.uuid4(), secret_key=_TEST_SECRET_KEY)


def test_install_state_rejects_expired() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = create_install_state(
        org_id, user_id, secret_key=_TEST_SECRET_KEY, ttl_seconds=-1
    )
    with pytest.raises(ValueError, match="expired"):
        verify_install_state(state, user_id, secret_key=_TEST_SECRET_KEY)


def test_install_state_rejects_malformed() -> None:
    with pytest.raises(ValueError, match="format"):
        verify_install_state("not-a-state", uuid.uuid4(), secret_key=_TEST_SECRET_KEY)


# ===========================================================================
# Settings — GitHub App configuration
# ===========================================================================


def test_settings_normalize_escaped_private_key_newlines() -> None:
    settings = Settings(
        github_app_private_key="-----BEGIN\\nKEYDATA\\n-----END",
    )
    assert settings.github_app_private_key_pem == "-----BEGIN\nKEYDATA\n-----END"


def test_settings_keep_real_private_key_newlines() -> None:
    settings = Settings(
        github_app_private_key="-----BEGIN\nKEYDATA\n-----END",
    )
    assert settings.github_app_private_key_pem == "-----BEGIN\nKEYDATA\n-----END"


def test_production_requires_github_app_companions() -> None:
    with pytest.raises(ValueError, match="github_app"):
        Settings(
            environment="production",
            secret_key=_TEST_SECRET_KEY,
            allowed_hosts=["api.example.com"],
            github_app_id="12345",
        )
