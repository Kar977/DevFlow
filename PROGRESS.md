# DevFlow Insight — Implementation Progress

> **How to use this file:**  
> Before starting work in any new Claude session, read this file first.  
> After completing a task, mark it `[x]` and update the "Last completed" note.  
> The [Architecture Rules](#architecture-rules) section must be respected at all times.

---

## Quick Status

| Module | Models | Migration | Repository | Service | Routes | Tests | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Auth** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |
| **Organizations** | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | Not started |
| **Projects** | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | Not started |
| **Tasks + Time Tracking** | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | Not started |
| **Metrics** | — | — | ☐ | ☐ | ☐ | ☐ | Not started |
| **Reports** | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | Not started |
| **GitHub Integration** | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | Not started |

**Last completed:** Auth module (JWT + bcrypt + refresh tokens, 18 tests green)  
**Next up:** Organizations module

---

## Stage 1 — Backend API

### ✅ 1. Infrastructure & Scaffold

- [x] FastAPI app factory (`main.py`)
- [x] Config via pydantic-settings (`core/config.py`)
- [x] Async SQLAlchemy engine + `get_session` dependency (`core/database.py`)
- [x] `Base` declarative base
- [x] `AppError` + exception handlers (`core/errors.py`)
- [x] Architecture boundary test (`tests/test_architecture_boundaries.py`)
- [x] Health check endpoint (`GET /health`)
- [x] Docker Compose (api + postgres)
- [x] Alembic migration environment (`migrations/env.py`)

---

### ✅ 2. Auth Module

**Branch:** `feature/auth-module`

#### Models
- [x] `core/models/base.py` — `UUIDPrimaryKeyMixin`, `TimestampMixin`
- [x] `core/models/user.py` — `User` (id, email, hashed_password, full_name, avatar_url, created_at, updated_at)
- [x] `core/models/refresh_token.py` — `RefreshToken` (id, user_id→FK, token_hash SHA-256, expires_at, revoked_at, created_at)
- [x] `core/models/__init__.py` — exports `User`, `RefreshToken`

#### Security
- [x] `core/security.py` — `hash_password`, `verify_password` (bcrypt direct), `generate_refresh_token`, `hash_token` (SHA-256), `create_access_token` (JWT HS256), `decode_access_token`, `get_current_subject` (FastAPI dep), `AuthenticatedSubject`

#### Repository
- [x] `core/repositories/user.py` — `UserRepository`: `get_by_id`, `get_by_email`, `exists_by_email`, `create`, `update`
- [x] `core/repositories/refresh_token.py` — `RefreshTokenRepository`: `create`, `get_by_hash`, `revoke`, `revoke_all_for_user`

#### Service
- [x] `core/services/auth.py` — `AuthService`: `register`, `login`, `refresh`, `logout`, `get_user`, `update_profile`, `_issue_tokens`, `access_token_expires_in`
- [x] `get_auth_service(session)` FastAPI dependency at module level

#### Schemas
- [x] `core/schemas/auth/__init__.py` — `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `UpdateProfileRequest`, `TokenResponse`, `AccessTokenResponse`, `UserResponse`

#### Routes
- [x] `api/v1/auth/routes.py`
  - [x] `POST /register` → 201 UserResponse
  - [x] `POST /login` → 200 TokenResponse
  - [x] `POST /refresh` → 200 AccessTokenResponse
  - [x] `POST /logout` → 204
  - [x] `GET /me` → 200 UserResponse (protected)
  - [x] `PATCH /me` → 200 UserResponse (protected)

#### Migration
- [x] `migrations/versions/0001_create_users_and_refresh_tokens.py`

#### Tests
- [x] `tests/test_auth.py` — 14 tests, fake in-memory repos, dependency override
  - [x] register: success, duplicate email, short password
  - [x] login: success, wrong password, unknown email
  - [x] refresh: success, invalid token, revoked token, expired token
  - [x] logout: revokes token (subsequent refresh fails)
  - [x] GET /me: success, missing token
  - [x] PATCH /me: updates full_name

---

### ☐ 3. Organizations Module

**Implements:** workspace/team management  
**Router prefix:** `/api/v1/organizations`

#### Models (new files)
- [ ] `core/models/organization.py` — `Organization` (id, name, slug, description, created_by→FK users.id, created_at, updated_at)
- [ ] `core/models/organization_member.py` — `OrganizationMember` (id, org_id→FK, user_id→FK, role: `owner`|`admin`|`member`, joined_at)
- [ ] Update `core/models/__init__.py` to export new models

#### Repository
- [ ] `core/repositories/organization.py` — `OrganizationRepository`:
  - `create(*, name, slug, description, created_by)` → Organization
  - `get_by_id(org_id)` → Organization | None
  - `get_by_slug(slug)` → Organization | None
  - `list_for_user(user_id)` → list[Organization]
  - `update(org, *, name, description)` → Organization
  - `soft_delete(org, deleted_at)` → None
  - `add_member(*, org_id, user_id, role)` → OrganizationMember
  - `get_member(org_id, user_id)` → OrganizationMember | None
  - `list_members(org_id)` → list[OrganizationMember]
  - `remove_member(member)` → None

#### Service
- [ ] `core/services/organization.py` — `OrganizationService`:
  - `create_organization(*, user_id, name, description)` → Organization
  - `get_organization(*, org_id, user_id)` → Organization  (check membership)
  - `list_user_organizations(user_id)` → list[Organization]
  - `update_organization(*, org_id, user_id, name, description)` → Organization
  - `delete_organization(*, org_id, user_id)` → None  (only owner)
  - `invite_member(*, org_id, inviter_id, email, role)` → OrganizationMember
  - `list_members(*, org_id, user_id)` → list[OrganizationMember]
  - `remove_member(*, org_id, remover_id, target_user_id)` → None
- [ ] `get_organization_service(session)` FastAPI dependency

#### Schemas
- [ ] `core/schemas/organizations/__init__.py`:
  - `CreateOrganizationRequest`, `UpdateOrganizationRequest`
  - `OrganizationResponse`, `OrganizationListResponse`
  - `InviteMemberRequest`, `MemberResponse`

#### Routes
- [ ] `api/v1/organizations/routes.py`
  - [ ] `POST /organizations` → 201
  - [ ] `GET /organizations` → 200 list
  - [ ] `GET /organizations/{org_id}` → 200
  - [ ] `PATCH /organizations/{org_id}` → 200
  - [ ] `DELETE /organizations/{org_id}` → 204
  - [ ] `POST /organizations/{org_id}/members` → 201
  - [ ] `GET /organizations/{org_id}/members` → 200 list
  - [ ] `DELETE /organizations/{org_id}/members/{user_id}` → 204

#### Migration
- [ ] `migrations/versions/0002_create_organizations_and_members.py`

#### Tests
- [ ] `tests/test_organizations.py` — fake repos, dependency override

---

### ☐ 4. Projects Module

**Implements:** project management (router file: `repositories/`)  
**Router prefix:** `/api/v1/projects`

#### Models
- [ ] `core/models/project.py` — `Project` (id, org_id→FK, name, description, status: `active`|`archived`, github_repo_url, created_by→FK, created_at, updated_at)
- [ ] Update `core/models/__init__.py`

#### Repository
- [ ] `core/repositories/project.py` — `ProjectRepository`:
  - `create(*, org_id, name, description, created_by, github_repo_url)` → Project
  - `get_by_id(project_id)` → Project | None
  - `list_for_org(org_id)` → list[Project]
  - `list_for_user(user_id)` → list[Project]
  - `update(project, *, name, description, status, github_repo_url)` → Project
  - `archive(project)` → None

#### Service
- [ ] `core/services/project.py` — `ProjectService`:
  - `create_project(*, org_id, user_id, name, description, github_repo_url)` → Project
  - `get_project(*, project_id, user_id)` → Project
  - `list_projects(*, user_id, org_id)` → list[Project]
  - `update_project(*, project_id, user_id, **fields)` → Project
  - `archive_project(*, project_id, user_id)` → None
- [ ] `get_project_service(session)` FastAPI dependency

#### Schemas
- [ ] `core/schemas/projects/__init__.py`:
  - `CreateProjectRequest`, `UpdateProjectRequest`
  - `ProjectResponse`, `ProjectStatsResponse`

#### Routes
- [ ] `api/v1/repositories/routes.py` (replaces placeholder, prefix → `/api/v1/projects`)
  - [ ] `POST /projects` → 201
  - [ ] `GET /projects` → 200 list
  - [ ] `GET /projects/{project_id}` → 200
  - [ ] `PATCH /projects/{project_id}` → 200
  - [ ] `DELETE /projects/{project_id}` → 204

#### Migration
- [ ] `migrations/versions/0003_create_projects.py`

#### Tests
- [ ] `tests/test_projects.py`

---

### ☐ 5. Tasks + Time Tracking Module

**Implements:** task management + work sessions (router file: `pull_requests/`)  
**Router prefix:** `/api/v1/tasks`

#### Models
- [ ] `core/models/task.py` — `Task`:
  - id, project_id→FK, title, description, status (`backlog`|`todo`|`in_progress`|`review`|`done`|`cancelled`), priority (`low`|`medium`|`high`|`critical`), estimate_minutes, assignee_id→FK users.id, due_date, github_pr_url, created_by→FK, created_at, updated_at
- [ ] `core/models/work_session.py` — `WorkSession`:
  - id, task_id→FK, user_id→FK, started_at, ended_at (nullable), duration_minutes (computed on stop), created_at
- [ ] Update `core/models/__init__.py`

#### Repository
- [ ] `core/repositories/task.py` — `TaskRepository`:
  - `create(*, project_id, title, description, priority, estimate_minutes, assignee_id, created_by)` → Task
  - `get_by_id(task_id)` → Task | None
  - `list_for_project(project_id, *, status, assignee_id)` → list[Task]
  - `update(task, **fields)` → Task
  - `delete(task)` → None
- [ ] `core/repositories/work_session.py` — `WorkSessionRepository`:
  - `create(*, task_id, user_id, started_at)` → WorkSession
  - `get_active_for_user(user_id)` → WorkSession | None
  - `get_by_id(session_id)` → WorkSession | None
  - `list_for_task(task_id)` → list[WorkSession]
  - `stop(session, *, ended_at, duration_minutes)` → WorkSession

#### Service
- [ ] `core/services/task.py` — `TaskService`:
  - `create_task(*, project_id, user_id, title, **fields)` → Task
  - `get_task(*, task_id, user_id)` → Task
  - `list_tasks(*, project_id, user_id, status, assignee_id)` → list[Task]
  - `update_task(*, task_id, user_id, **fields)` → Task
  - `delete_task(*, task_id, user_id)` → None
  - `start_session(*, task_id, user_id)` → WorkSession  (error if already active)
  - `stop_session(*, task_id, user_id)` → WorkSession
  - `list_sessions(*, task_id, user_id)` → list[WorkSession]
- [ ] `get_task_service(session)` FastAPI dependency

#### Schemas
- [ ] `core/schemas/tasks/__init__.py`:
  - `CreateTaskRequest`, `UpdateTaskRequest`
  - `TaskResponse`, `WorkSessionResponse`

#### Routes
- [ ] `api/v1/pull_requests/routes.py` (replaces placeholder, prefix → `/api/v1/tasks`)
  - [ ] `POST /tasks` → 201
  - [ ] `GET /tasks` → 200 list (query params: project_id, status, assignee_id)
  - [ ] `GET /tasks/{task_id}` → 200
  - [ ] `PATCH /tasks/{task_id}` → 200
  - [ ] `DELETE /tasks/{task_id}` → 204
  - [ ] `POST /tasks/{task_id}/start` → 201 WorkSession
  - [ ] `POST /tasks/{task_id}/stop` → 200 WorkSession
  - [ ] `GET /tasks/{task_id}/sessions` → 200 list

#### Migration
- [ ] `migrations/versions/0004_create_tasks_and_work_sessions.py`

#### Tests
- [ ] `tests/test_tasks.py`

---

### ☐ 6. Metrics Module

**Implements:** productivity dashboards (no ORM model — aggregates over tasks/sessions)  
**Router prefix:** `/api/v1/metrics`

#### Service
- [ ] `core/services/metrics.py` — `MetricsService`:
  - `get_summary(*, user_id, date_from, date_to)` → SummaryResponse
  - `get_velocity(*, user_id, date_from, date_to)` → VelocityResponse  (tasks closed per week + trend)
  - `get_time_tracking(*, user_id, date_from, date_to)` → TimeTrackingResponse  (daily/weekly hours)
  - `get_completion_rate(*, user_id, date_from, date_to)` → CompletionRateResponse
  - `get_estimation_accuracy(*, user_id, date_from, date_to)` → EstimationAccuracyResponse
  - `get_streaks(*, user_id)` → StreakResponse
  - `get_project_metrics(*, project_id, user_id)` → ProjectMetricsResponse
- [ ] `get_metrics_service(session)` FastAPI dependency

#### Schemas
- [ ] `core/schemas/metrics/__init__.py`:
  - `MetricValueResponse` (value, prev_value, delta_pct)
  - `SummaryResponse`, `VelocityResponse`, `TimeTrackingResponse`
  - `CompletionRateResponse`, `EstimationAccuracyResponse`
  - `StreakResponse`, `ProjectMetricsResponse`

#### Routes
- [ ] `api/v1/metrics/routes.py` (replaces placeholder)
  - [ ] `GET /metrics/summary`
  - [ ] `GET /metrics/velocity`
  - [ ] `GET /metrics/time-tracking`
  - [ ] `GET /metrics/completion-rate`
  - [ ] `GET /metrics/estimation-accuracy`
  - [ ] `GET /metrics/streaks`
  - [ ] `GET /metrics/projects/{project_id}`

#### Tests
- [ ] `tests/test_metrics.py`

---

### ☐ 7. Reports Module

**Router prefix:** `/api/v1/reports`

#### Models
- [ ] `core/models/report.py` — `Report` (id, user_id→FK, type: `weekly_summary`|`project_status`|`productivity_overview`, format: `json`|`csv`, status: `pending`|`generating`|`ready`|`failed`, payload JSON, generated_at, created_at)
- [ ] Update `core/models/__init__.py`

#### Repository
- [ ] `core/repositories/report.py` — `ReportRepository`: `create`, `get_by_id`, `list_for_user`, `update_status`, `delete`

#### Service
- [ ] `core/services/report.py` — `ReportService`:
  - `create_report(*, user_id, type, format)` → Report
  - `get_report(*, report_id, user_id)` → Report
  - `list_reports(*, user_id)` → list[Report]
  - `delete_report(*, report_id, user_id)` → None
  - `_generate(report)` — background task
- [ ] `get_report_service(session)` FastAPI dependency

#### Schemas
- [ ] `core/schemas/reports/__init__.py`: `CreateReportRequest`, `ReportResponse`

#### Routes
- [ ] `api/v1/reports/routes.py` (replaces placeholder)
  - [ ] `POST /reports` → 202 (async generation)
  - [ ] `GET /reports` → 200 list
  - [ ] `GET /reports/{report_id}` → 200
  - [ ] `DELETE /reports/{report_id}` → 204

#### Migration
- [ ] `migrations/versions/0005_create_reports.py`

#### Tests
- [ ] `tests/test_reports.py`

---

### ☐ 8. GitHub Integration Module

**Router prefix:** `/api/v1/integrations/github`  
**Note:** Optional — system works fully without it.

#### Models
- [ ] `core/models/github_connection.py` — `GitHubConnection` (id, user_id→FK unique, github_user_id, github_login, access_token_encrypted, scopes, connected_at, updated_at)
- [ ] Update `core/models/__init__.py`

#### Core integration layer
- [ ] `core/integrations/github/client.py` — async httpx client, rate-limit handling, retry/backoff
- [ ] `core/integrations/github/oauth.py` — OAuth App flow (exchange code → token)
- [ ] `core/integrations/github/webhooks.py` — HMAC-SHA256 signature verification + event parsing
- [ ] `core/integrations/github/sync.py` — sync repos/PRs/issues → Tasks

#### Repository
- [ ] `core/repositories/github_connection.py` — `GitHubConnectionRepository`: `create`, `get_by_user_id`, `update_token`, `delete`

#### Service
- [ ] `core/services/github_sync.py` — `GitHubSyncService`:
  - `authorize_url(*, user_id)` → str
  - `handle_callback(*, user_id, code)` → GitHubConnection
  - `get_connection_status(*, user_id)` → GitHubConnection | None
  - `disconnect(*, user_id)` → None
  - `sync(*, user_id)` → SyncResultResponse
  - `handle_webhook(*, payload, signature)` → None

#### Schemas
- [ ] `core/schemas/github/__init__.py`: `GitHubConnectionResponse`, `SyncResultResponse`, `WebhookPayload`

#### Routes
- [ ] `api/v1/integrations/github/routes.py` (replaces placeholder)
  - [ ] `POST /integrations/github/authorize`
  - [ ] `GET /integrations/github/callback`
  - [ ] `GET /integrations/github/status`
  - [ ] `DELETE /integrations/github/disconnect`
  - [ ] `POST /integrations/github/sync`
  - [ ] `POST /integrations/github/webhooks`

#### Migration
- [ ] `migrations/versions/0006_create_github_connections.py`

#### Tests
- [ ] `tests/test_github_integration.py`

---

## Stage 2 — Frontend (React)

> Not started. Begin after all Stage 1 modules are complete.

- [ ] React + TypeScript + Vite scaffold
- [ ] Auth pages (login, register)
- [ ] Dashboard layout
- [ ] Task management UI
- [ ] Project management UI
- [ ] Productivity metrics dashboards
- [ ] Time tracking controls
- [ ] GitHub integration settings page

---

## Architecture Rules

> These rules are enforced by `tests/test_architecture_boundaries.py`. Breaking them causes CI failure.

### Layer boundaries (strict)

```
Routes  →  Services  →  Repositories  →  Models
```

- **Routes** may import from: `core.services.*`, `core.schemas.*`, `core.security`, `core.errors`
- **Routes must NOT import from:** `core.repositories.*`, `core.integrations.*`
- **Services** may import from: `core.repositories.*`, `core.models.*`, `core.security`, `core.errors`, `core.config`
- **Services must NOT import from:** `api.*`

### Dependency injection pattern

Every service module exposes a `get_xxx_service(session: AsyncSession = Depends(get_session)) -> XxxService` factory.  
Routes inject the service via `service: XxxService = Depends(get_xxx_service)`.

```python
# ✅ Correct — in routes.py
from devflow_api.core.services.organization import OrganizationService, get_organization_service

@router.post("/organizations")
async def create_org(
    body: CreateOrganizationRequest,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    ...
```

### Transaction management

`get_session` uses `session.begin()` → one transaction per request, auto-commit on success, auto-rollback on exception.  
**Services must NOT call `session.commit()`** — the session is committed by the middleware.

### Model conventions

- Every model inherits `UUIDPrimaryKeyMixin` + `TimestampMixin` (from `core/models/base.py`) + `Base`
- Table names: `snake_case` plural (e.g., `work_sessions`, `github_connections`)
- Each model in its own file under `core/models/`

### Test pattern

- Tests use **fake in-memory repositories** (no database required)
- Override FastAPI dependencies with `app.dependency_overrides[get_xxx_service] = lambda: fake_service`
- Architecture boundary test lives in `tests/test_architecture_boundaries.py`
- When instantiating ORM objects in fake repos, set `id=uuid.uuid4()`, `created_at=datetime.now(UTC)`, `updated_at=datetime.now(UTC)` explicitly (SQLAlchemy `default=` applies at INSERT time, not Python construction)

---

## Key File Paths

```
apps/api/
├── src/devflow_api/
│   ├── api/v1/
│   │   ├── auth/routes.py          ✅
│   │   ├── organizations/routes.py  ☐  (replace placeholder)
│   │   ├── repositories/routes.py   ☐  (= Projects, replace placeholder)
│   │   ├── pull_requests/routes.py  ☐  (= Tasks, replace placeholder)
│   │   ├── metrics/routes.py        ☐  (replace placeholder)
│   │   ├── reports/routes.py        ☐  (replace placeholder)
│   │   └── integrations/github/routes.py ☐ (replace placeholder)
│   └── core/
│       ├── models/        base.py ✅  user.py ✅  refresh_token.py ✅
│       ├── repositories/  user.py ✅  refresh_token.py ✅
│       ├── services/      auth.py ✅
│       ├── schemas/       auth/ ✅
│       ├── security.py    ✅
│       ├── config.py      ✅
│       └── database.py    ✅
├── migrations/versions/
│   └── 0001_create_users_and_refresh_tokens.py ✅
└── tests/
    ├── test_architecture_boundaries.py ✅
    ├── test_health.py                  ✅
    └── test_auth.py                    ✅  (14 tests)
```

---

## Environment & Commands

```bash
# Run tests
uv run pytest -v

# Type check
uv run mypy src/

# Lint
uv run ruff check src/ tests/

# Auto-fix lint
uv run ruff check --fix src/ tests/

# Start dev server (requires running postgres)
uv run uvicorn devflow_api.main:app --reload

# Run migrations (requires running postgres)
uv run alembic upgrade head

# Docker (full stack)
docker compose up
```

**Working directory for all commands:** `apps/api/`
