"""OrgSyncService — syncs PRs of all tracked repositories of an organization."""

import uuid
from datetime import UTC, datetime

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.integrations.github.app_auth import InstallationTokenProvider
from devflow_api.core.integrations.github.client import GitHubApiClient
from devflow_api.core.models.repository import Repository
from devflow_api.core.models.sync_run import SyncRun
from devflow_api.core.repositories.github_installation import (
    GitHubInstallationRepository,
)
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.repositories.pull_request_review import (
    PullRequestReviewRepository,
)
from devflow_api.core.repositories.repository import RepositoryRepository
from devflow_api.core.repositories.sync_run import SyncRunRepository
from devflow_api.core.schemas.github import SyncResultResponse
from devflow_api.core.services.org_access import require_admin, require_member


class OrgSyncService:
    def __init__(
        self,
        installation_repo: GitHubInstallationRepository,
        repository_repo: RepositoryRepository,
        pr_repo: PullRequestRepository,
        review_repo: PullRequestReviewRepository,
        sync_run_repo: SyncRunRepository,
        org_repo: OrganizationRepository,
        api_client: GitHubApiClient,
        token_provider: InstallationTokenProvider,
    ) -> None:
        self._installation_repo = installation_repo
        self._repository_repo = repository_repo
        self._pr_repo = pr_repo
        self._review_repo = review_repo
        self._sync_run_repo = sync_run_repo
        self._org_repo = org_repo
        self._api_client = api_client
        self._token_provider = token_provider

    async def sync(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> SyncResultResponse:
        """Pull all PRs (every author) of the org's tracked repositories.

        Incremental: PR pages arrive sorted by ``updated`` descending, so the
        walk stops at the first PR not updated since the repo's last sync.
        """
        await require_admin(self._org_repo, org_id, user_id)
        installations = await self._installation_repo.list_for_org(org_id)
        if not installations:
            raise AppError(
                code="no_installation",
                message="No GitHub App installation is connected to this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        run = await self._sync_run_repo.create(
            organization_id=org_id, triggered_by=user_id
        )
        repos_synced = 0
        prs_synced = 0
        reviews_synced = 0
        try:
            for installation in installations:
                if installation.suspended_at is not None:
                    continue
                token = await self._token_provider.get_token(
                    installation.installation_id
                )
                tracked = await self._repository_repo.list_tracked_for_installation(
                    installation.id
                )
                for repo in tracked:
                    prs, reviews = await self._sync_repo(token, repo)
                    prs_synced += prs
                    reviews_synced += reviews
                    repos_synced += 1
        except Exception as exc:
            await self._sync_run_repo.fail(run, error_message=str(exc))
            raise
        await self._sync_run_repo.complete(
            run,
            repos_synced=repos_synced,
            prs_synced=prs_synced,
            reviews_synced=reviews_synced,
        )
        return SyncResultResponse(prs_synced=prs_synced, reviews_synced=reviews_synced)

    async def list_runs(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, limit: int = 20
    ) -> list[SyncRun]:
        await require_member(self._org_repo, org_id, user_id)
        return await self._sync_run_repo.list_for_org(org_id, limit=limit)

    async def _sync_repo(self, token: str, repo: Repository) -> tuple[int, int]:
        owner, name = repo.full_name.split("/", 1)
        pulls = await self._api_client.list_repo_pulls(token, owner, name)
        now = datetime.now(UTC)
        prs_synced = 0
        reviews_synced = 0
        for pr_data in pulls:
            updated_at = _parse_dt(str(pr_data["updated_at"]))
            if repo.last_synced_at is not None and updated_at < _ensure_aware(
                repo.last_synced_at
            ):
                break  # results are sorted by updated desc — the rest is stale
            merged_at = _parse_dt_opt(pr_data.get("merged_at"))
            pr_obj = await self._pr_repo.upsert(
                repository_id=repo.id,
                github_pr_id=int(pr_data["id"]),
                number=int(pr_data["number"]),
                title=str(pr_data.get("title", "")),
                author_login=str((pr_data.get("user") or {}).get("login", "")),
                state="merged" if merged_at else str(pr_data.get("state", "open")),
                created_at_github=_parse_dt(str(pr_data["created_at"])),
                merged_at=merged_at,
                closed_at=_parse_dt_opt(pr_data.get("closed_at")),
                html_url=str(pr_data["html_url"]),
                last_synced_at=now,
            )
            prs_synced += 1

            reviews = await self._api_client.list_pr_reviews(
                token, owner, name, int(pr_data["number"])
            )
            min_submitted: datetime | None = None
            for rev in reviews:
                submitted_at = _parse_dt(str(rev["submitted_at"]))
                await self._review_repo.upsert(
                    pull_request_id=pr_obj.id,
                    github_review_id=int(rev["id"]),
                    reviewer_login=str((rev.get("user") or {}).get("login", "")),
                    state=str(rev.get("state", "")).lower(),
                    submitted_at=submitted_at,
                )
                reviews_synced += 1
                if min_submitted is None or submitted_at < min_submitted:
                    min_submitted = submitted_at
            if min_submitted is not None:
                await self._pr_repo.set_first_review_at(pr_obj, min_submitted)
        await self._repository_repo.set_last_synced_at(repo, now)
        return prs_synced, reviews_synced


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_dt_opt(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    return _parse_dt(value)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def get_org_sync_service(
    session: AsyncSession = Depends(get_session),
) -> OrgSyncService:
    settings = get_settings()
    api_client = GitHubApiClient()
    return OrgSyncService(
        installation_repo=GitHubInstallationRepository(session),
        repository_repo=RepositoryRepository(session),
        pr_repo=PullRequestRepository(session),
        review_repo=PullRequestReviewRepository(session),
        sync_run_repo=SyncRunRepository(session),
        org_repo=OrganizationRepository(session),
        api_client=api_client,
        token_provider=InstallationTokenProvider(
            api_client=api_client,
            app_id=settings.github_app_id,
            private_key_pem=settings.github_app_private_key_pem,
        ),
    )
