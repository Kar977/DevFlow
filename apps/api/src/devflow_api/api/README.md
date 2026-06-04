# API Layer

HTTP layer — route declarations, request validation, and response contracts.

## Rules

- Route handlers delegate business logic to services (`core/services/`).
- Routes **do not import** repositories or integration clients directly (enforced by `test_architecture_boundaries.py`).
- A route handler should be thin: validate input (Pydantic) → call service → return response schema.
- Every route handler is decorated with `@router.get/post/patch/delete` and includes documentation (summary, description, responses).

## Route Handler Pattern

```python
@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(
    body: CreateTaskRequest,
    session: AsyncSession = Depends(get_session),
    subject: AuthenticatedSubject = Depends(get_current_subject),
) -> TaskResponse:
    task_repo = TaskRepository(session)
    work_session_repo = WorkSessionRepository(session)
    service = TaskService(task_repo, work_session_repo)
    task = await service.create(
        title=body.title,
        created_by=subject.subject_id,
        **body.model_dump(exclude={"title"}, exclude_unset=True),
    )
    await session.commit()
    return TaskResponse.model_validate(task)
```

## Directory Structure

```
api/
└── v1/
    ├── router.py                # Main v1 router — mounts all sub-routers
    ├── auth/
    │   └── routes.py            # POST /auth/register, /auth/login, etc.
    ├── organizations/
    │   └── routes.py            # CRUD /organizations + /members
    ├── repositories/            # Handles the "Projects" domain
    │   └── routes.py            # CRUD /projects
    ├── pull_requests/           # Handles the "Tasks + Time Tracking" domain
    │   └── routes.py            # CRUD /tasks + /start, /stop, /sessions
    ├── metrics/
    │   └── routes.py            # GET /metrics/*
    ├── reports/
    │   └── routes.py            # CRUD /reports
    └── integrations/
        └── github/
            └── routes.py        # GitHub OAuth + webhook + sync
```
