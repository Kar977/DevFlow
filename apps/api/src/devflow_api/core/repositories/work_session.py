"""WorkSession repository — database access for time-tracking intervals."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.work_session import WorkSession


class WorkSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        started_at: datetime,
    ) -> WorkSession:
        session = WorkSession(task_id=task_id, user_id=user_id, started_at=started_at)
        self._session.add(session)
        await self._session.flush()
        return session

    async def get_active_for_user(self, user_id: uuid.UUID) -> WorkSession | None:
        stmt = select(WorkSession).where(
            WorkSession.user_id == user_id,
            WorkSession.ended_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, session_id: uuid.UUID) -> WorkSession | None:
        return await self._session.get(WorkSession, session_id)

    async def list_for_task(self, task_id: uuid.UUID) -> list[WorkSession]:
        stmt = (
            select(WorkSession)
            .where(WorkSession.task_id == task_id)
            .order_by(WorkSession.started_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def stop(
        self,
        session: WorkSession,
        *,
        ended_at: datetime,
        duration_minutes: int,
    ) -> WorkSession:
        session.ended_at = ended_at
        session.duration_minutes = duration_minutes
        await self._session.flush()
        return session
