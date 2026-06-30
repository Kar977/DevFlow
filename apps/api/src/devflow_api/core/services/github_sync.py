"""GitHubSyncService — OAuth connection, sync, and webhook handling."""

import json
import uuid
from datetime import UTC, datetime

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
from devflow_api.core.integrations.github.webhooks import verify_signature
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.repositories.github_connection import (
    GitHubConnectionRepository,
)
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.repositories.pull_request_review import (
    PullRequestReviewRepository,
)
from devflow_api.core.repositories.sync_run import SyncRunRepository
from devflow_api.core.schemas.github import SyncResultResponse


class GitHubSyncService:
    def __init__(
        self,
        conn_repo: GitHubConnectionRepository,
        pr_repo: PullRequestRepository,
        review_repo: PullRequestReviewRepository,
        sync_run_repo: SyncRunRepository,
        cipher: TokenCipher | None,
        api_client: GitHubApiClient,
    ) -> None:
        self._conn_repo = conn_repo
        self._pr_repo = pr_repo
        self._review_repo = review_repo
        self._sync_run_repo = sync_run_repo
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

    async def sync(self, *, user_id: uuid.UUID) -> SyncResultResponse:
        """Fetch assigned PRs and their reviews from GitHub, upsert locally."""
        conn = await self._conn_repo.get_by_user_id(user_id)
        if not conn:
            raise AppError(
                code="not_connected",
                message="GitHub account is not connected.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        token = self._require_cipher().decrypt(conn.access_token_encrypted)
        run = await self._sync_run_repo.create(user_id=user_id)
        prs_synced = 0
        reviews_synced = 0
        try:
            prs = await self._api_client.list_assigned_prs(token)
            now = datetime.now(UTC)
            for pr_data in prs:
                owner_repo: str = pr_data["repository_url"].split("/repos/", 1)[-1]
                owner, repo = owner_repo.split("/", 1)
                pr_obj = await self._pr_repo.upsert(
                    user_id=user_id,
                    github_pr_id=int(pr_data["number"]),
                    github_repo_full_name=owner_repo,
                    number=int(pr_data["number"]),
                    title=str(pr_data.get("title", "")),
                    author_login=str(pr_data.get("user", {}).get("login", "")),
                    state=_resolve_pr_state(pr_data),
                    created_at_github=_parse_dt(str(pr_data["created_at"])),
                    merged_at=_parse_dt_opt(
                        pr_data.get("pull_request", {}).get("merged_at")
                    ),
                    closed_at=_parse_dt_opt(pr_data.get("closed_at")),
                    html_url=str(pr_data["html_url"]),
                    last_synced_at=now,
                )
                prs_synced += 1

                reviews = await self._api_client.list_pr_reviews(
                    token, owner, repo, int(pr_data["number"])
                )
                min_submitted: datetime | None = None
                for rev in reviews:
                    submitted_at = _parse_dt(str(rev["submitted_at"]))
                    await self._review_repo.upsert(
                        pull_request_id=pr_obj.id,
                        github_review_id=int(rev["id"]),
                        reviewer_login=str(rev.get("user", {}).get("login", "")),
                        state=str(rev.get("state", "")).lower(),
                        submitted_at=submitted_at,
                    )
                    reviews_synced += 1
                    if min_submitted is None or submitted_at < min_submitted:
                        min_submitted = submitted_at
                if min_submitted is not None:
                    await self._pr_repo.set_first_review_at(pr_obj, min_submitted)
        except Exception as exc:
            await self._sync_run_repo.fail(run, error_message=str(exc))
            raise
        await self._sync_run_repo.complete(
            run, prs_synced=prs_synced, reviews_synced=reviews_synced
        )
        return SyncResultResponse(prs_synced=prs_synced, reviews_synced=reviews_synced)

    async def handle_webhook(
        self,
        *,
        signature: str,
        raw_body: bytes,
    ) -> None:
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

        _payload: dict[str, object] = json.loads(raw_body)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_dt_opt(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    return _parse_dt(value)


def _resolve_pr_state(pr_data: dict[str, object]) -> str:
    pr_extra = pr_data.get("pull_request", {})
    if isinstance(pr_extra, dict) and pr_extra.get("merged_at"):
        return "merged"
    state = str(pr_data.get("state", "open"))
    return state


def get_github_sync_service(
    session: AsyncSession = Depends(get_session),
) -> GitHubSyncService:
    settings = get_settings()
    key = settings.github_token_encryption_key
    cipher = TokenCipher(key) if key else None
    return GitHubSyncService(
        conn_repo=GitHubConnectionRepository(session),
        pr_repo=PullRequestRepository(session),
        review_repo=PullRequestReviewRepository(session),
        sync_run_repo=SyncRunRepository(session),
        cipher=cipher,
        api_client=GitHubApiClient(),
    )
