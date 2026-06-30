"""Repository routes — aggregated list of GitHub repos the user has PRs in."""

from fastapi import APIRouter, Depends

from devflow_api.core.schemas.pull_requests import RepositoryListResponse
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.pull_request import (
    PullRequestService,
    get_pull_request_service,
)

router = APIRouter()


@router.get(
    "",
    response_model=RepositoryListResponse,
    summary="List GitHub repositories the current user has synced PRs from",
)
async def list_repositories(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PullRequestService = Depends(get_pull_request_service),
) -> RepositoryListResponse:
    return await service.list_repositories(user_id=subject.user_id)
