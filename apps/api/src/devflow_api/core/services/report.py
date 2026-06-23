"""Report service — report lifecycle and async generation.

Reports are created immediately as ``status="pending"`` and then generated in a
FastAPI BackgroundTask so the POST /reports endpoint can return 202 right away.

The background generator (``run_report_generation``) opens its own DB session via
``async_session_factory`` because the request-scoped session has already been
committed and closed by the time the background task runs.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import async_session_factory, get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.report import Report
from devflow_api.core.repositories.metrics import MetricsRepository
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.repositories.report import ReportRepository
from devflow_api.core.services.metrics import MetricsService

logger = logging.getLogger(__name__)

_DEFAULT_WEEKLY_DAYS = 7
_DEFAULT_OVERVIEW_DAYS = 30


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReportService:
    def __init__(
        self,
        report_repo: ReportRepository,
        project_repo: ProjectRepository | None = None,
        org_repo: OrganizationRepository | None = None,
    ) -> None:
        self._report_repo = report_repo
        self._project_repo = project_repo
        self._org_repo = org_repo

    async def _require_project_access(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Raise 404/403 if user cannot access the project.

        Only enforced when project_repo and org_repo are injected (i.e. in
        the real service, not in legacy tests that omit these repos).
        """
        if self._project_repo is None or self._org_repo is None:
            return
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise AppError(
                code="not_found",
                message="Project not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await self._org_repo.get_member(project.org_id, user_id)
        if not member:
            raise AppError(
                code="forbidden",
                message="You do not have access to this project.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    async def create_report(
        self,
        *,
        user_id: uuid.UUID,
        report_type: str,
        fmt: str,
        project_id: uuid.UUID | None,
    ) -> Report:
        if report_type == "project_status" and project_id is None:
            raise AppError(
                code="validation_error",
                message="project_id is required for project_status reports.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        # Validate project access synchronously before enqueuing background work.
        if report_type == "project_status" and project_id is not None:
            await self._require_project_access(project_id=project_id, user_id=user_id)
        return await self._report_repo.create(
            user_id=user_id,
            report_type=report_type,
            fmt=fmt,
        )

    async def get_report(
        self,
        *,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Report:
        report = await self._report_repo.get_by_id(report_id)
        if report is None:
            raise AppError(
                code="not_found",
                message="Report not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if report.user_id != user_id:
            raise AppError(
                code="forbidden",
                message="You do not have access to this report.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return report

    async def list_reports(
        self,
        *,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Report], int]:
        reports = await self._report_repo.list_for_user(
            user_id, limit=limit, offset=offset
        )
        total = await self._report_repo.count_for_user(user_id)
        return reports, total

    async def delete_report(
        self,
        *,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        report = await self.get_report(report_id=report_id, user_id=user_id)
        await self._report_repo.delete(report)


def get_report_service(
    session: AsyncSession = Depends(get_session),
) -> ReportService:
    return ReportService(
        report_repo=ReportRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
    )


# ---------------------------------------------------------------------------
# Generator protocol (enables dependency injection in tests)
# ---------------------------------------------------------------------------


@runtime_checkable
class ReportGenerator(Protocol):
    async def __call__(
        self,
        report_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        report_type: str,
        date_from: datetime | None,
        date_to: datetime | None,
        project_id: uuid.UUID | None,
    ) -> None: ...


def get_report_generator() -> ReportGenerator:
    """FastAPI dependency — returns the real report generator."""
    return run_report_generation


# ---------------------------------------------------------------------------
# Background generation
# ---------------------------------------------------------------------------


async def run_report_generation(
    report_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    report_type: str,
    date_from: datetime | None,
    date_to: datetime | None,
    project_id: uuid.UUID | None,
) -> None:
    """Generate a report in the background with its own DB session.

    Opens a fresh session (the request session is already closed by the time
    BackgroundTasks run) and flips the report status to ``ready`` or ``failed``.
    """
    async with async_session_factory() as session:
        async with session.begin():
            report_repo = ReportRepository(session)
            report = await report_repo.get_by_id(report_id)
            if report is None:
                return

            await report_repo.update_status(report, status="generating")

            metrics_service = MetricsService(
                metrics_repo=MetricsRepository(session),
                project_repo=ProjectRepository(session),
                org_repo=OrganizationRepository(session),
            )

            try:
                payload = await _generate_payload(
                    report_type,
                    user_id=user_id,
                    date_from=date_from,
                    date_to=date_to,
                    project_id=project_id,
                    metrics=metrics_service,
                )
                await report_repo.update_status(
                    report,
                    status="ready",
                    payload=payload,
                    generated_at=datetime.now(UTC),
                )
            except Exception as exc:  # noqa: BLE001
                # Log full detail server-side; store only a generic code in the
                # user-visible field to avoid leaking internal error messages.
                logger.exception("Report generation failed for report_id=%s", report_id)
                _ = exc  # referenced to satisfy linters; detail is in the log
                await report_repo.update_status(
                    report,
                    status="failed",
                    error_message="generation_failed",
                )


async def _generate_payload(
    report_type: str,
    *,
    user_id: uuid.UUID,
    date_from: datetime | None,
    date_to: datetime | None,
    project_id: uuid.UUID | None,
    metrics: MetricsService,
) -> dict[str, Any]:
    """Compute the JSON payload for the given report type."""
    if report_type == "weekly_summary":
        return await _weekly_summary(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            metrics=metrics,
        )
    if report_type == "productivity_overview":
        return await _productivity_overview(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            metrics=metrics,
        )
    if report_type == "project_status":
        assert project_id is not None, "project_id is required for project_status"
        return await _project_status(
            user_id=user_id,
            project_id=project_id,
            metrics=metrics,
        )
    raise ValueError(f"Unknown report type: {report_type}")


async def _weekly_summary(
    *,
    user_id: uuid.UUID,
    date_from: datetime | None,
    date_to: datetime | None,
    metrics: MetricsService,
) -> dict[str, Any]:
    end = date_to or datetime.now(UTC)
    start = date_from or (end - timedelta(days=_DEFAULT_WEEKLY_DAYS))

    velocity = await metrics.get_velocity(user_id=user_id, date_from=start, date_to=end)
    time_tracking = await metrics.get_time_tracking(
        user_id=user_id, date_from=start, date_to=end
    )
    completion = await metrics.get_completion_rate(
        user_id=user_id, date_from=start, date_to=end
    )

    work_days = len(time_tracking.daily)
    avg_hours = round(time_tracking.total_hours / work_days, 2) if work_days else 0.0

    return {
        "period": {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
        },
        "tasks_completed": velocity.total_done,
        "total_work_hours": time_tracking.total_hours,
        "velocity": velocity.total_done,
        "completion_rate": completion.completion_rate,
        "work_days": work_days,
        "avg_hours_per_day": avg_hours,
    }


async def _productivity_overview(
    *,
    user_id: uuid.UUID,
    date_from: datetime | None,
    date_to: datetime | None,
    metrics: MetricsService,
) -> dict[str, Any]:
    end = date_to or datetime.now(UTC)
    start = date_from or (end - timedelta(days=_DEFAULT_OVERVIEW_DAYS))

    summary = await metrics.get_summary(user_id=user_id, date_from=start, date_to=end)
    velocity = await metrics.get_velocity(user_id=user_id, date_from=start, date_to=end)
    completion = await metrics.get_completion_rate(
        user_id=user_id, date_from=start, date_to=end
    )
    accuracy = await metrics.get_estimation_accuracy(
        user_id=user_id, date_from=start, date_to=end
    )
    streaks = await metrics.get_streaks(user_id=user_id)

    return {
        "period": {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
        },
        "tasks_completed": summary.tasks_completed.value,
        "active_hours": summary.active_hours.value,
        "velocity": velocity.total_done,
        "average_per_week": velocity.average_per_week,
        "completion_rate": completion.completion_rate,
        "estimation_accuracy": {
            "sample_size": accuracy.sample_size,
            "average_ratio": accuracy.average_ratio,
            "accurate_count": accuracy.accurate_count,
        },
        "streaks": {
            "current_streak": streaks.current_streak,
            "longest_streak": streaks.longest_streak,
        },
    }


async def _project_status(
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    metrics: MetricsService,
) -> dict[str, Any]:
    result = await metrics.get_project_metrics(project_id=project_id, user_id=user_id)
    return {
        "project_id": str(result.project_id),
        "total_tasks": result.total_tasks,
        "open_tasks": result.open_tasks,
        "overdue_tasks": result.overdue_tasks,
        "overdue_rate": result.overdue_rate,
        "health": result.health,
    }
