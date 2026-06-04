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

### Projects (router: `/repositories`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/projects` | Create project | Bearer |
| GET | `/api/v1/projects` | List projects | Bearer |
| GET | `/api/v1/projects/{project_id}` | Project details | Bearer |
| PATCH | `/api/v1/projects/{project_id}` | Update project | Bearer |
| DELETE | `/api/v1/projects/{project_id}` | Archive project | Bearer |

### Tasks + Time Tracking (router: `/pull-requests`)

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

### Reports

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/reports` | Generate report | Bearer |
| GET | `/api/v1/reports` | List reports | Bearer |
| GET | `/api/v1/reports/{report_id}` | Get report | Bearer |
| DELETE | `/api/v1/reports/{report_id}` | Delete report | Bearer |

### GitHub Integration

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/integrations/github/authorize` | Start OAuth flow | Bearer |
| GET | `/api/v1/integrations/github/callback` | OAuth callback | — |
| GET | `/api/v1/integrations/github/status` | Connection status | Bearer |
| DELETE | `/api/v1/integrations/github/disconnect` | Disconnect GitHub | Bearer |
| POST | `/api/v1/integrations/github/sync` | Manual sync | Bearer |
| POST | `/api/v1/integrations/github/webhooks` | Webhook receiver | HMAC |

## URL Conventions

- Resources in plural: `/tasks`, `/projects`, `/organizations`
- Resource ID in path: `/tasks/{task_id}` (UUID)
- Actions as sub-resources: `/tasks/{task_id}/start`, `/tasks/{task_id}/stop`
- Sub-collections: `/organizations/{org_id}/members`
- Query params for filtering: `?status=in_progress&priority=high`
- Pagination: `?limit=20&offset=0` (default limit=20, max=100)

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

## Paginated Response Format

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

## Implementation Status

| Router | Status |
|---|---|
| auth | Placeholder → to be implemented |
| organizations | Placeholder → to be implemented |
| repositories (projects) | Placeholder → to be implemented |
| pull_requests (tasks) | Placeholder → to be implemented |
| metrics | Placeholder → to be implemented |
| reports | Placeholder → to be implemented |
| integrations/github | Placeholder → to be implemented |
