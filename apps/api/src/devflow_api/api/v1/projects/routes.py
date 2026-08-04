"""Project routes — project lifecycle within organizations."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from devflow_api.core.schemas.pagination import PageMeta
from devflow_api.core.schemas.projects import (
    CreateProjectRequest,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.project import ProjectService, get_project_service

router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    body: CreateProjectRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = await service.create_project(
        org_id=body.org_id,
        user_id=subject.user_id,
        name=body.name,
        description=body.description,
        github_repo_url=body.github_repo_url,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects for the current user",
)
async def list_projects(
    org_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    projects, total = await service.list_projects(
        user_id=subject.user_id, org_id=org_id, limit=limit, offset=offset
    )
    items = [ProjectResponse.model_validate(p) for p in projects]
    return ProjectListResponse(
        data=items, meta=PageMeta(total=total, limit=limit, offset=offset)
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a single project",
)
async def get_project(
    project_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project, stats = await service.get_project_detail(
        project_id=project_id, user_id=subject.user_id
    )
    return ProjectResponse.model_validate(project).model_copy(update={"stats": stats})


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
async def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = await service.update_project(
        project_id=project_id,
        user_id=subject.user_id,
        name=body.name,
        description=body.description,
        status=body.status,
        github_repo_url=body.github_repo_url,
    )
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a project",
)
async def delete_project(
    project_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ProjectService = Depends(get_project_service),
) -> None:
    await service.archive_project(project_id=project_id, user_id=subject.user_id)
