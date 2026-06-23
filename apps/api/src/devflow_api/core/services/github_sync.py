"""GitHubSyncService — OAuth connection, sync, and webhook handling."""

import json
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
from devflow_api.core.integrations.github.sync import issue_to_task_fields
from devflow_api.core.integrations.github.webhooks import verify_signature
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.repositories.github_connection import (
    GitHubConnectionRepository,
)
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.repositories.task import TaskRepository
from devflow_api.core.schemas.github import SyncResultResponse


class GitHubSyncService:
    def __init__(
        self,
        conn_repo: GitHubConnectionRepository,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
        cipher: TokenCipher | None,
        api_client: GitHubApiClient,
    ) -> None:
        self._conn_repo = conn_repo
        self._task_repo = task_repo
        self._project_repo = project_repo
        self._org_repo = org_repo
        self._cipher = cipher
        self._api_client = api_client

    def _require_cipher(self) -> TokenCipher:
        """Return the cipher or raise a clean 503 when encryption is not configured."""
        if self._cipher is None:
            raise AppError(
                code="github_not_configured",
                message="GitHub integration is not configured on this server.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._cipher

    async def _require_project_access(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise AppError(
                code="not_found",
                message="Project not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await self._org_repo.get_member(project.org_id, user_id)
        if not member:
            raise AppError(
                code="forbidden",
                message="You are not a member of this project's organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    def authorize_url(self, *, user_id: uuid.UUID) -> str:
        """Return the GitHub OAuth authorization URL with a signed CSRF state token."""
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

    async def sync(
        self, *, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> SyncResultResponse:
        """Import open issues assigned to the user into the given project."""
        await self._require_project_access(project_id=project_id, user_id=user_id)
        conn = await self._conn_repo.get_by_user_id(user_id)
        if not conn:
            raise AppError(
                code="not_connected",
                message="GitHub account is not connected.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        token = self._require_cipher().decrypt(conn.access_token_encrypted)
        issues = await self._api_client.list_assigned_issues(token)

        created = 0
        skipped = 0
        for issue in issues:
            fields = issue_to_task_fields(issue)
            existing = await self._task_repo.get_by_github_pr_url(
                project_id=project_id, github_pr_url=fields["github_pr_url"]
            )
            if existing:
                skipped += 1
                continue
            await self._task_repo.create(
                project_id=project_id,
                title=fields["title"],
                description=fields["description"],
                priority="medium",
                estimate_minutes=None,
                assignee_id=user_id,
                due_date=None,
                github_pr_url=fields["github_pr_url"],
                created_by=user_id,
            )
            created += 1

        return SyncResultResponse(created=created, skipped=skipped, total=len(issues))

    async def handle_webhook(
        self,
        *,
        signature: str,
        raw_body: bytes,
    ) -> None:
        """Verify HMAC signature first, then parse and process the webhook payload.

        JSON is intentionally parsed *after* signature verification so that
        untrusted input is never deserialised before authentication.
        """
        settings = get_settings()
        if not settings.github_webhook_secret:
            raise AppError(
                code="webhook_not_configured",
                message="Webhook secret is not configured.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            verify_signature(
                payload_bytes=raw_body,
                secret=settings.github_webhook_secret,
                signature_header=signature,
            )
        except ValueError as exc:
            raise AppError(
                code="invalid_signature",
                message=str(exc),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc

        # Signature is valid — safe to parse JSON now.
        _payload: dict[str, object] = json.loads(raw_body)


def get_github_sync_service(
    session: AsyncSession = Depends(get_session),
) -> GitHubSyncService:
    settings = get_settings()
    key = settings.github_token_encryption_key
    cipher = TokenCipher(key) if key else None
    return GitHubSyncService(
        conn_repo=GitHubConnectionRepository(session),
        task_repo=TaskRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
        cipher=cipher,
        api_client=GitHubApiClient(),
    )
