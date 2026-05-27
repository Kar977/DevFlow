# Models

SQLAlchemy ORM models — persystowany stan domeny w bazie danych.

## Zasady

- Modele reprezentują wyłącznie stan w bazie danych. Logika biznesowa należy do `services/`.
- Każdy model w osobnym pliku (`user.py`, `task.py`, etc.).
- Wszystkie modele dziedziczą po `Base` z `core/database.py`.
- Nazwy tabel: `snake_case` w liczbie mnogiej (np. `work_sessions`, `refresh_tokens`).
- Każdy model ma pola `id` (UUID), `created_at` i `updated_at` z automatycznym wypełnianiem.

## Modele do zaimplementowania

### `user.py` — tabela `users`

```python
class User(Base):
    __tablename__ = "users"

    id: UUID (primary_key, default=uuid4)
    email: str (unique, not null, indexed)
    hashed_password: str (not null)
    full_name: str | None
    avatar_url: str | None
    created_at: datetime (default=now, not null)
    updated_at: datetime (default=now, onupdate=now, not null)
```

Relacje:
- `refresh_tokens` → `RefreshToken` (one-to-many)
- `memberships` → `OrganizationMember` (one-to-many)
- `projects` → `Project` (one-to-many, created_by)
- `tasks` → `Task` (one-to-many, assignee_id)
- `work_sessions` → `WorkSession` (one-to-many)
- `reports` → `Report` (one-to-many)
- `github_connection` → `GitHubConnection` (one-to-one)

---

### `refresh_token.py` — tabela `refresh_tokens`

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: UUID (primary_key)
    user_id: UUID (FK → users.id, not null, indexed)
    token_hash: str (unique, not null)   ← SHA-256 hash tokenu
    expires_at: datetime (not null)
    revoked_at: datetime | None
    created_at: datetime (default=now)
```

Indeks: `(token_hash)` dla szybkiego wyszukiwania przy refresh.

---

### `organization.py` — tabele `organizations` + `organization_members`

```python
class Organization(Base):
    __tablename__ = "organizations"

    id: UUID (primary_key)
    name: str (not null)
    slug: str (unique, not null, indexed)  ← URL-friendly identyfikator
    description: str | None
    created_by: UUID (FK → users.id, not null)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None            ← soft delete

class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: UUID (primary_key)
    org_id: UUID (FK → organizations.id, not null)
    user_id: UUID (FK → users.id, not null)
    role: str (not null)                   ← 'owner' | 'admin' | 'member'
    joined_at: datetime (default=now)

    __table_args__ = UniqueConstraint('org_id', 'user_id')
```

---

### `project.py` — tabela `projects`

```python
class Project(Base):
    __tablename__ = "projects"

    id: UUID (primary_key)
    org_id: UUID (FK → organizations.id) | None  ← None = projekt osobisty
    name: str (not null)
    description: str | None
    status: str (not null, default='active')     ← 'active' | 'archived'
    github_repo_url: str | None
    created_by: UUID (FK → users.id, not null)
    created_at: datetime
    updated_at: datetime
```

Indeks: `(org_id)`, `(created_by)`.

---

### `task.py` — tabela `tasks`

```python
class Task(Base):
    __tablename__ = "tasks"

    id: UUID (primary_key)
    project_id: UUID (FK → projects.id) | None
    title: str (not null)
    description: str | None
    status: str (not null, default='backlog')
        # 'backlog' | 'todo' | 'in_progress' | 'review' | 'done' | 'cancelled'
    priority: str (not null, default='medium')
        # 'low' | 'medium' | 'high' | 'critical'
    estimate_minutes: int | None
    assignee_id: UUID (FK → users.id) | None
    created_by: UUID (FK → users.id, not null)
    due_date: date | None
    source: str (not null, default='manual')
        # 'manual' | 'github_pr' | 'github_issue'
    github_url: str | None
    created_at: datetime
    updated_at: datetime
```

Indeksy: `(project_id)`, `(assignee_id)`, `(status)`, `(created_by)`.

---

### `work_session.py` — tabela `work_sessions`

```python
class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: UUID (primary_key)
    task_id: UUID (FK → tasks.id, not null, indexed)
    user_id: UUID (FK → users.id, not null, indexed)
    started_at: datetime (not null)
    ended_at: datetime | None           ← None = sesja aktywna
    duration_minutes: int | None        ← wypełniane automatycznie przy stop
    created_at: datetime
```

Indeks: `(user_id, started_at)` dla agregacji czasowych w MetricsService.

**Uwaga:** W danym momencie user może mieć tylko jedną aktywną sesję (`ended_at IS NULL`). Serwis powinien to egzekwować.

---

### `report.py` — tabela `reports`

```python
class Report(Base):
    __tablename__ = "reports"

    id: UUID (primary_key)
    user_id: UUID (FK → users.id, not null, indexed)
    type: str (not null)
        # 'weekly_summary' | 'project_status' | 'productivity_overview'
    format: str (not null, default='json')
        # 'json' | 'csv' | 'pdf'
    status: str (not null, default='pending')
        # 'pending' | 'generating' | 'ready' | 'failed'
    payload: dict | None                ← JSON payload dla format='json'
    file_url: str | None                ← URL pliku dla format='csv'/'pdf'
    error_message: str | None           ← szczegóły błędu gdy status='failed'
    generated_at: datetime | None
    created_at: datetime
```

---

### `github_connection.py` — tabela `github_connections`

```python
class GitHubConnection(Base):
    __tablename__ = "github_connections"

    id: UUID (primary_key)
    user_id: UUID (FK → users.id, unique, not null)  ← jeden user = jedno połączenie
    github_user_id: int (not null)
    github_username: str (not null)
    access_token_encrypted: bytes (not null)         ← szyfrowany Fernet
    scopes: str (not null)                           ← np. "repo,read:user,read:org"
    connected_at: datetime (default=now)
    last_sync_at: datetime | None
```

## Kolejność migracji Alembic

Migracje muszą być tworzone w tej kolejności (ze względu na FK):

1. `users`
2. `refresh_tokens` (FK → users)
3. `organizations`
4. `organization_members` (FK → organizations, users)
5. `projects` (FK → organizations, users)
6. `tasks` (FK → projects, users)
7. `work_sessions` (FK → tasks, users)
8. `reports` (FK → users)
9. `github_connections` (FK → users)
