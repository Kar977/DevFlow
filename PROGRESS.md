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
| **Organizations** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |
| **Projects** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |
| **Tasks + Time Tracking** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |
| **Metrics** | — | — | ✅ | ✅ | ✅ | ✅ | **Done** |
| **Reports** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |
| **GitHub Integration** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Done** |

**Last completed:** Redis cache-aside dla metryk (InMemoryCache + RedisCache za CacheBackend Protocol, 15 testów zielonych, TTL 60 s, fallback bez cache)  
**Next up:** Stage 2 — Frontend (React)

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

### ✅ 3. Organizations Module

**Branch:** `feature/organizations-module`

**Implements:** workspace/team management  
**Router prefix:** `/api/v1/organizations`

#### Models (new files)
- [x] `core/models/organization.py` — `Organization` (id, name, slug, description, created_by→FK users.id, created_at, updated_at)
- [x] `core/models/organization_member.py` — `OrganizationMember` (id, org_id→FK, user_id→FK, role: `owner`|`admin`|`member`, joined_at)
- [x] Update `core/models/__init__.py` to export new models

#### Repository
- [x] `core/repositories/organization.py` — `OrganizationRepository`:
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
- [x] `core/services/organization.py` — `OrganizationService`:
  - `create_organization(*, user_id, name, description)` → Organization
  - `get_organization(*, org_id, user_id)` → Organization  (check membership)
  - `list_user_organizations(user_id)` → list[Organization]
  - `update_organization(*, org_id, user_id, name, description)` → Organization
  - `delete_organization(*, org_id, user_id)` → None  (only owner)
  - `invite_member(*, org_id, inviter_id, email, role)` → OrganizationMember
  - `list_members(*, org_id, user_id)` → list[OrganizationMember]
  - `remove_member(*, org_id, remover_id, target_user_id)` → None
- [x] `get_organization_service(session)` FastAPI dependency

#### Schemas
- [x] `core/schemas/organizations/__init__.py`:
  - `CreateOrganizationRequest`, `UpdateOrganizationRequest`
  - `OrganizationResponse`, `OrganizationListResponse`
  - `InviteMemberRequest`, `MemberResponse`

#### Routes
- [x] `api/v1/organizations/routes.py`
  - [x] `POST /organizations` → 201
  - [x] `GET /organizations` → 200 list
  - [x] `GET /organizations/{org_id}` → 200
  - [x] `PATCH /organizations/{org_id}` → 200
  - [x] `DELETE /organizations/{org_id}` → 204
  - [x] `POST /organizations/{org_id}/members` → 201
  - [x] `GET /organizations/{org_id}/members` → 200 list
  - [x] `DELETE /organizations/{org_id}/members/{user_id}` → 204

#### Migration
- [x] `migrations/versions/0002_create_organizations_and_members.py`

#### Tests
- [x] `tests/test_organizations.py` — fake repos, dependency override

---

### ✅ 4. Projects Module

**Branch:** `feature/projects-module`

**Implements:** project management (router file: `repositories/`)  
**Router prefix:** `/api/v1/projects`

#### Models
- [x] `core/models/project.py` — `Project` (id, org_id→FK, name, description, status: `active`|`archived`, github_repo_url, created_by→FK, created_at, updated_at)
- [x] Update `core/models/__init__.py`

#### Repository
- [x] `core/repositories/project.py` — `ProjectRepository`:
  - `create(*, org_id, name, description, created_by, github_repo_url)` → Project
  - `get_by_id(project_id)` → Project | None
  - `list_for_org(org_id, *, limit, offset)` → list[Project]
  - `list_for_user(user_id, *, limit, offset)` → list[Project]
  - `update(project, *, name, description, status, github_repo_url)` → Project
  - `archive(project)` → None

#### Service
- [x] `core/services/project.py` — `ProjectService`:
  - `create_project(*, org_id, user_id, name, description, github_repo_url)` → Project
  - `get_project(*, project_id, user_id)` → Project
  - `list_projects(*, user_id, org_id, limit, offset)` → list[Project]
  - `update_project(*, project_id, user_id, **fields)` → Project
  - `archive_project(*, project_id, user_id)` → None
- [x] `get_project_service(session)` FastAPI dependency
- _Access control: every operation requires organization membership (via `OrganizationRepository.get_member`)._

#### Schemas
- [x] `core/schemas/projects/__init__.py`:
  - `CreateProjectRequest`, `UpdateProjectRequest`
  - `ProjectResponse`, `ProjectListResponse`
  - _`ProjectStatsResponse` deferred to Tasks/Metrics (no task data source yet)._

#### Routes
- [x] `api/v1/repositories/routes.py` (replaced placeholder, prefix → `/api/v1/projects`)
  - [x] `POST /projects` → 201
  - [x] `GET /projects` → 200 list (query: `org_id`, `limit`, `offset`)
  - [x] `GET /projects/{project_id}` → 200
  - [x] `PATCH /projects/{project_id}` → 200
  - [x] `DELETE /projects/{project_id}` → 204 (archives the project)

#### Migration
- [x] `migrations/versions/0003_create_projects.py`

#### Tests
- [x] `tests/test_projects.py` — 8 tests, fake repos, dependency override

---

### ✅ 5. Tasks + Time Tracking Module

**Branch:** `feature/tasks-module`

**Implements:** task management + work sessions (router file: `pull_requests/`)  
**Router prefix:** `/api/v1/tasks`

#### Models
- [x] `core/models/task.py` — `Task`:
  - id, project_id→FK, title, description, status (`backlog`|`todo`|`in_progress`|`review`|`done`|`cancelled`), priority (`low`|`medium`|`high`|`critical`), estimate_minutes, assignee_id→FK users.id, due_date, github_pr_url, created_by→FK, created_at, updated_at
- [x] `core/models/work_session.py` — `WorkSession`:
  - id, task_id→FK, user_id→FK, started_at, ended_at (nullable), duration_minutes (computed on stop), created_at
- [x] Update `core/models/__init__.py`

#### Repository
- [x] `core/repositories/task.py` — `TaskRepository`:
  - `create(*, project_id, title, description, priority, estimate_minutes, assignee_id, due_date, github_pr_url, created_by)` → Task
  - `get_by_id(task_id)` → Task | None
  - `list_for_project(project_id, *, status, assignee_id, limit, offset)` → list[Task]
  - `update(task, **fields)` → Task
  - `delete(task)` → None
- [x] `core/repositories/work_session.py` — `WorkSessionRepository`:
  - `create(*, task_id, user_id, started_at)` → WorkSession
  - `get_active_for_user(user_id)` → WorkSession | None
  - `get_by_id(session_id)` → WorkSession | None
  - `list_for_task(task_id)` → list[WorkSession]
  - `stop(session, *, ended_at, duration_minutes)` → WorkSession

#### Service
- [x] `core/services/task.py` — `TaskService`:
  - `create_task(*, project_id, user_id, title, **fields)` → Task
  - `get_task(*, task_id, user_id)` → Task
  - `list_tasks(*, project_id, user_id, status, assignee_id, limit, offset)` → list[Task]
  - `update_task(*, task_id, user_id, **fields)` → Task
  - `delete_task(*, task_id, user_id)` → None
  - `start_session(*, task_id, user_id)` → WorkSession  (409 if already active)
  - `stop_session(*, task_id, user_id)` → WorkSession  (computes duration_minutes)
  - `list_sessions(*, task_id, user_id)` → list[WorkSession]
- [x] `get_task_service(session)` FastAPI dependency
- _Access control: every operation requires membership in the task's project's organization (project → org → member)._

#### Schemas
- [x] `core/schemas/tasks/__init__.py`:
  - `CreateTaskRequest`, `UpdateTaskRequest`
  - `TaskResponse`, `TaskListResponse`
  - `WorkSessionResponse`, `WorkSessionListResponse`

#### Routes
- [x] `api/v1/pull_requests/routes.py` (replaced placeholder, prefix → `/api/v1/tasks`)
  - [x] `POST /tasks` → 201
  - [x] `GET /tasks` → 200 list (query params: `project_id` required, `status`, `assignee_id`, `limit`, `offset`)
  - [x] `GET /tasks/{task_id}` → 200
  - [x] `PATCH /tasks/{task_id}` → 200
  - [x] `DELETE /tasks/{task_id}` → 204
  - [x] `POST /tasks/{task_id}/start` → 201 WorkSession
  - [x] `POST /tasks/{task_id}/stop` → 200 WorkSession
  - [x] `GET /tasks/{task_id}/sessions` → 200 list

#### Migration
- [x] `migrations/versions/0004_create_tasks_and_work_sessions.py`

#### Tests
- [x] `tests/test_tasks.py` — 12 tests, fake repos, dependency override

---

### ✅ 6. Metrics Module

**Branch:** `feature/metrics-module`

**Implements:** productivity dashboards (no ORM model — aggregates over tasks/sessions)  
**Router prefix:** `/api/v1/metrics`

#### Repository
- [x] `core/repositories/metrics.py` — `MetricsRepository` (read-only): `get_tasks_for_user`, `get_work_sessions_for_user`, `get_tasks_for_project`. User-scoped, cross-project; date filtering + aggregation happen in the service.

#### Service
- [x] `core/services/metrics.py` — `MetricsService`:
  - `get_summary(*, user_id, date_from, date_to)` → SummaryResponse (completed + active hours vs previous period)
  - `get_velocity(*, user_id, date_from, date_to)` → VelocityResponse  (tasks closed per week + trend)
  - `get_time_tracking(*, user_id, date_from, date_to)` → TimeTrackingResponse  (daily hours)
  - `get_completion_rate(*, user_id, date_from, date_to)` → CompletionRateResponse
  - `get_estimation_accuracy(*, user_id, date_from, date_to)` → EstimationAccuracyResponse
  - `get_streaks(*, user_id)` → StreakResponse
  - `get_project_metrics(*, project_id, user_id)` → ProjectMetricsResponse (org-membership gated)
- [x] `get_metrics_service(session)` FastAPI dependency
- _A task is "completed" when status == 'done'; completion time approximated by `updated_at` (no completed_at column)._
- [x] **Cache (Redis, cache-aside, TTL 60 s, fallback bez cache)** — `core/cache.py`: `CacheBackend` Protocol, `InMemoryCache` (dev/test), `RedisCache` (prod via `DEVFLOW_API_REDIS_URL`). Cache wstrzyknięty jako opcjonalny parametr `MetricsService`; Redis dodany do `infra/docker-compose.yml`.

#### Schemas
- [x] `core/schemas/metrics/__init__.py`:
  - `MetricValueResponse` (value, prev_value, delta_pct)
  - `SummaryResponse`, `VelocityResponse`, `TimeTrackingResponse` (+ `DailyHoursResponse`)
  - `CompletionRateResponse`, `EstimationAccuracyResponse`
  - `StreakResponse`, `ProjectMetricsResponse`

#### Routes
- [x] `api/v1/metrics/routes.py` (replaced placeholder)
  - [x] `GET /metrics/summary`
  - [x] `GET /metrics/velocity`
  - [x] `GET /metrics/time-tracking`
  - [x] `GET /metrics/completion-rate`
  - [x] `GET /metrics/estimation-accuracy`
  - [x] `GET /metrics/streaks`
  - [x] `GET /metrics/projects/{project_id}`

#### Tests
- [x] `tests/test_metrics.py` — 9 tests, fake repos, dependency override
- [x] `tests/test_metrics_cache.py` — 15 tests: InMemoryCache unit, RedisCache fallback (broken-client stub), MetricsService cache-hit / cache-miss / expiry / no-cache

---

### ✅ 7. Reports Module

**Branch:** `feature/reports-module`

**Router prefix:** `/api/v1/reports`

#### Models
- [x] `core/models/report.py` — `Report` (id, user_id→FK, type: `weekly_summary`|`project_status`|`productivity_overview`, format: `json`, status: `pending`|`generating`|`ready`|`failed`, payload JSON, error_message, generated_at, created_at)
- [x] Update `core/models/__init__.py`

#### Repository
- [x] `core/repositories/report.py` — `ReportRepository`: `create`, `get_by_id`, `list_for_user`, `count_for_user`, `update_status`, `delete`

#### Service
- [x] `core/services/report.py` — `ReportService`:
  - `create_report(*, user_id, report_type, fmt, project_id)` → Report (validates project_id for project_status)
  - `get_report(*, report_id, user_id)` → Report (404/403)
  - `list_reports(*, user_id, limit, offset)` → tuple[list[Report], int]
  - `delete_report(*, report_id, user_id)` → None
  - `run_report_generation(...)` — background generator (own DB session via `async_session_factory`)
  - `ReportGenerator` Protocol + `get_report_generator()` dependency (overridable in tests)
- [x] `get_report_service(session)` FastAPI dependency
- _Generation reuses `MetricsService` for all three report types; background task runs after request-scoped session closes._

#### Schemas
- [x] `core/schemas/reports/__init__.py`: `CreateReportRequest`, `ReportResponse`, `ReportListResponse`

#### Routes
- [x] `api/v1/reports/routes.py` (replaces placeholder)
  - [x] `POST /reports` → 202 (async generation via BackgroundTasks)
  - [x] `GET /reports` → 200 list (`{items, total}`)
  - [x] `GET /reports/{report_id}` → 200
  - [x] `DELETE /reports/{report_id}` → 204

#### Migration
- [x] `migrations/versions/0006_create_reports.py`

#### Tests
- [x] `tests/test_reports.py` — 14 tests, fake repos + fake generator, dependency override
  - [x] create: 202, invalid type → 422, project_status without project_id → 422, with project_id → 202
  - [x] list: 200 + total, empty list, pagination
  - [x] get: 200, 404, 403 (other user)
  - [x] delete: 204, 404, 403 (other user)
  - [x] unit test: `_generate_payload` weekly_summary shape

---

### ✅ 8. GitHub Integration Module

**Branch:** `feature/github-integration`

**Router prefix:** `/api/v1/integrations/github`  
**Note:** Optional — system works fully without it. Requires env vars: `DEVFLOW_API_GITHUB_CLIENT_ID`, `DEVFLOW_API_GITHUB_CLIENT_SECRET`, `DEVFLOW_API_GITHUB_TOKEN_ENCRYPTION_KEY` (Fernet), `DEVFLOW_API_GITHUB_WEBHOOK_SECRET`. New runtime deps: `httpx`, `cryptography`.

#### Models
- [x] `core/models/github_connection.py` — `GitHubConnection` (user_id→FK unique, github_user_id, github_login, access_token_encrypted, scopes, connected_at, updated_at)
- [x] Update `core/models/__init__.py`

#### Core integration layer
- [x] `core/integrations/github/client.py` — async httpx client, retry/backoff (3 attempts, exp. sleep)
- [x] `core/integrations/github/oauth.py` — OAuth App flow (authorize URL, code→token exchange)
- [x] `core/integrations/github/webhooks.py` — HMAC-SHA256 signature verification + event parsing
- [x] `core/integrations/github/sync.py` — issue/PR → TaskFields mapping
- [x] `core/integrations/github/crypto.py` — Fernet token encryption/decryption at rest

#### Repository
- [x] `core/repositories/github_connection.py` — `GitHubConnectionRepository`: `create`, `get_by_user_id`, `update_token`, `delete`
- [x] `core/repositories/task.py` extended: `get_by_github_pr_url` for deduplication

#### Service
- [x] `core/services/github_sync.py` — `GitHubSyncService`:
  - `authorize_url(*, user_id)` → str
  - `handle_callback(*, user_id, code)` → GitHubConnection (upsert on re-auth)
  - `get_connection_status(*, user_id)` → GitHubConnection | None
  - `disconnect(*, user_id)` → None
  - `sync(*, user_id, project_id)` → SyncResultResponse (org-membership gated, dedupes by github_pr_url)
  - `handle_webhook(*, payload, signature, raw_body)` → None (HMAC-SHA256 validated)

#### Schemas
- [x] `core/schemas/github/__init__.py`: `AuthorizeUrlResponse`, `GitHubConnectionResponse`, `SyncResultResponse`

#### Routes
- [x] `api/v1/integrations/github/routes.py` (replaced placeholder)
  - [x] `POST /integrations/github/authorize`
  - [x] `GET /integrations/github/callback`
  - [x] `GET /integrations/github/status`
  - [x] `DELETE /integrations/github/disconnect`
  - [x] `POST /integrations/github/sync`
  - [x] `POST /integrations/github/webhooks`

#### Migration
- [x] `migrations/versions/0005_create_github_connections.py`
  - _Note: migration is 0005 (Reports was planned as 0005 but GitHub shipped first, as agreed)._

#### Tests
- [x] `tests/test_github_integration.py` — 18 tests: cipher roundtrip, HMAC verify, OAuth URL, sync dedup, route flows (fake repos + dependency override)

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
│   │   ├── organizations/routes.py  ✅
│   │   ├── repositories/routes.py   ✅  (= Projects, prefix /projects)
│   │   ├── pull_requests/routes.py  ✅  (= Tasks, prefix /tasks)
│   │   ├── metrics/routes.py        ✅
│   │   ├── reports/routes.py        ✅
│   │   └── integrations/github/routes.py ✅
│   └── core/
│       ├── models/        base.py ✅  user.py ✅  refresh_token.py ✅  organization.py ✅  organization_member.py ✅  project.py ✅  task.py ✅  work_session.py ✅  github_connection.py ✅  report.py ✅
│       ├── repositories/  user.py ✅  refresh_token.py ✅  organization.py ✅  project.py ✅  task.py ✅  work_session.py ✅  metrics.py ✅  github_connection.py ✅  report.py ✅
│       ├── integrations/github/  client.py ✅  oauth.py ✅  webhooks.py ✅  sync.py ✅  crypto.py ✅
│       ├── services/      auth.py ✅  organization.py ✅  project.py ✅  task.py ✅  metrics.py ✅  github_sync.py ✅  report.py ✅
│       ├── schemas/       auth/ ✅  organizations/ ✅  projects/ ✅  tasks/ ✅  metrics/ ✅  github/ ✅  reports/ ✅
│       ├── security.py    ✅
│       ├── config.py      ✅
│       └── database.py    ✅
├── migrations/versions/
│   ├── 0001_create_users_and_refresh_tokens.py ✅
│   ├── 0002_create_organizations_and_members.py ✅
│   ├── 0003_create_projects.py ✅
│   ├── 0004_create_tasks_and_work_sessions.py ✅
│   ├── 0005_create_github_connections.py ✅
│   └── 0006_create_reports.py ✅
└── tests/
    ├── test_architecture_boundaries.py ✅
    ├── test_health.py                  ✅
    ├── test_auth.py                    ✅  (14 tests)
    ├── test_organizations.py           ✅
    ├── test_projects.py                ✅  (8 tests)
    ├── test_tasks.py                   ✅  (12 tests)
    ├── test_metrics.py                 ✅  (9 tests)
    ├── test_github_integration.py      ✅  (18 tests)
    └── test_reports.py                 ✅  (14 tests)
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
