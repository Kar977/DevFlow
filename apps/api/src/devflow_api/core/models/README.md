# Models

SQLAlchemy ORM models — persisted domain state in the database.

## Rules

- Models represent database state only. Business logic belongs in `services/`.
- Each model in its own file (`user.py`, `task.py`, etc.).
- All models inherit from `Base` in `core/database.py`.
- Table names: `snake_case` plural (e.g. `work_sessions`, `refresh_tokens`).
- Every model has `id` (UUID), `created_at`, and `updated_at` fields with automatic population.

## Models to Implement

### `user.py` — table `users`

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

Relations:
- `refresh_tokens` → `RefreshToken` (one-to-many)
- `memberships` → `OrganizationMember` (one-to-many)
- `projects` → `Project` (one-to-many, created_by)
- `tasks` → `Task` (one-to-many, assignee_id)
- `work_sessions` → `WorkSession` (one-to-many)
- `reports` → `Report` (one-to-many)
- `github_connection` → `GitHubConnection` (one-to-one)

---

### `refresh_token.py` — table `refresh_tokens`

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: UUID (primary_key)
    user_id: UUID (FK → users.id, not null, indexed)
    token_hash: str (unique, not null)   ← SHA-256 hash of the token
    expires_at: datetime (not null)
    revoked_at: datetime | None
    created_at: datetime (default=now)
```

Index on `(token_hash)` for fast lookup during refresh.

---

### `organization.py` — tables `organizations` + `organization_members`

```python
class Organization(Base):
    __tablename__ = "organizations"

    id: UUID (primary_key)
    name: str (not null)
    slug: str (unique, not null, indexed)  ← URL-friendly identifier
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

### `project.py` — table `projects`

```python
class Project(Base):
    __tablename__ = "projects"

    id: UUID (primary_key)
    org_id: UUID (FK → organizations.id) | None  ← None = personal project
    name: str (not null)
    description: str | None
    status: str (not null, default='active')     ← 'active' | 'archived'
    github_repo_url: str | None
    created_by: UUID (FK → users.id, not null)
    created_at: datetime
    updated_at: datetime
```

Indexes on `(org_id)`, `(created_by)`.

---

### `task.py` — table `tasks`

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

Indexes on `(project_id)`, `(assignee_id)`, `(status)`, `(created_by)`.

---

### `work_session.py` — table `work_sessions`

```python
class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: UUID (primary_key)
    task_id: UUID (FK → tasks.id, not null, indexed)
    user_id: UUID (FK → users.id, not null, indexed)
    started_at: datetime (not null)
    ended_at: datetime | None           ← None = active session
    duration_seconds: int | None        ← filled automatically on stop
    created_at: datetime
```

Index on `(user_id, started_at)` for time aggregations in MetricsService.

**Note:** A user can have only one active session at a time (`ended_at IS NULL`). The service must enforce this constraint.

---

### `report.py` — table `reports`

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
    payload: dict | None                ← JSON payload for format='json'
    file_url: str | None                ← file URL for format='csv'/'pdf'
    error_message: str | None           ← error details when status='failed'
    generated_at: datetime | None
    created_at: datetime
```

---

### `github_connection.py` — table `github_connections`

```python
class GitHubConnection(Base):
    __tablename__ = "github_connections"

    id: UUID (primary_key)
    user_id: UUID (FK → users.id, unique, not null)  ← one user = one connection
    github_user_id: int (not null)
    github_username: str (not null)
    access_token_encrypted: bytes (not null)         ← Fernet-encrypted
    scopes: str (not null)                           ← e.g. "repo,read:user,read:org"
    connected_at: datetime (default=now)
    last_sync_at: datetime | None
```

## Alembic Migration Order

Migrations must be created in this order (due to FK dependencies):

1. `users`
2. `refresh_tokens` (FK → users)
3. `organizations`
4. `organization_members` (FK → organizations, users)
5. `projects` (FK → organizations, users)
6. `tasks` (FK → projects, users)
7. `work_sessions` (FK → tasks, users)
8. `reports` (FK → users)
9. `github_connections` (FK → users)
