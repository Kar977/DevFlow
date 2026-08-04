"""Project repository — database access for the Project aggregate."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by: uuid.UUID,
        github_repo_url: str | None,
    ) -> Project:
        project = Project(
            org_id=org_id,
            name=name,
            description=description,
            created_by=created_by,
            github_repo_url=github_repo_url,
            status="active",
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list_for_org(
        self, org_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.org_id == org_id)
            .order_by(Project.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[Project]:
        stmt = (
            select(Project)
            .join(OrganizationMember, OrganizationMember.org_id == Project.org_id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Project.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_org(self, org_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Project).where(Project.org_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Project)
            .join(OrganizationMember, OrganizationMember.org_id == Project.org_id)
            .where(OrganizationMember.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def update(
        self,
        project: Project,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        github_repo_url: str | None = None,
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        if github_repo_url is not None:
            project.github_repo_url = github_repo_url
        await self._session.flush()
        return project

    async def archive(self, project: Project) -> None:
        project.status = "archived"
        await self._session.flush()
