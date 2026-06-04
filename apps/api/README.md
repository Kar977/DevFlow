# DevFlow API

FastAPI backend for DevFlow Insight — a productivity and task management platform for developers.

## Development

Install dependencies and run checks from the `apps/api/` directory:

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Start the development server:

```powershell
uv run uvicorn devflow_api.main:app --reload
```

## Architecture

Layered architecture with enforced boundaries:

```
HTTP Request
    │
    ▼
Routes (api/v1/)                ← input validation, delegate to service
    │
    ▼
Services (core/services/)       ← business logic, orchestration
    │
    ▼
Repositories (core/repositories/) ← data access
    │
    ▼
Models (core/models/)           ← SQLAlchemy ORM, persisted state
    │
    ▼
PostgreSQL
```

**Rule:** Routes do not import Repositories directly. Services do not know about FastAPI.

## Data Models

### User

```
id: UUID (PK)
email: str (unique)
hashed_password: str
full_name: str | None
avatar_url: str | None
created_at: datetime
updated_at: datetime
```

### RefreshToken

```
id: UUID (PK)
user_id: UUID (FK → users)
token_hash: str (unique)
expires_at: datetime
revoked_at: datetime | None
created_at: datetime
```

### Organization

```
id: UUID (PK)
name: str
slug: str (unique)
description: str | None
created_by: UUID (FK → users)
created_at: datetime
updated_at: datetime
```

### OrganizationMember

```
id: UUID (PK)
org_id: UUID (FK → organizations)
user_id: UUID (FK → users)
role: Enum('owner', 'admin', 'member')
joined_at: datetime
```

### Project

```
id: UUID (PK)
org_id: UUID (FK → organizations) | None
name: str
description: str | None
status: Enum('active', 'archived')
github_repo_url: str | None
created_by: UUID (FK → users)
created_at: datetime
updated_at: datetime
```

### Task

```
id: UUID (PK)
project_id: UUID (FK → projects) | None
title: str
description: str | None
status: Enum('backlog', 'todo', 'in_progress', 'review', 'done', 'cancelled')
priority: Enum('low', 'medium', 'high', 'critical')
estimate_minutes: int | None
assignee_id: UUID (FK → users) | None
created_by: UUID (FK → users)
due_date: date | None
source: Enum('manual', 'github_pr', 'github_issue')
github_url: str | None
created_at: datetime
updated_at: datetime
```

### WorkSession

```
id: UUID (PK)
task_id: UUID (FK → tasks)
user_id: UUID (FK → users)
started_at: datetime
ended_at: datetime | None
duration_minutes: int | None   ← filled automatically on stop
created_at: datetime
```

### Report

```
id: UUID (PK)
user_id: UUID (FK → users)
type: Enum('weekly_summary', 'project_status', 'productivity_overview')
format: Enum('json', 'csv', 'pdf')
status: Enum('pending', 'generating', 'ready', 'failed')
payload: JSON | None           ← for format='json'
file_url: str | None           ← for format='csv'/'pdf'
generated_at: datetime | None
created_at: datetime
```

### GitHubConnection

```
id: UUID (PK)
user_id: UUID (FK → users, unique)
github_user_id: int
github_username: str
access_token_encrypted: bytes  ← Fernet-encrypted
scopes: str                    ← e.g. "repo,read:user"
connected_at: datetime
last_sync_at: datetime | None
```

## Database Schema (relations)

```
users ──────────────────────────────────────────────────────────┐
  │                                                             │
  ├─< refresh_tokens                                            │
  ├─< organization_members >─── organizations                   │
  ├─< projects (created_by)                                     │
  ├─< tasks (assignee_id, created_by)                          │
  ├─< work_sessions                                             │
  ├─< reports                                                   │
  └─< github_connections                                        │
                                                                │
organizations ──< projects ──< tasks ──< work_sessions          │
```

## Endpoint Reference

### Health & Status

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/health` | Health check | ✅ Implemented |
| GET | `/api/v1` | API status | ✅ Implemented |

### Auth (`/api/v1/auth`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Register | No |
| POST | `/api/v1/auth/login` | Login → JWT tokens | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | Refresh token |
| POST | `/api/v1/auth/logout` | Logout | Bearer |
| GET | `/api/v1/auth/me` | Current user profile | Bearer |
| PATCH | `/api/v1/auth/me` | Update profile | Bearer |

### Organizations (`/api/v1/organizations`)

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/api/v1/organizations` | Create org | Authenticated |
| GET | `/api/v1/organizations` | List my orgs | Authenticated |
| GET | `/api/v1/organizations/{org_id}` | Org details | Member |
| PATCH | `/api/v1/organizations/{org_id}` | Update org | Admin/Owner |
| DELETE | `/api/v1/organizations/{org_id}` | Delete org (soft) | Owner |
| POST | `/api/v1/organizations/{org_id}/members` | Invite member | Admin/Owner |
| GET | `/api/v1/organizations/{org_id}/members` | List members | Member |
| DELETE | `/api/v1/organizations/{org_id}/members/{user_id}` | Remove member | Admin/Owner |

### Projects (`/api/v1/projects`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/projects` | Create project | Bearer |
| GET | `/api/v1/projects` | List projects | Bearer |
| GET | `/api/v1/projects/{project_id}` | Project details | Bearer |
| PATCH | `/api/v1/projects/{project_id}` | Update project | Bearer |
| DELETE | `/api/v1/projects/{project_id}` | Archive project | Bearer |

### Tasks (`/api/v1/tasks`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/tasks` | Create task | Bearer |
| GET | `/api/v1/tasks` | List tasks | Bearer |
| GET | `/api/v1/tasks/{task_id}` | Task details | Bearer |
| PATCH | `/api/v1/tasks/{task_id}` | Update task | Bearer |
| DELETE | `/api/v1/tasks/{task_id}` | Delete task | Bearer |
| POST | `/api/v1/tasks/{task_id}/start` | Start work session | Bearer |
| POST | `/api/v1/tasks/{task_id}/stop` | Stop work session | Bearer |
| GET | `/api/v1/tasks/{task_id}/sessions` | Session history | Bearer |

### Metrics (`/api/v1/metrics`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/metrics/summary` | Productivity summary | Bearer |
| GET | `/api/v1/metrics/velocity` | Velocity (tasks/week) | Bearer |
| GET | `/api/v1/metrics/time-tracking` | Daily work hours | Bearer |
| GET | `/api/v1/metrics/completion-rate` | % completed tasks | Bearer |
| GET | `/api/v1/metrics/estimation-accuracy` | Estimation accuracy | Bearer |
| GET | `/api/v1/metrics/streaks` | Activity streaks | Bearer |
| GET | `/api/v1/metrics/projects/{project_id}` | Project metrics | Bearer |

### Reports (`/api/v1/reports`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/reports` | Generate report | Bearer |
| GET | `/api/v1/reports` | List reports | Bearer |
| GET | `/api/v1/reports/{report_id}` | Get report | Bearer |
| DELETE | `/api/v1/reports/{report_id}` | Delete report | Bearer |

### GitHub Integration (`/api/v1/integrations/github`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/authorize` | Start OAuth flow | Bearer |
| GET | `/api/v1/integrations/github/callback` | OAuth callback | — |
| GET | `/api/v1/integrations/github/status` | Connection status | Bearer |
| DELETE | `/api/v1/integrations/github/disconnect` | Disconnect GitHub | Bearer |
| POST | `/api/v1/integrations/github/sync` | Manual sync | Bearer |
| POST | `/api/v1/integrations/github/webhooks` | Webhook receiver | HMAC |

## Authentication Flow

```
1. POST /auth/register → 201 Created
2. POST /auth/login → { access_token, refresh_token, expires_in }
3. Every request: Authorization: Bearer <access_token>
4. When access_token expires (TTL 15 min):
   POST /auth/refresh { refresh_token } → { access_token, expires_in }
5. POST /auth/logout → invalidates refresh_token in DB
```

## Response Format

### Success

```json
{
  "data": { ... },
  "meta": { "total": 42, "limit": 20, "offset": 0 }
}
```

`meta` is omitted for non-paginated responses.

### Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": { "email": "Invalid email format" }
  }
}
```

## Coding Conventions

- **Types:** Strict typing, mypy strict — no `Any` without justification
- **Async:** All route handlers and database operations use async/await
- **Validation:** Pydantic v2 on all inputs; separate Request vs Response schemas
- **Errors:** `AppError` with code, message, and HTTP status; never catch generic Exception
- **Naming:** snake_case for variables/functions, PascalCase for classes, SCREAMING_SNAKE for constants
- **Tests:** Every service unit-tested, every endpoint integration-tested
