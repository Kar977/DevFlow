"""SyncRun repository — create and update GitHub sync run records."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.sync_run import SyncRun


class SyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: uuid.UUID) -> SyncRun:
        run = SyncRun(
            user_id=user_id,
            status="running",
            prs_synced=0,
            reviews_synced=0,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete(
        self, run: SyncRun, *, prs_synced: int, reviews_synced: int
    ) -> SyncRun:
        run.status = "completed"
        run.prs_synced = prs_synced
        run.reviews_synced = reviews_synced
        run.finished_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def fail(self, run: SyncRun, *, error_message: str) -> SyncRun:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        await self._session.flush()
        return run
