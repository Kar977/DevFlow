"""Task routes — task lifecycle and time tracking."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from devflow_api.core.schemas.pagination import PageMeta
from devflow_api.core.schemas.tasks import (
    ActiveSessionEnvelope,
    ActiveSessionResponse,
    CreateTaskRequest,
    TaskListResponse,
    TaskResponse,
    UpdateTaskRequest,
    WorkSessionListResponse,
    WorkSessionResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.task import TaskService, get_task_service
from devflow_api.core.unset import UNSET

router = APIRouter()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
async def create_task(
    body: CreateTaskRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    task = await service.create_task(
        project_id=body.project_id,
        user_id=subject.user_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        estimate_minutes=body.estimate_minutes,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        github_pr_url=body.github_pr_url,
    )
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks within a project",
)
async def list_tasks(
    project_id: uuid.UUID,
    task_status: str | None = Query(default=None, alias="status"),
    assignee_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    tasks, total = await service.list_tasks(
        project_id=project_id,
        user_id=subject.user_id,
        status=task_status,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )
    items = [
        TaskResponse.model_validate(t).model_copy(update={"tracked_seconds": secs})
        for t, secs in tasks
    ]
    return TaskListResponse(
        data=items, meta=PageMeta(total=total, limit=limit, offset=offset)
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task",
)
async def get_task(
    task_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    task = await service.get_task(task_id=task_id, user_id=subject.user_id)
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
)
async def update_task(
    task_id: uuid.UUID,
    body: UpdateTaskRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    fields = body.model_fields_set
    task = await service.update_task(
        task_id=task_id,
        user_id=subject.user_id,
        title=body.title,
        description=body.description if "description" in fields else UNSET,
        status=body.status,
        priority=body.priority,
        estimate_minutes=body.estimate_minutes
        if "estimate_minutes" in fields
        else UNSET,
        assignee_id=body.assignee_id if "assignee_id" in fields else UNSET,
        due_date=body.due_date if "due_date" in fields else UNSET,
        github_pr_url=body.github_pr_url if "github_pr_url" in fields else UNSET,
    )
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> None:
    await service.delete_task(task_id=task_id, user_id=subject.user_id)


@router.get(
    "/sessions/active",
    response_model=ActiveSessionEnvelope,
    summary="Get the caller's active work session, if any",
)
async def get_active_session(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> ActiveSessionEnvelope:
    result = await service.get_active_session(user_id=subject.user_id)
    if result is None:
        return ActiveSessionEnvelope(data=None)
    session, task_title = result
    return ActiveSessionEnvelope(
        data=ActiveSessionResponse(
            id=session.id,
            task_id=session.task_id,
            task_title=task_title,
            started_at=session.started_at,
        )
    )


@router.post(
    "/{task_id}/start",
    response_model=WorkSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a work session on a task",
)
async def start_session(
    task_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> WorkSessionResponse:
    session = await service.start_session(task_id=task_id, user_id=subject.user_id)
    return WorkSessionResponse.model_validate(session)


@router.post(
    "/{task_id}/stop",
    response_model=WorkSessionResponse,
    summary="Stop the active work session on a task",
)
async def stop_session(
    task_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> WorkSessionResponse:
    session = await service.stop_session(task_id=task_id, user_id=subject.user_id)
    return WorkSessionResponse.model_validate(session)


@router.get(
    "/{task_id}/sessions",
    response_model=WorkSessionListResponse,
    summary="List work sessions for a task",
)
async def list_sessions(
    task_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> WorkSessionListResponse:
    sessions = await service.list_sessions(task_id=task_id, user_id=subject.user_id)
    items = [WorkSessionResponse.model_validate(s) for s in sessions]
    return WorkSessionListResponse(data=items)
