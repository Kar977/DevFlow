"""Repository repository — database access for GitHub repository rows."""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.repository import Repository


class RepositoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        organization_id: uuid.UUID,
        github_installation_id: uuid.UUID,
        github_repo_id: int,
        full_name: str,
        private: bool,
        default_branch: str | None,
    ) -> Repository:
        """Insert or refresh a repository row without touching ``tracked``."""
        stmt = (
            insert(Repository)
            .values(
                organization_id=organization_id,
                github_installation_id=github_installation_id,
                github_repo_id=github_repo_id,
                full_name=full_name,
                private=private,
                default_branch=default_branch,
            )
            .on_conflict_do_update(
                constraint="uq_repositories_installation_repo",
                set_={
                    "full_name": full_name,
                    "private": private,
                    "default_branch": default_branch,
                },
            )
            .returning(Repository)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_id_for_org(
        self, repo_id: uuid.UUID, org_id: uuid.UUID
    ) -> Repository | None:
        stmt = select(Repository).where(
            Repository.id == repo_id,
            Repository.organization_id == org_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_org(
        self, org_id: uuid.UUID, *, tracked: bool | None = None
    ) -> list[Repository]:
        stmt = select(Repository).where(Repository.organization_id == org_id)
        if tracked is not None:
            stmt = stmt.where(Repository.tracked == tracked)
        stmt = stmt.order_by(Repository.full_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_tracked_for_installation(
        self, github_installation_id: uuid.UUID
    ) -> list[Repository]:
        stmt = (
            select(Repository)
            .where(
                Repository.github_installation_id == github_installation_id,
                Repository.tracked.is_(True),
            )
            .order_by(Repository.full_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_tracked(self, repo: Repository, tracked: bool) -> Repository:
        repo.tracked = tracked
        await self._session.flush()
        return repo

    async def set_last_synced_at(
        self, repo: Repository, last_synced_at: datetime
    ) -> Repository:
        repo.last_synced_at = last_synced_at
        await self._session.flush()
        return repo

    async def delete_missing(
        self, github_installation_id: uuid.UUID, keep_github_repo_ids: set[int]
    ) -> int:
        stmt = delete(Repository).where(
            Repository.github_installation_id == github_installation_id,
        )
        if keep_github_repo_ids:
            stmt = stmt.where(Repository.github_repo_id.notin_(keep_github_repo_ids))
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return int(result.rowcount or 0)

    async def delete_by_github_repo_ids(
        self, github_installation_id: uuid.UUID, github_repo_ids: set[int]
    ) -> int:
        if not github_repo_ids:
            return 0
        stmt = delete(Repository).where(
            Repository.github_installation_id == github_installation_id,
            Repository.github_repo_id.in_(github_repo_ids),
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return int(result.rowcount or 0)
