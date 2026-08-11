"""Task service — task lifecycle and time tracking within projects."""

import uuid
from datetime import UTC, datetime

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.project import Project
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.repositories.task import TaskRepository
from devflow_api.core.repositories.work_session import WorkSessionRepository
from devflow_api.core.unset import UNSET, Unset


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        work_session_repo: WorkSessionRepository,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
        cache: CacheBackend | None = None,
    ) -> None:
        self._task_repo = task_repo
        self._work_session_repo = work_session_repo
        self._project_repo = project_repo
        self._org_repo = org_repo
        self._cache = cache

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
    ) -> Task:
        project = await self._require_project_access(
            project_id=project_id, user_id=user_id
        )
        await self._validate_assignee(assignee_id=assignee_id, org_id=project.org_id)
        return await self._task_repo.create(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            estimate_minutes=estimate_minutes,
            assignee_id=assignee_id,
            due_date=due_date,
            github_pr_url=github_pr_url,
            created_by=user_id,
        )

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
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Task, int]], int]:
        await self._require_project_access(project_id=project_id, user_id=user_id)
        tasks = await self._task_repo.list_for_project(
            project_id,
            status=status,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )
        tracked = await self._work_session_repo.tracked_seconds_for_tasks(
            [t.id for t in tasks]
        )
        total = await self._task_repo.count_for_project(
            project_id, status=status, assignee_id=assignee_id
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
    ) -> Task:
        task, project = await self._get_accessible_task(
            task_id=task_id, user_id=user_id
        )
        if not isinstance(assignee_id, Unset):
            await self._validate_assignee(
                assignee_id=assignee_id, org_id=project.org_id
            )
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
        started_at = active.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
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
    ) -> tuple[WorkSession, str] | None:
        """The caller's active session, if any, with its task's title.

        No project-access check: an active session belongs to the caller by
        construction (created via `start_session`, which already enforced
        access at the time it was opened).
        """
        return await self._work_session_repo.get_active_with_task(user_id)


def get_task_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
) -> TaskService:
    return TaskService(
        task_repo=TaskRepository(session),
        work_session_repo=WorkSessionRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
        cache=cache,
    )
