"""Task routes — task lifecycle and time tracking."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from devflow_api.core.schemas.pagination import PageMeta
from devflow_api.core.schemas.tasks import (
    ActiveSessionEnvelope,
    CreateTaskRequest,
    TaskListResponse,
    TaskResponse,
    UpdateTaskRequest,
    WorkSessionListResponse,
    WorkSessionResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.task import TaskService, get_task_service
from devflow_api.core.unset import UNSET, Unset

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
        sprint_start_date=body.sprint_start_date,
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
    sprint_start_date: date | None = Query(default=None),
    backlog_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    # UNSET = no sprint filter (neither query param given); backlog_only
    # wins over sprint_start_date if a caller sends both.
    sprint: date | None | Unset = UNSET
    if backlog_only:
        sprint = None
    elif sprint_start_date is not None:
        sprint = sprint_start_date
    tasks, total = await service.list_tasks(
        project_id=project_id,
        user_id=subject.user_id,
        status=task_status,
        assignee_id=assignee_id,
        sprint=sprint,
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
    "/overdue",
    response_model=TaskListResponse,
    summary="List the caller's overdue tasks across an organization",
)
async def list_overdue_tasks(
    organization_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    tasks, total = await service.list_overdue_tasks(
        org_id=organization_id,
        user_id=subject.user_id,
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


# NOTE: this route MUST stay declared above `/{task_id}` below. FastAPI
# matches path operations in declaration order, and a single-segment static
# path like `/overdue` would otherwise be swallowed by `/{task_id}` — the
# request would try to parse "overdue" as a UUID and 422 instead of running
# this handler. (Contrast with `/sessions/active` further down, which is
# safe because it has two segments.)
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
        sprint_start_date=body.sprint_start_date
        if "sprint_start_date" in fields
        else UNSET,
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
    return ActiveSessionEnvelope(data=result)


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
