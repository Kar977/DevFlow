"""MetricSnapshot repository — database access for persisted weekly metrics.

Read methods return every captured week (across all metric keys) for one
owner from `period_from` onward, so the service can build a `dict[(key,
week), value]` in one round trip rather than one query per metric per week.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.metric_snapshot import MetricSnapshot


class MetricSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, user_id: uuid.UUID, *, period_from: datetime
    ) -> list[MetricSnapshot]:
        stmt = select(MetricSnapshot).where(
            MetricSnapshot.scope == "user",
            MetricSnapshot.user_id == user_id,
            MetricSnapshot.period_start >= period_from,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_org(
        self, org_id: uuid.UUID, *, period_from: datetime
    ) -> list[MetricSnapshot]:
        stmt = select(MetricSnapshot).where(
            MetricSnapshot.scope == "org",
            MetricSnapshot.org_id == org_id,
            MetricSnapshot.period_start >= period_from,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(self, rows: list[dict[str, Any]]) -> None:
        """Insert *rows*, silently skipping any that already exist.

        ``ON CONFLICT DO NOTHING`` with no target lets Postgres pick whichever
        of the two scope-specific partial unique indexes applies to each
        row — safe under concurrent callers backfilling the same week.
        """
        if not rows:
            return
        stmt = insert(MetricSnapshot).values(rows).on_conflict_do_nothing()
        await self._session.execute(stmt)
        await self._session.flush()
