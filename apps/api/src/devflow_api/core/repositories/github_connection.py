"""GitHubConnection repository — database access for GitHub OAuth links."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.github_connection import GitHubConnection


class GitHubConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        github_user_id: str,
        github_login: str,
        access_token_encrypted: str,
        scopes: str,
    ) -> GitHubConnection:
        conn = GitHubConnection(
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            access_token_encrypted=access_token_encrypted,
            scopes=scopes,
        )
        self._session.add(conn)
        await self._session.flush()
        return conn

    async def get_by_user_id(self, user_id: uuid.UUID) -> GitHubConnection | None:
        stmt = select(GitHubConnection).where(GitHubConnection.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_token(
        self,
        conn: GitHubConnection,
        *,
        access_token_encrypted: str,
        scopes: str,
    ) -> GitHubConnection:
        conn.access_token_encrypted = access_token_encrypted
        conn.scopes = scopes
        await self._session.flush()
        return conn

    async def delete(self, conn: GitHubConnection) -> None:
        await self._session.delete(conn)
        await self._session.flush()
