"""TaskStatusChange repository — audit trail for Task.status transitions."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.task_status_change import TaskStatusChange


class TaskStatusChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_tasks(self, task_ids: list[uuid.UUID]) -> list[TaskStatusChange]:
        """Every recorded transition for the given tasks, oldest first per task.

        Backs the cycle-time-per-stage metric (`MetricsService.get_cycle_time`)
        — the read path this table's `ix_task_status_changes_task_id_changed_at`
        index and docstring were added in anticipation of.
        """
        if not task_ids:
            return []
        stmt = (
            select(TaskStatusChange)
            .where(TaskStatusChange.task_id.in_(task_ids))
            .order_by(TaskStatusChange.task_id, TaskStatusChange.changed_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def record(
        self,
        *,
        task_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        changed_by: uuid.UUID | None,
        changed_at: datetime,
    ) -> TaskStatusChange:
        change = TaskStatusChange(
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            changed_at=changed_at,
        )
        self._session.add(change)
        await self._session.flush()
        return change
