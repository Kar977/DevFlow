"""PullRequestService — query org-scoped PR analytics data."""

import uuid

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.repositories.repository import RepositoryRepository
from devflow_api.core.schemas.pull_requests import (
    PullRequestDetailResponse,
    PullRequestListResponse,
    PullRequestResponse,
    ReviewResponse,
)
from devflow_api.core.services.org_access import require_member


class PullRequestService:
    def __init__(
        self,
        pr_repo: PullRequestRepository,
        repository_repo: RepositoryRepository,
        org_repo: OrganizationRepository,
    ) -> None:
        self._pr_repo = pr_repo
        self._repository_repo = repository_repo
        self._org_repo = org_repo

    async def list_pull_requests(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        repository_id: uuid.UUID | None = None,
        state: str | None = None,
        author_login: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PullRequestListResponse:
        await require_member(self._org_repo, org_id, user_id)
        prs = await self._pr_repo.list_for_org(
            org_id,
            repository_id=repository_id,
            state=state,
            author_login=author_login,
            limit=limit,
            offset=offset,
        )
        total = await self._pr_repo.count_for_org(
            org_id,
            repository_id=repository_id,
            state=state,
            author_login=author_login,
        )
        name_map = await self._repository_names(org_id)
        items = [self._to_response(pr, name_map) for pr in prs]
        return PullRequestListResponse(items=items, total=total)

    async def get_pull_request(
        self, *, pr_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> PullRequestDetailResponse:
        await require_member(self._org_repo, org_id, user_id)
        pr = await self._pr_repo.get_by_id_for_org(pr_id, org_id)
        if pr is None:
            raise AppError(
                code="not_found",
                message="Pull request not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        reviews_orm = await self._pr_repo.list_reviews_for_pr(pr.id)
        reviews = [ReviewResponse.model_validate(r) for r in reviews_orm]
        name_map = await self._repository_names(org_id)
        pr_resp = self._to_response(pr, name_map)
        return PullRequestDetailResponse(**pr_resp.model_dump(), reviews=reviews)

    async def _repository_names(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        repos = await self._repository_repo.list_for_org(org_id)
        return {repo.id: repo.full_name for repo in repos}

    @staticmethod
    def _to_response(
        pr: PullRequest, name_map: dict[uuid.UUID, str]
    ) -> PullRequestResponse:
        return PullRequestResponse(
            id=pr.id,
            repository_id=pr.repository_id,
            repository_full_name=name_map.get(pr.repository_id, ""),
            github_pr_id=pr.github_pr_id,
            number=pr.number,
            title=pr.title,
            author_login=pr.author_login,
            state=pr.state,
            created_at_github=pr.created_at_github,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            first_review_at=pr.first_review_at,
            html_url=pr.html_url,
            last_synced_at=pr.last_synced_at,
        )


def get_pull_request_service(
    session: AsyncSession = Depends(get_session),
) -> PullRequestService:
    return PullRequestService(
        pr_repo=PullRequestRepository(session),
        repository_repo=RepositoryRepository(session),
        org_repo=OrganizationRepository(session),
    )
