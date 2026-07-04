"""GitHubInstallation repository — database access for App installations."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.github_installation import GitHubInstallation


class GitHubInstallationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        organization_id: uuid.UUID,
        installation_id: int,
        account_login: str,
        account_type: str,
        account_avatar_url: str | None,
        repository_selection: str,
        created_by: uuid.UUID | None,
    ) -> GitHubInstallation:
        stmt = (
            insert(GitHubInstallation)
            .values(
                organization_id=organization_id,
                installation_id=installation_id,
                account_login=account_login,
                account_type=account_type,
                account_avatar_url=account_avatar_url,
                repository_selection=repository_selection,
                created_by=created_by,
            )
            .on_conflict_do_update(
                index_elements=[GitHubInstallation.installation_id],
                set_={
                    "account_login": account_login,
                    "account_type": account_type,
                    "account_avatar_url": account_avatar_url,
                    "repository_selection": repository_selection,
                },
            )
            .returning(GitHubInstallation)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, row_id: uuid.UUID) -> GitHubInstallation | None:
        stmt = select(GitHubInstallation).where(GitHubInstallation.id == row_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_installation_id(
        self, installation_id: int
    ) -> GitHubInstallation | None:
        stmt = select(GitHubInstallation).where(
            GitHubInstallation.installation_id == installation_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_org(self, org_id: uuid.UUID) -> list[GitHubInstallation]:
        stmt = (
            select(GitHubInstallation)
            .where(GitHubInstallation.organization_id == org_id)
            .order_by(GitHubInstallation.account_login)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_suspended_at(
        self, row: GitHubInstallation, suspended_at: datetime | None
    ) -> GitHubInstallation:
        row.suspended_at = suspended_at
        await self._session.flush()
        return row

    async def delete(self, row: GitHubInstallation) -> None:
        await self._session.delete(row)
        await self._session.flush()
