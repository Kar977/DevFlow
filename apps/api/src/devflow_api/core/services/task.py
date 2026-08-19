"""Task service — task lifecycle and time tracking within projects."""

import uuid
from datetime import UTC, date, datetime

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.repositories.task import TaskRepository
from devflow_api.core.repositories.task_status_change import (
    TaskStatusChangeRepository,
)
from devflow_api.core.repositories.work_session import WorkSessionRepository
from devflow_api.core.schemas.tasks import ActiveSessionResponse
from devflow_api.core.services.org_access import require_member
from devflow_api.core.services.organization_settings import (
    OrganizationSettingsService,
    get_organization_settings_service,
)
from devflow_api.core.services.period import is_sprint_start
from devflow_api.core.unset import UNSET, Unset


def _as_utc(value: datetime) -> datetime:
    """Coerce a possibly-naive datetime to aware UTC.

    Rows can come back naive depending on how they were written; elapsed-time
    math on a mix of naive/aware datetimes raises TypeError.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        work_session_repo: WorkSessionRepository,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
        status_change_repo: TaskStatusChangeRepository,
        cache: CacheBackend | None = None,
        long_running_session_hours: int = 6,
        settings_service: OrganizationSettingsService | None = None,
    ) -> None:
        self._task_repo = task_repo
        self._work_session_repo = work_session_repo
        self._project_repo = project_repo
        self._org_repo = org_repo
        self._status_change_repo = status_change_repo
        self._cache = cache
        self._long_running_session_hours = long_running_session_hours
        # Optional so existing test call sites that construct TaskService
        # directly (without an org-settings double) keep working — sprint
        # validation is simply skipped when unset, same escape hatch as
        # PRMetricsService uses for its own settings_service dependency.
        self._settings_service = settings_service

    async def _require_project_access(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> Project:
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
                message="You are not a member of this project's organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return project

    async def _get_accessible_task(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Task, Project]:
        """Return (task, project) after verifying the caller has project access."""
        task = await self._task_repo.get_by_id(task_id)
        if not task:
            raise AppError(
                code="not_found",
                message="Task not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        project = await self._require_project_access(
            project_id=task.project_id, user_id=user_id
        )
        return task, project

    async def _validate_assignee(
        self, *, assignee_id: uuid.UUID | None, org_id: uuid.UUID
    ) -> None:
        """Raise 422 when assignee_id is set but is not an org member."""
        if assignee_id is None:
            return
        member = await self._org_repo.get_member(org_id, assignee_id)
        if not member:
            raise AppError(
                code="invalid_assignee",
                message="Assignee must be a member of the project's organization.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    async def _validate_sprint_start_date(
        self, *, sprint_start_date: date | None, org_id: uuid.UUID
    ) -> None:
        """Raise 422 when sprint_start_date is set but isn't an actual sprint
        boundary under the org's current cadence.

        Never called on read — only at the point a task's sprint assignment
        is written — so a later cadence change can't turn an existing,
        already-valid assignment into a load-time error. Skipped entirely
        when no settings_service was wired in (see __init__).
        """
        if sprint_start_date is None or self._settings_service is None:
            return
        effective = await self._settings_service.get_effective(org_id)
        if effective.sprint_anchor_date is None:
            raise AppError(
                code="sprint_not_configured",
                message="This organization has no sprint cadence configured.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if not is_sprint_start(
            effective.sprint_anchor_date,
            effective.sprint_length_days,
            sprint_start_date,
        ):
            raise AppError(
                code="invalid_sprint_start",
                message=(
                    "sprint_start_date must be the first day of a sprint "
                    "under this organization's cadence."
                ),
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    async def create_task(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        description: str | None = None,
        priority: str = "medium",
        estimate_minutes: int | None = None,
        assignee_id: uuid.UUID | None = None,
        due_date: datetime | None = None,
        github_pr_url: str | None = None,
        sprint_start_date: date | None = None,
    ) -> Task:
        project = await self._require_project_access(
            project_id=project_id, user_id=user_id
        )
        await self._validate_assignee(assignee_id=assignee_id, org_id=project.org_id)
        await self._validate_sprint_start_date(
            sprint_start_date=sprint_start_date, org_id=project.org_id
        )
        created = await self._task_repo.create(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            estimate_minutes=estimate_minutes,
            assignee_id=assignee_id,
            due_date=due_date,
            github_pr_url=github_pr_url,
            created_by=user_id,
            sprint_start_date=sprint_start_date,
        )
        # Read the initial status off the created row rather than hardcoding
        # it here — it's set by TaskRepository.create, not this method.
        await self._status_change_repo.record(
            task_id=created.id,
            from_status=None,
            to_status=created.status,
            changed_by=user_id,
            changed_at=created.created_at,
        )
        return created

    async def get_task(self, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task, _project = await self._get_accessible_task(
            task_id=task_id, user_id=user_id
        )
        return task

    async def list_tasks(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
        # UNSET = no sprint filter, None = backlog only, a date = that sprint.
        sprint: date | None | Unset = UNSET,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Task, int]], int]:
        await self._require_project_access(project_id=project_id, user_id=user_id)
        tasks = await self._task_repo.list_for_project(
            project_id,
            status=status,
            assignee_id=assignee_id,
            sprint=sprint,
            limit=limit,
            offset=offset,
        )
        tracked = await self._work_session_repo.tracked_seconds_for_tasks(
            [t.id for t in tasks]
        )
        total = await self._task_repo.count_for_project(
            project_id, status=status, assignee_id=assignee_id, sprint=sprint
        )
        return [(task, tracked.get(task.id, 0)) for task in tasks], total

    async def list_overdue_tasks(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 5,
        offset: int = 0,
    ) -> tuple[list[tuple[Task, int]], int]:
        """The caller's own overdue tasks across every project in `org_id` —
        the personal feed backing the dashboard "overdue" banner."""
        await require_member(self._org_repo, org_id, user_id)
        now = datetime.now(UTC)
        tasks = await self._task_repo.list_overdue_for_user(
            user_id=user_id, org_id=org_id, now=now, limit=limit, offset=offset
        )
        tracked = await self._work_session_repo.tracked_seconds_for_tasks(
            [t.id for t in tasks]
        )
        total = await self._task_repo.count_overdue_for_user(
            user_id=user_id, org_id=org_id, now=now
        )
        return [(task, tracked.get(task.id, 0)) for task in tasks], total

    async def update_task(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
        description: str | None | Unset = UNSET,
        status: str | None = None,
        priority: str | None = None,
        estimate_minutes: int | None | Unset = UNSET,
        assignee_id: uuid.UUID | None | Unset = UNSET,
        due_date: datetime | None | Unset = UNSET,
        github_pr_url: str | None | Unset = UNSET,
        sprint_start_date: date | None | Unset = UNSET,
    ) -> Task:
        task, project = await self._get_accessible_task(
            task_id=task_id, user_id=user_id
        )
        if not isinstance(assignee_id, Unset):
            await self._validate_assignee(
                assignee_id=assignee_id, org_id=project.org_id
            )
        if not isinstance(sprint_start_date, Unset):
            await self._validate_sprint_start_date(
                sprint_start_date=sprint_start_date, org_id=project.org_id
            )
        completed_at: datetime | None | Unset = UNSET
        transition: tuple[str | None, str, datetime] | None = None
        if status is not None and status != task.status:
            changed_at = datetime.now(UTC)
            transition = (task.status, status, changed_at)
            if status == "done":
                completed_at = changed_at
            elif task.status == "done":
                completed_at = None
        updated = await self._task_repo.update(
            task,
            title=title,
            description=description,
            status=status,
            priority=priority,
            estimate_minutes=estimate_minutes,
            assignee_id=assignee_id,
            due_date=due_date,
            github_pr_url=github_pr_url,
            completed_at=completed_at,
            sprint_start_date=sprint_start_date,
        )
        if transition is not None:
            previous_status, new_status, changed_at = transition
            await self._status_change_repo.record(
                task_id=updated.id,
                from_status=previous_status,
                to_status=new_status,
                changed_by=user_id,
                changed_at=changed_at,
            )
        if status == "done" and self._cache is not None and updated.assignee_id:
            await self._cache.delete_matching(str(updated.assignee_id))
        return updated

    async def delete_task(self, *, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
        task, _project = await self._get_accessible_task(
            task_id=task_id, user_id=user_id
        )
        await self._task_repo.delete(task)

    async def start_session(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkSession:
        await self._get_accessible_task(task_id=task_id, user_id=user_id)
        active = await self._work_session_repo.get_active_for_user(user_id)
        if active is not None:
            raise AppError(
                code="session_active",
                message="You already have an active work session.",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "active_task_id": str(active.task_id),
                    "active_session_id": str(active.id),
                },
            )
        return await self._work_session_repo.create(
            task_id=task_id, user_id=user_id, started_at=datetime.now(UTC)
        )

    async def stop_session(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkSession:
        await self._get_accessible_task(task_id=task_id, user_id=user_id)
        active = await self._work_session_repo.get_active_for_user(user_id)
        if active is None or active.task_id != task_id:
            raise AppError(
                code="no_active_session",
                message="No active work session for this task.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        ended_at = datetime.now(UTC)
        started_at = _as_utc(active.started_at)
        duration_seconds = int((ended_at - started_at).total_seconds())
        stopped = await self._work_session_repo.stop(
            active, ended_at=ended_at, duration_seconds=duration_seconds
        )
        if self._cache is not None:
            await self._cache.delete_matching(str(user_id))
        return stopped

    async def list_sessions(
        self, *, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[WorkSession]:
        await self._get_accessible_task(task_id=task_id, user_id=user_id)
        return await self._work_session_repo.list_for_task(task_id)

    async def get_active_session(
        self, *, user_id: uuid.UUID
    ) -> ActiveSessionResponse | None:
        """The caller's active session, if any, with its task's title.

        No project-access check: an active session belongs to the caller by
        construction (created via `start_session`, which already enforced
        access at the time it was opened).
        """
        result = await self._work_session_repo.get_active_with_task(user_id)
        if result is None:
            return None
        session, task_title = result
        threshold_seconds = self._long_running_session_hours * 3600
        elapsed_seconds = int(
            (datetime.now(UTC) - _as_utc(session.started_at)).total_seconds()
        )
        return ActiveSessionResponse(
            id=session.id,
            task_id=session.task_id,
            task_title=task_title,
            started_at=session.started_at,
            elapsed_seconds=elapsed_seconds,
            is_long_running=elapsed_seconds >= threshold_seconds,
            long_running_threshold_seconds=threshold_seconds,
        )


def get_task_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
    settings_service: OrganizationSettingsService = Depends(
        get_organization_settings_service
    ),
) -> TaskService:
    return TaskService(
        task_repo=TaskRepository(session),
        work_session_repo=WorkSessionRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
        status_change_repo=TaskStatusChangeRepository(session),
        cache=cache,
        long_running_session_hours=get_settings().long_running_session_hours,
        settings_service=settings_service,
    )
