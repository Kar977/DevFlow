"""GitHubSyncService — the per-user GitHub identity link (OAuth).

Repo/PR data flows through the GitHub App services (``github_app``,
``org_sync``).  This service only maintains the user ↔ github_login mapping
used for member-level metric attribution.
"""

import uuid

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.integrations.github.client import GitHubApiClient
from devflow_api.core.integrations.github.crypto import TokenCipher
from devflow_api.core.integrations.github.oauth import (
    build_authorize_url,
    create_oauth_state,
    exchange_code_for_token,
    verify_oauth_state,
)
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.repositories.github_connection import (
    GitHubConnectionRepository,
)


class GitHubSyncService:
    def __init__(
        self,
        conn_repo: GitHubConnectionRepository,
        cipher: TokenCipher | None,
        api_client: GitHubApiClient,
    ) -> None:
        self._conn_repo = conn_repo
        self._cipher = cipher
        self._api_client = api_client

    def _require_cipher(self) -> TokenCipher:
        if self._cipher is None:
            raise AppError(
                code="github_not_configured",
                message="GitHub integration is not configured on this server.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._cipher

    def authorize_url(self, *, user_id: uuid.UUID) -> str:
        settings = get_settings()
        state = create_oauth_state(user_id, secret_key=settings.secret_key)
        return build_authorize_url(
            client_id=settings.github_client_id,
            redirect_uri=settings.github_redirect_uri,
            state=state,
            scopes=settings.github_oauth_scopes,
        )

    async def handle_callback(
        self, *, user_id: uuid.UUID, code: str, state: str
    ) -> GitHubConnection:
        settings = get_settings()
        try:
            verify_oauth_state(state, user_id, secret_key=settings.secret_key)
        except ValueError as exc:
            raise AppError(
                code="invalid_oauth_state",
                message=(
                    "OAuth state is invalid or expired. "
                    "Please restart the GitHub authorization flow."
                ),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc
        token_result = await exchange_code_for_token(
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            code=code,
            redirect_uri=settings.github_redirect_uri,
        )
        gh_user = await self._api_client.get_authenticated_user(
            token_result.access_token
        )
        github_user_id = str(gh_user["id"])
        github_login = str(gh_user["login"])
        encrypted = self._require_cipher().encrypt(token_result.access_token)

        existing = await self._conn_repo.get_by_user_id(user_id)
        if existing:
            return await self._conn_repo.update_token(
                existing,
                access_token_encrypted=encrypted,
                scopes=token_result.scopes,
            )
        return await self._conn_repo.create(
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            access_token_encrypted=encrypted,
            scopes=token_result.scopes,
        )

    async def get_connection_status(
        self, *, user_id: uuid.UUID
    ) -> GitHubConnection | None:
        return await self._conn_repo.get_by_user_id(user_id)

    async def disconnect(self, *, user_id: uuid.UUID) -> None:
        conn = await self._conn_repo.get_by_user_id(user_id)
        if not conn:
            raise AppError(
                code="not_found",
                message="No GitHub connection found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._conn_repo.delete(conn)


def get_github_sync_service(
    session: AsyncSession = Depends(get_session),
) -> GitHubSyncService:
    settings = get_settings()
    key = settings.github_token_encryption_key
    cipher = TokenCipher(key) if key else None
    return GitHubSyncService(
        conn_repo=GitHubConnectionRepository(session),
        cipher=cipher,
        api_client=GitHubApiClient(),
    )
