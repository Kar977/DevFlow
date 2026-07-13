"""Task routes — task lifecycle and time tracking."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from devflow_api.core.schemas.tasks import (
    CreateTaskRequest,
    TaskListResponse,
    TaskResponse,
    UpdateTaskRequest,
    WorkSessionListResponse,
    WorkSessionResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.task import TaskService, get_task_service

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
    tasks = await service.list_tasks(
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
    return TaskListResponse(items=items, total=len(items))


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
    task = await service.update_task(
        task_id=task_id,
        user_id=subject.user_id,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        estimate_minutes=body.estimate_minutes,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        github_pr_url=body.github_pr_url,
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
    return WorkSessionListResponse(items=items, total=len(items))
