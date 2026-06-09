"""Metrics repository — read-only aggregating queries over tasks/work_sessions.

The metrics domain is user-scoped and cuts across projects, so it owns its own
repository rather than reusing the per-aggregate task/work-session repos. Date
filtering and aggregation are performed in ``MetricsService``; this layer only
fetches the relevant rows.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession


class MetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tasks_for_user(self, user_id: uuid.UUID) -> list[Task]:
        """Return every task assigned to the user (all projects, all time)."""
        stmt = select(Task).where(Task.assignee_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_work_sessions_for_user(self, user_id: uuid.UUID) -> list[WorkSession]:
        """Return every work session logged by the user."""
        stmt = select(WorkSession).where(WorkSession.user_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_tasks_for_project(self, project_id: uuid.UUID) -> list[Task]:
        """Return every task belonging to the project."""
        stmt = select(Task).where(Task.project_id == project_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
