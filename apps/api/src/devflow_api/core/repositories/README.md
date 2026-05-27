# Repositories

Data Access Objects — izolacja zapytań SQLAlchemy od logiki biznesowej.

## Zasady

- Repozytorium ukrywa szczegóły SQLAlchemy przed serwisami.
- Brak logiki biznesowej — tylko budowanie zapytań i mapowanie wyników.
- Route handlery nie importują repozytoriów bezpośrednio (egzekwowane przez test `test_architecture_boundaries.py`).
- Każde repozytorium w osobnym pliku.
- `AsyncSession` wstrzykiwana przez konstruktor (dependency injection).

## Wzorzec implementacji

```python
class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.get(User, user_id)
        return result

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs: Any) -> User:
        user = User(**kwargs)
        self._session.add(user)
        await self._session.flush()   # flush zamiast commit — commit w serwisie
        return user
```

## Repozytoria do zaimplementowania

### `user.py` — `UserRepository`

```python
async def get_by_id(user_id: UUID) -> User | None
async def get_by_email(email: str) -> User | None
async def create(email, hashed_password, full_name, avatar_url) -> User
async def update(user_id: UUID, **fields) -> User
async def exists_by_email(email: str) -> bool
```

---

### `refresh_token.py` — `RefreshTokenRepository`

```python
async def create(user_id: UUID, token_hash: str, expires_at: datetime) -> RefreshToken
async def get_by_hash(token_hash: str) -> RefreshToken | None
async def revoke(token_id: UUID) -> None
async def revoke_all_for_user(user_id: UUID) -> None
async def delete_expired() -> int   ← cleanup job
```

---

### `organization.py` — `OrganizationRepository`

```python
async def create(name: str, slug: str, created_by: UUID) -> Organization
async def get_by_id(org_id: UUID) -> Organization | None
async def get_by_slug(slug: str) -> Organization | None
async def list_for_user(user_id: UUID) -> list[Organization]
async def update(org_id: UUID, **fields) -> Organization
async def soft_delete(org_id: UUID) -> None

# Members
async def add_member(org_id: UUID, user_id: UUID, role: str) -> OrganizationMember
async def get_member(org_id: UUID, user_id: UUID) -> OrganizationMember | None
async def list_members(org_id: UUID) -> list[OrganizationMember]
async def update_member_role(org_id: UUID, user_id: UUID, role: str) -> None
async def remove_member(org_id: UUID, user_id: UUID) -> None
```

---

### `project.py` — `ProjectRepository`

```python
async def create(name: str, created_by: UUID, **kwargs) -> Project
async def get_by_id(project_id: UUID) -> Project | None
async def list_for_user(
    user_id: UUID,
    org_id: UUID | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Project], int]   ← (items, total_count)
async def update(project_id: UUID, **fields) -> Project
async def archive(project_id: UUID) -> None
```

---

### `task.py` — `TaskRepository`

```python
async def create(title: str, created_by: UUID, **kwargs) -> Task
async def get_by_id(task_id: UUID) -> Task | None
async def list(
    user_id: UUID,
    project_id: UUID | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Task], int]
async def update(task_id: UUID, **fields) -> Task
async def delete(task_id: UUID) -> None

# Agregacje dla MetricsService
async def count_by_status(user_id: UUID, date_from: date, date_to: date) -> dict[str, int]
async def list_completed_by_week(user_id: UUID, weeks: int = 8) -> list[tuple[date, int]]
async def list_overdue(project_id: UUID) -> list[Task]
```

---

### `work_session.py` — `WorkSessionRepository`

```python
async def create(task_id: UUID, user_id: UUID) -> WorkSession   ← started_at=now
async def get_active(user_id: UUID) -> WorkSession | None       ← ended_at IS NULL
async def stop(session_id: UUID) -> WorkSession                 ← ustawia ended_at + duration
async def list_for_task(task_id: UUID) -> list[WorkSession]

# Agregacje dla MetricsService
async def sum_minutes_by_day(
    user_id: UUID,
    date_from: date,
    date_to: date,
) -> dict[date, int]   ← {date: total_minutes}
async def total_minutes_for_task(task_id: UUID) -> int
```

---

### `report.py` — `ReportRepository`

```python
async def create(user_id: UUID, type: str, format: str) -> Report
async def get_by_id(report_id: UUID) -> Report | None
async def list_for_user(user_id: UUID, limit: int = 20, offset: int = 0) -> tuple[list[Report], int]
async def update_status(report_id: UUID, status: str, **kwargs) -> Report
async def delete(report_id: UUID) -> None
```

---

### `github_connection.py` — `GitHubConnectionRepository`

```python
async def create(user_id: UUID, github_user_id: int, github_username: str,
                 access_token_encrypted: bytes, scopes: str) -> GitHubConnection
async def get_by_user(user_id: UUID) -> GitHubConnection | None
async def update_token(user_id: UUID, access_token_encrypted: bytes) -> None
async def update_last_sync(user_id: UUID) -> None
async def delete(user_id: UUID) -> None
```
