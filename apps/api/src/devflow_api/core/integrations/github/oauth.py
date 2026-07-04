"""GitHub OAuth App flow — authorization URL, state helpers, and code→token exchange."""

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

# OAuth state TTL in seconds (10 minutes is generous for a human authorization flow).
_STATE_TTL_SECONDS = 600
_STATE_SEP = ":"


def create_oauth_state(user_id: uuid.UUID, *, secret_key: str) -> str:
    """Return a signed, tamper-evident OAuth state token.

    Format (plain, before signing):  ``<user_id>:<nonce>:<exp_ts>``
    Final token:                      ``<user_id>:<nonce>:<exp_ts>:<hmac_hex>``

    The HMAC is computed over ``user_id:nonce:exp_ts`` using ``secret_key``.
    """
    nonce = secrets.token_urlsafe(16)
    exp_ts = str(int(time.time()) + _STATE_TTL_SECONDS)
    payload = _STATE_SEP.join([str(user_id), nonce, exp_ts])
    sig = _sign_state(payload, secret_key)
    return f"{payload}{_STATE_SEP}{sig}"


def verify_oauth_state(
    state: str, expected_user_id: uuid.UUID, *, secret_key: str
) -> None:
    """Raise ``ValueError`` when the state is invalid, expired, or wrong user.

    Does *not* consume the state (stateless design — replay within the TTL
    window is possible; use DB-backed single-use tokens for stronger protection).
    """
    parts = state.split(_STATE_SEP)
    if len(parts) != 4:  # noqa: PLR2004
        raise ValueError("Invalid OAuth state format.")

    user_id_str, _nonce, exp_ts_str, received_sig = parts
    payload = _STATE_SEP.join([user_id_str, _nonce, exp_ts_str])

    expected_sig = _sign_state(payload, secret_key)
    if not hmac.compare_digest(expected_sig, received_sig):
        raise ValueError("OAuth state signature is invalid.")

    try:
        exp_ts = int(exp_ts_str)
    except ValueError as exc:
        raise ValueError("OAuth state expiry timestamp is malformed.") from exc

    if time.time() > exp_ts:
        raise ValueError("OAuth state has expired.")

    if user_id_str != str(expected_user_id):
        raise ValueError("OAuth state user mismatch.")


def _sign_state(payload: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


_INSTALL_STATE_PREFIX = "install"
_INSTALL_STATE_PARTS = 6


def create_install_state(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    secret_key: str,
    ttl_seconds: int = _STATE_TTL_SECONDS,
) -> str:
    """Return a signed state token for the GitHub App installation flow.

    Format: ``install:<org_id>:<user_id>:<nonce>:<exp_ts>:<hmac_hex>``.
    Carries the DevFlow organization the installation should be linked to.
    """
    nonce = secrets.token_urlsafe(16)
    exp_ts = str(int(time.time()) + ttl_seconds)
    payload = _STATE_SEP.join(
        [_INSTALL_STATE_PREFIX, str(org_id), str(user_id), nonce, exp_ts]
    )
    sig = _sign_state(payload, secret_key)
    return f"{payload}{_STATE_SEP}{sig}"


def verify_install_state(
    state: str, expected_user_id: uuid.UUID, *, secret_key: str
) -> uuid.UUID:
    """Validate an install state and return the organization id it carries.

    Raises ``ValueError`` when the state is malformed, tampered, expired,
    or was issued to a different user.
    """
    parts = state.split(_STATE_SEP)
    if len(parts) != _INSTALL_STATE_PARTS or parts[0] != _INSTALL_STATE_PREFIX:
        raise ValueError("Invalid install state format.")

    _prefix, org_id_str, user_id_str, _nonce, exp_ts_str, received_sig = parts
    payload = _STATE_SEP.join(parts[:-1])

    expected_sig = _sign_state(payload, secret_key)
    if not hmac.compare_digest(expected_sig, received_sig):
        raise ValueError("Install state signature is invalid.")

    try:
        exp_ts = int(exp_ts_str)
    except ValueError as exc:
        raise ValueError("Install state expiry timestamp is malformed.") from exc

    if time.time() > exp_ts:
        raise ValueError("Install state has expired.")

    if user_id_str != str(expected_user_id):
        raise ValueError("Install state user mismatch.")

    try:
        return uuid.UUID(org_id_str)
    except ValueError as exc:
        raise ValueError("Install state organization id is malformed.") from exc


@dataclass(frozen=True)
class OAuthTokenResult:
    access_token: str
    scopes: str


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str, scopes: str
) -> str:
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
        }
    )
    return f"{GITHUB_AUTHORIZE_URL}?{params}"


async def exchange_code_for_token(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> OAuthTokenResult:
    """Exchange an OAuth authorization code for an access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
        response.raise_for_status()
        data: dict[str, object] = response.json()

    error = data.get("error")
    if error:
        description = data.get("error_description")
        raise ValueError(f"GitHub OAuth error: {error} — {description}")

    access_token = str(data["access_token"])
    scopes = str(data.get("scope", ""))
    return OAuthTokenResult(access_token=access_token, scopes=scopes)
