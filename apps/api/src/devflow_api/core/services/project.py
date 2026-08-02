"""Project service — project lifecycle within organizations."""

import uuid

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.project import Project
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
    ) -> None:
        self._project_repo = project_repo
        self._org_repo = org_repo

    async def _require_org_membership(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        member = await self._org_repo.get_member(org_id, user_id)
        if not member:
            raise AppError(
                code="forbidden",
                message="You are not a member of this organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    async def _get_owned_project(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> Project:
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise AppError(
                code="not_found",
                message="Project not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._require_org_membership(org_id=project.org_id, user_id=user_id)
        return project

    async def create_project(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        description: str | None = None,
        github_repo_url: str | None = None,
    ) -> Project:
        await self._require_org_membership(org_id=org_id, user_id=user_id)
        return await self._project_repo.create(
            org_id=org_id,
            name=name,
            description=description,
            created_by=user_id,
            github_repo_url=github_repo_url,
        )

    async def get_project(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> Project:
        return await self._get_owned_project(project_id=project_id, user_id=user_id)

    async def list_projects(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        if org_id is not None:
            await self._require_org_membership(org_id=org_id, user_id=user_id)
            projects = await self._project_repo.list_for_org(
                org_id, limit=limit, offset=offset
            )
            total = await self._project_repo.count_for_org(org_id)
            return projects, total
        projects = await self._project_repo.list_for_user(
            user_id, limit=limit, offset=offset
        )
        total = await self._project_repo.count_for_user(user_id)
        return projects, total

    async def update_project(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        github_repo_url: str | None = None,
    ) -> Project:
        project = await self._get_owned_project(project_id=project_id, user_id=user_id)
        return await self._project_repo.update(
            project,
            name=name,
            description=description,
            status=status,
            github_repo_url=github_repo_url,
        )

    async def archive_project(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        project = await self._get_owned_project(project_id=project_id, user_id=user_id)
        await self._project_repo.archive(project)


def get_project_service(
    session: AsyncSession = Depends(get_session),
) -> ProjectService:
    return ProjectService(
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
    )
