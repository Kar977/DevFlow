"""Task repository — database access for the Task aggregate."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.task import Task
from devflow_api.core.unset import UNSET, Unset


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        title: str,
        description: str | None,
        priority: str,
        estimate_minutes: int | None,
        assignee_id: uuid.UUID | None,
        due_date: datetime | None,
        github_pr_url: str | None,
        created_by: uuid.UUID,
    ) -> Task:
        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            status="backlog",
            priority=priority,
            estimate_minutes=estimate_minutes,
            assignee_id=assignee_id,
            due_date=due_date,
            github_pr_url=github_pr_url,
            created_by=created_by,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
        limit: int,
        offset: int,
    ) -> list[Task]:
        stmt = select(Task).where(Task.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_project(
        self,
        project_id: uuid.UUID,
        *,
        status: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(Task).where(Task.project_id == project_id)
        )
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_github_pr_url(
        self, *, project_id: uuid.UUID, github_pr_url: str
    ) -> Task | None:
        stmt = select(Task).where(
            Task.project_id == project_id,
            Task.github_pr_url == github_pr_url,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        task: Task,
        *,
        title: str | None = None,
        description: str | None | Unset = UNSET,
        status: str | None = None,
        priority: str | None = None,
        estimate_minutes: int | None | Unset = UNSET,
        assignee_id: uuid.UUID | None | Unset = UNSET,
        due_date: datetime | None | Unset = UNSET,
        github_pr_url: str | None | Unset = UNSET,
    ) -> Task:
        if title is not None:
            task.title = title
        if not isinstance(description, Unset):
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if not isinstance(estimate_minutes, Unset):
            task.estimate_minutes = estimate_minutes
        if not isinstance(assignee_id, Unset):
            task.assignee_id = assignee_id
        if not isinstance(due_date, Unset):
            task.due_date = due_date
        if not isinstance(github_pr_url, Unset):
            task.github_pr_url = github_pr_url
        await self._session.flush()
        # `updated_at` is set by an onupdate=func.now() server-side default;
        # without a refresh the attribute stays expired and a later sync
        # attribute read (e.g. TaskResponse.model_validate) raises
        # MissingGreenlet when it tries to lazily reload it.
        await self._session.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self._session.delete(task)
        await self._session.flush()
