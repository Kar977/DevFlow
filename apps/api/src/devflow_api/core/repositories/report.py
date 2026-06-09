"""Report repository — database access for the Report aggregate."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.report import Report


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        report_type: str,
        fmt: str,
    ) -> Report:
        report = Report(
            user_id=user_id,
            type=report_type,
            format=fmt,
            status="pending",
        )
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return await self._session.get(Report, report_id)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(Report).where(Report.user_id == user_id)
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def update_status(
        self,
        report: Report,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
        generated_at: datetime | None = None,
    ) -> Report:
        report.status = status
        if payload is not None:
            report.payload = payload
        if error_message is not None:
            report.error_message = error_message
        if generated_at is not None:
            report.generated_at = generated_at
        await self._session.flush()
        return report

    async def delete(self, report: Report) -> None:
        await self._session.delete(report)
        await self._session.flush()
