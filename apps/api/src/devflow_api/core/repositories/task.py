"""Task repository — database access for the Task aggregate."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.task import Task


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
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        estimate_minutes: int | None = None,
        assignee_id: uuid.UUID | None = None,
        due_date: datetime | None = None,
        github_pr_url: str | None = None,
    ) -> Task:
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if estimate_minutes is not None:
            task.estimate_minutes = estimate_minutes
        if assignee_id is not None:
            task.assignee_id = assignee_id
        if due_date is not None:
            task.due_date = due_date
        if github_pr_url is not None:
            task.github_pr_url = github_pr_url
        await self._session.flush()
        return task

    async def delete(self, task: Task) -> None:
        await self._session.delete(task)
        await self._session.flush()
