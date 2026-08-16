"""TaskStatusChange repository — write-only audit trail for Task.status."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.task_status_change import TaskStatusChange


class TaskStatusChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
