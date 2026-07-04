"""GitHub App authentication — app JWTs and installation access tokens."""

import time
from datetime import UTC, datetime, timedelta

import jwt

from devflow_api.core.integrations.github.client import GitHubApiClient

# GitHub caps app JWT lifetime at 600 s; leave headroom for transit time.
_APP_JWT_TTL_SECONDS = 540
# Backdate iat to tolerate clock skew between us and GitHub.
_APP_JWT_BACKDATE_SECONDS = 60
# Re-mint installation tokens when they are about to expire.
_TOKEN_REFRESH_MARGIN_SECONDS = 60


def create_app_jwt(*, app_id: str, private_key_pem: str) -> str:
    """Return a short-lived RS256 JWT authenticating as the GitHub App."""
    if not app_id or not private_key_pem:
        raise ValueError("GitHub App credentials are not configured.")
    now = int(time.time())
    payload = {
        "iat": now - _APP_JWT_BACKDATE_SECONDS,
        "exp": now + _APP_JWT_TTL_SECONDS,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


class InstallationTokenProvider:
    """Mints and caches short-lived installation access tokens."""

    def __init__(
        self,
        *,
        api_client: GitHubApiClient,
        app_id: str,
        private_key_pem: str,
    ) -> None:
        self._api_client = api_client
        self._app_id = app_id
        self._private_key_pem = private_key_pem
        self._cache: dict[int, tuple[str, datetime]] = {}

    def mint_app_jwt(self) -> str:
        """Return a fresh app JWT for App-level API calls."""
        return create_app_jwt(
            app_id=self._app_id, private_key_pem=self._private_key_pem
        )

    async def get_token(self, installation_id: int) -> str:
        """Return a valid installation access token, minting when needed."""
        cached = self._cache.get(installation_id)
        if cached is not None:
            token, expires_at = cached
            margin = timedelta(seconds=_TOKEN_REFRESH_MARGIN_SECONDS)
            if expires_at - datetime.now(UTC) > margin:
                return token

        app_jwt = create_app_jwt(
            app_id=self._app_id, private_key_pem=self._private_key_pem
        )
        data = await self._api_client.create_installation_access_token(
            app_jwt, installation_id
        )
        token = str(data["token"])
        expires_at = datetime.fromisoformat(
            str(data["expires_at"]).replace("Z", "+00:00")
        )
        self._cache[installation_id] = (token, expires_at)
        return token
