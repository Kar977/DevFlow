"""PullRequestService — query PR data for the current user."""

import uuid

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.schemas.pull_requests import (
    PullRequestDetailResponse,
    PullRequestListResponse,
    PullRequestResponse,
    RepositoryListResponse,
    RepositoryResponse,
    ReviewResponse,
)


class PullRequestService:
    def __init__(self, pr_repo: PullRequestRepository) -> None:
        self._pr_repo = pr_repo

    async def list_pull_requests(
        self,
        *,
        user_id: uuid.UUID,
        state: str | None = None,
        author_login: str | None = None,
        repo: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PullRequestListResponse:
        prs = await self._pr_repo.list_for_user(
            user_id,
            state=state,
            author_login=author_login,
            repo=repo,
            limit=limit,
            offset=offset,
        )
        total = await self._pr_repo.count_for_user(
            user_id, state=state, author_login=author_login, repo=repo
        )
        items = [PullRequestResponse.model_validate(pr) for pr in prs]
        return PullRequestListResponse(items=items, total=total)

    async def get_pull_request(
        self, *, pr_id: uuid.UUID, user_id: uuid.UUID
    ) -> PullRequestDetailResponse:
        pr = await self._pr_repo.get_by_id(pr_id, user_id)
        if pr is None:
            raise AppError(
                code="not_found",
                message="Pull request not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        reviews_orm = await self._pr_repo.list_reviews_for_pr(pr.id)
        reviews = [ReviewResponse.model_validate(r) for r in reviews_orm]
        pr_resp = PullRequestResponse.model_validate(pr)
        return PullRequestDetailResponse(**pr_resp.model_dump(), reviews=reviews)

    async def list_repositories(self, *, user_id: uuid.UUID) -> RepositoryListResponse:
        repos = await self._pr_repo.list_repos_for_user(user_id)
        items: list[RepositoryResponse] = []
        for full_name in repos:
            count = await self._pr_repo.count_for_user(user_id, repo=full_name)
            items.append(RepositoryResponse(full_name=full_name, pr_count=count))
        return RepositoryListResponse(items=items)


def get_pull_request_service(
    session: AsyncSession = Depends(get_session),
) -> PullRequestService:
    return PullRequestService(pr_repo=PullRequestRepository(session))
