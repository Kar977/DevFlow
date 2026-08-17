"""User repository — database access for the User model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        result = await self.get_by_email(email)
        return result is not None

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            avatar_url=avatar_url,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(
        self,
        user: User,
        *,
        full_name: str | None = None,
        avatar_url: str | None = None,
        timezone: str | None = None,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if timezone is not None:
            user.timezone = timezone
        await self._session.flush()
        return user
