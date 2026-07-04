"""SyncRun repository — create and update org-level GitHub sync run records."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.sync_run import SyncRun


class SyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, organization_id: uuid.UUID, triggered_by: uuid.UUID | None
    ) -> SyncRun:
        run = SyncRun(
            organization_id=organization_id,
            triggered_by=triggered_by,
            status="running",
            repos_synced=0,
            prs_synced=0,
            reviews_synced=0,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete(
        self,
        run: SyncRun,
        *,
        repos_synced: int,
        prs_synced: int,
        reviews_synced: int,
    ) -> SyncRun:
        run.status = "completed"
        run.repos_synced = repos_synced
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

    async def list_for_org(
        self, org_id: uuid.UUID, *, limit: int = 20
    ) -> list[SyncRun]:
        stmt = (
            select(SyncRun)
            .where(SyncRun.organization_id == org_id)
            .order_by(SyncRun.started_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
