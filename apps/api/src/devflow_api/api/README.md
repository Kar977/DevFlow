# API Layer

Warstwa HTTP — deklaracje tras, walidacja requestów i kontrakty odpowiedzi.

## Zasady

- Route handlery delegują logikę biznesową do serwisów (`core/services/`).
- Routes **nie importują** repozytoriów ani klientów integracji bezpośrednio (egzekwowane przez `test_architecture_boundaries.py`).
- Route handler powinien być cienki: walidacja wejścia (Pydantic) → wywołanie serwisu → zwrócenie response schema.
- Każdy route handler oznaczony dekoratorem `@router.get/post/patch/delete` z dokumentacją (summary, description, responses).

## Wzorzec implementacji route handlera

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

## Struktura katalogów

```
api/
└── v1/
    ├── router.py                # Główny router v1 — montuje wszystkie sub-routery
    ├── auth/
    │   └── routes.py            # POST /auth/register, /auth/login, etc.
    ├── organizations/
    │   └── routes.py            # CRUD /organizations + /members
    ├── repositories/            # Obsługuje domainę "Projects"
    │   └── routes.py            # CRUD /projects
    ├── pull_requests/           # Obsługuje domainę "Tasks + Time Tracking"
    │   └── routes.py            # CRUD /tasks + /start, /stop, /sessions
    ├── metrics/
    │   └── routes.py            # GET /metrics/*
    ├── reports/
    │   └── routes.py            # CRUD /reports
    └── integrations/
        └── github/
            └── routes.py        # GitHub OAuth + webhook + sync
```
