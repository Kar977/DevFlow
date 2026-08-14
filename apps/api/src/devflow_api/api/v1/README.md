# API v1

Version 1 of the public HTTP API contract. All routes are mounted under `/api/v1`.

## Full Endpoint List

### System

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | Health check | No |
| GET | `/api/v1` | API status | No |

### Auth

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Register | No |
| POST | `/api/v1/auth/login` | Login → JWT | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | Refresh token |
| POST | `/api/v1/auth/logout` | Logout | Bearer |
| GET | `/api/v1/auth/me` | Current user profile | Bearer |
| PATCH | `/api/v1/auth/me` | Update profile | Bearer |

### Organizations

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/organizations` | Create org | Bearer |
| GET | `/api/v1/organizations` | List my orgs | Bearer |
| GET | `/api/v1/organizations/{org_id}` | Org details | Bearer |
| PATCH | `/api/v1/organizations/{org_id}` | Update org | Bearer (admin+) |
| DELETE | `/api/v1/organizations/{org_id}` | Delete org | Bearer (owner) |
| POST | `/api/v1/organizations/{org_id}/members` | Invite member | Bearer (admin+) |
| GET | `/api/v1/organizations/{org_id}/members` | List members | Bearer |
| DELETE | `/api/v1/organizations/{org_id}/members/{user_id}` | Remove member | Bearer (admin+) |
| PATCH | `/api/v1/organizations/{org_id}/members/{user_id}` | Change member role | Bearer (admin+) |

### Projects (router dir: `api/v1/projects/`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/projects` | Create project | Bearer |
| GET | `/api/v1/projects` | List projects | Bearer |
| GET | `/api/v1/projects/{project_id}` | Project details | Bearer |
| PATCH | `/api/v1/projects/{project_id}` | Update project | Bearer |
| DELETE | `/api/v1/projects/{project_id}` | Archive project | Bearer |

### Tasks + Time Tracking (router dir: `api/v1/tasks/`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/tasks` | Create task | Bearer |
| GET | `/api/v1/tasks` | List tasks | Bearer |
| GET | `/api/v1/tasks/overdue` | Caller's overdue tasks across an org | Bearer |
| GET | `/api/v1/tasks/{task_id}` | Task details | Bearer |
| PATCH | `/api/v1/tasks/{task_id}` | Update task | Bearer |
| DELETE | `/api/v1/tasks/{task_id}` | Delete task | Bearer |
| POST | `/api/v1/tasks/{task_id}/start` | Start work session | Bearer |
| POST | `/api/v1/tasks/{task_id}/stop` | Stop work session | Bearer |
| GET | `/api/v1/tasks/{task_id}/sessions` | Session history | Bearer |

### GitHub PR Analytics (router dirs: `api/v1/pull_requests/`, `api/v1/repositories/`)

The scaffold's `pull_requests`/`repositories` router names now carry a different
domain than Tasks/Projects above — they serve org-scoped GitHub PR data pulled
in via the GitHub App integration, not the task-management Projects/Tasks
endpoints. Names kept as-is to preserve scaffold continuity.

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/pull-requests` | List PRs of an org | Bearer |
| GET | `/api/v1/pull-requests/{pr_id}` | PR detail with reviews | Bearer |
| GET | `/api/v1/repositories` | List repos tracked by an org | Bearer |
| PATCH | `/api/v1/repositories/{repo_id}` | Toggle repo tracking | Bearer |

### Metrics

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/metrics/summary` | Productivity summary | Bearer |
| GET | `/api/v1/metrics/velocity` | Velocity (tasks/week) | Bearer |
| GET | `/api/v1/metrics/time-tracking` | Daily work hours | Bearer |
| GET | `/api/v1/metrics/completion-rate` | % completed tasks | Bearer |
| GET | `/api/v1/metrics/estimation-accuracy` | Estimation accuracy | Bearer |
| GET | `/api/v1/metrics/streaks` | Activity streaks | Bearer |
| GET | `/api/v1/metrics/projects/{project_id}` | Project metrics | Bearer |
| GET | `/api/v1/metrics/pr-dashboard` | GitHub PR-flow KPI dashboard | Bearer |
| GET | `/api/v1/metrics/pr-dashboard/members` | Org members for the PR dashboard filter | Bearer |

### Reports

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/reports` | Generate report | Bearer |
| GET | `/api/v1/reports` | List reports | Bearer |
| GET | `/api/v1/reports/{report_id}` | Get report | Bearer |
| DELETE | `/api/v1/reports/{report_id}` | Delete report | Bearer |

### GitHub Integration

GitHub App installations (repository access, org-scoped):

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/app/install-url` | Get the App install URL | Bearer |
| POST | `/api/v1/integrations/github/app/setup` | Complete the install redirect | Bearer |
| GET | `/api/v1/integrations/github/app/installations` | List an org's installations | Bearer |
| DELETE | `/api/v1/integrations/github/app/installations/{installation_uuid}` | Disconnect an installation | Bearer |
| POST | `/api/v1/integrations/github/app/installations/{installation_uuid}/refresh-repos` | Refresh the repo pool | Bearer |
| POST | `/api/v1/integrations/github/sync` | Sync PRs of all tracked repos | Bearer |
| GET | `/api/v1/integrations/github/sync-runs` | List recent sync runs | Bearer |
| POST | `/api/v1/integrations/github/webhooks` | Webhook receiver | HMAC |

GitHub OAuth identity (personal account link, used for per-member PR attribution):

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/authorize` | Start OAuth flow | Bearer |
| GET | `/api/v1/integrations/github/callback` | OAuth callback | — |
| GET | `/api/v1/integrations/github/status` | Connection status | Bearer |
| DELETE | `/api/v1/integrations/github/disconnect` | Disconnect GitHub | Bearer |

## URL Conventions

- Resources in plural: `/tasks`, `/projects`, `/organizations`
- Resource ID in path: `/tasks/{task_id}` (UUID)
- Actions as sub-resources: `/tasks/{task_id}/start`, `/tasks/{task_id}/stop`
- Sub-collections: `/organizations/{org_id}/members`
- Query params for filtering: `?status=in_progress&priority=high`
- Pagination: `?limit=20&offset=0` (max=100). Default `limit` is 20 for `/reports`
  and 50 for `/projects`, `/tasks`, `/pull-requests`.

## Standard HTTP Status Codes

| Code | When |
|---|---|
| 200 | GET, PATCH — success |
| 201 | POST — resource created |
| 204 | DELETE — success, no body |
| 400 | Input validation error |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (e.g. email already taken) |
| 422 | Request parsing error (Pydantic) |

## List Response Format

Endpoints that accept `limit`/`offset` (`/projects`, `/tasks`, `/reports`,
`/pull-requests`) return `meta` with a real row count:

```json
{
  "data": [...],
  "meta": {
    "total": 142,
    "limit": 20,
    "offset": 0
  }
}
```

Collection endpoints without pagination (`/organizations`,
`/organizations/{id}/members`, `/tasks/{id}/sessions`, `/repositories`,
`/integrations/github/app/installations`, `/integrations/github/sync-runs`,
`/metrics/pr-dashboard/members`) omit `meta` entirely:

```json
{ "data": [...] }
```

Single-resource responses (`GET /projects/{id}`, `POST /auth/login`, ...) are
not wrapped — the resource is returned directly at the top level.

## Implementation Status

All routers listed above are fully implemented, each backed by a service and
repository layer with integration tests (see `apps/api/tests/`).
