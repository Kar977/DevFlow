"""Pull request routes — GitHub PR analytics."""

import uuid

from fastapi import APIRouter, Depends, Query

from devflow_api.core.schemas.pull_requests import (
    PullRequestDetailResponse,
    PullRequestListResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.pull_request import (
    PullRequestService,
    get_pull_request_service,
)

router = APIRouter()


@router.get(
    "",
    response_model=PullRequestListResponse,
    summary="List pull requests for the current user",
)
async def list_pull_requests(
    state: str | None = None,
    author_login: str | None = None,
    repo: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PullRequestService = Depends(get_pull_request_service),
) -> PullRequestListResponse:
    return await service.list_pull_requests(
        user_id=subject.user_id,
        state=state,
        author_login=author_login,
        repo=repo,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{pr_id}",
    response_model=PullRequestDetailResponse,
    summary="Get a single pull request with reviews",
)
async def get_pull_request(
    pr_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PullRequestService = Depends(get_pull_request_service),
) -> PullRequestDetailResponse:
    return await service.get_pull_request(pr_id=pr_id, user_id=subject.user_id)
