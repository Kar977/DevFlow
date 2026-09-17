"""Orchestrates one demo reseed: wipe, build, write, generate reports.

One transaction plus N more, not one giant one:

1. wipe *and* write every domain row built by
   :func:`~devflow_api.demo.dataset.build_dataset`, together in a single
   transaction. This runs against a live API (see
   ``devflow_api.demo.scheduler``), so the wipe must never be visible on its
   own — a reader must see either the old dataset or the new one, never an
   empty database. Postgres holds the wipe's ``ACCESS EXCLUSIVE`` lock (see
   ``wipe.wipe_all``) until this transaction commits, so concurrent readers
   simply wait rather than observing the gap.
2. one call per requested report into the real
   ``core.services.report._do_generate_report`` — which *must* run after
   step 1 is committed, because it opens its own session
   (``async_session_factory``) and only ever sees committed data.

This mirrors exactly what a real `POST /reports` request triggers, so a
seeded report's payload is never a hand-rolled guess at the schema — it is
computed by the same code a live user's report would be.
"""

import logging
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import async_session_factory
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.organization import Organization
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.organization_settings import OrganizationSettings
from devflow_api.core.models.project import Project
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.models.report import Report
from devflow_api.core.models.repository import Repository
from devflow_api.core.models.sync_run import SyncRun
from devflow_api.core.models.task import Task
from devflow_api.core.models.task_status_change import TaskStatusChange
from devflow_api.core.models.user import User
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.services.report import _do_generate_report  # noqa: PLC2701
from devflow_api.demo.dataset import DemoDataset, Row, build_dataset
from devflow_api.demo.timeline import Timeline
from devflow_api.demo.wipe import wipe_all

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 500


async def _bulk_insert(session: AsyncSession, model: type, rows: list[Row]) -> None:
    """Insert *rows* in chunks via Core ``insert()``.

    Core insert (not ORM ``add_all``) writes exactly the columns given,
    verbatim — including the explicit, backdated ``created_at``/``updated_at``
    every row carries — without SQLAlchemy's Python-side column defaults or
    ``onupdate`` triggers ever getting a chance to run.
    """
    if not rows:
        return
    for start in range(0, len(rows), _CHUNK_SIZE):
        chunk = rows[start : start + _CHUNK_SIZE]
        await session.execute(insert(model), chunk)


async def _write_dataset(session: AsyncSession, dataset: DemoDataset) -> None:
    await _bulk_insert(session, User, dataset.users)
    await _bulk_insert(session, Organization, dataset.organizations)
    await _bulk_insert(session, OrganizationMember, dataset.organization_members)
    await _bulk_insert(session, OrganizationSettings, dataset.organization_settings)
    await _bulk_insert(session, GitHubInstallation, dataset.github_installations)
    await _bulk_insert(session, GitHubConnection, dataset.github_connections)
    await _bulk_insert(session, Repository, dataset.repositories)
    await _bulk_insert(session, SyncRun, dataset.sync_runs)
    await _bulk_insert(session, Project, dataset.projects)
    await _bulk_insert(session, Task, dataset.tasks)
    await _bulk_insert(session, TaskStatusChange, dataset.task_status_changes)
    await _bulk_insert(session, WorkSession, dataset.work_sessions)
    await _bulk_insert(session, PullRequest, dataset.pull_requests)
    await _bulk_insert(session, PullRequestReview, dataset.pull_request_reviews)

    pending_reports: list[Row] = [
        {
            "id": req.id,
            "user_id": req.user_id,
            "organization_id": req.organization_id,
            "type": req.report_type,
            "format": "json",
            "status": "pending",
            "payload": None,
            "error_message": None,
            "generated_at": None,
            "created_at": req.created_at,
        }
        for req in dataset.report_requests
    ]
    await _bulk_insert(session, Report, pending_reports)
    if dataset.failed_report is not None:
        await _bulk_insert(session, Report, [dataset.failed_report])


def _row_counts(dataset: DemoDataset) -> dict[str, int]:
    return {
        "users": len(dataset.users),
        "organizations": len(dataset.organizations),
        "organization_members": len(dataset.organization_members),
        "projects": len(dataset.projects),
        "tasks": len(dataset.tasks),
        "task_status_changes": len(dataset.task_status_changes),
        "work_sessions": len(dataset.work_sessions),
        "repositories": len(dataset.repositories),
        "pull_requests": len(dataset.pull_requests),
        "pull_request_reviews": len(dataset.pull_request_reviews),
        "reports": len(dataset.report_requests) + (1 if dataset.failed_report else 0),
    }


async def run_seed(*, now: datetime | None = None) -> dict[str, int]:
    """Wipe the database and reseed it with a fresh fictional dataset.

    ``now`` is exposed only for tests exercising this end-to-end against a
    real database; production always captures the real "now".
    """
    timeline = Timeline.at(now) if now is not None else Timeline.capture()
    dataset = build_dataset(timeline)

    async with async_session_factory() as session, session.begin():
        await wipe_all(session)
        await _write_dataset(session, dataset)

    for req in dataset.report_requests:
        await _do_generate_report(
            req.id,
            user_id=req.user_id,
            report_type=req.report_type,
            date_from=None,
            date_to=None,
            project_id=req.project_id,
        )

    counts = _row_counts(dataset)
    logger.info("Demo dataset seeded: %s", counts)
    return counts
