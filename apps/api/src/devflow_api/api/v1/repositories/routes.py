"""Repository routes — org-scoped repository listing and tracking."""

import uuid

from fastapi import APIRouter, Depends, Query

from devflow_api.core.schemas.github import (
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryUpdateRequest,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_app import (
    GitHubAppService,
    get_github_app_service,
)

router = APIRouter()


@router.get(
    "",
    response_model=RepositoryListResponse,
    summary="List GitHub repositories available to an organization",
)
async def list_repositories(
    organization_id: uuid.UUID = Query(...),
    tracked: bool | None = Query(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> RepositoryListResponse:
    rows = await service.list_repositories(
        org_id=organization_id, user_id=subject.user_id, tracked=tracked
    )
    return RepositoryListResponse(
        data=[RepositoryResponse.model_validate(row) for row in rows]
    )


@router.patch(
    "/{repo_id}",
    response_model=RepositoryResponse,
    summary="Enable or disable tracking of a repository",
)
async def update_repository(
    repo_id: uuid.UUID,
    payload: RepositoryUpdateRequest,
    organization_id: uuid.UUID = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> RepositoryResponse:
    repo = await service.set_repository_tracked(
        org_id=organization_id,
        user_id=subject.user_id,
        repo_id=repo_id,
        tracked=payload.tracked,
    )
    return RepositoryResponse.model_validate(repo)
