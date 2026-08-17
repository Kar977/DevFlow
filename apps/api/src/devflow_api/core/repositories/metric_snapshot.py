"""MetricSnapshot repository — database access for persisted weekly metrics.

Read methods return every captured week (across all metric keys) for one
owner from `period_from` onward, so the service can build a `dict[(key,
week), value]` in one round trip rather than one query per metric per week.
"""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
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

    async def delete_for_user(
        self, user_id: uuid.UUID, *, period_from: datetime | None = None
    ) -> int:
        """Drop this user's captured snapshots, optionally from a week on.

        The only way back from `_build_series`'s "a captured week is
        immutable" rule (see `MetricSnapshotService.recompute_user_trends`)
        — used both for a manual recompute and after a timezone change,
        since that moves the week grid itself.
        """
        stmt = delete(MetricSnapshot).where(
            MetricSnapshot.scope == "user", MetricSnapshot.user_id == user_id
        )
        if period_from is not None:
            stmt = stmt.where(MetricSnapshot.period_start >= period_from)
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        await self._session.flush()
        return int(result.rowcount or 0)

    async def delete_for_org(
        self, org_id: uuid.UUID, *, period_from: datetime | None = None
    ) -> int:
        """Org-scope counterpart to `delete_for_user`.

        Not currently wired to any route — org trends have no recompute
        endpoint (any member could force an org-wide rewrite) — but kept
        symmetric and unit-tested for when that need arises.
        """
        stmt = delete(MetricSnapshot).where(
            MetricSnapshot.scope == "org", MetricSnapshot.org_id == org_id
        )
        if period_from is not None:
            stmt = stmt.where(MetricSnapshot.period_start >= period_from)
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        await self._session.flush()
        return int(result.rowcount or 0)

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
