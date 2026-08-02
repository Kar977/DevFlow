# Tasks Routes

The `pull_requests` router handles the **tasks and time tracking** domain.

A task is the fundamental unit of work. It can be created manually or imported from GitHub (PR/Issue).
Each task supports a work timer for time tracking.

## Endpoints to Implement

### `POST /api/v1/tasks`

Create a new task.

Request:
```json
{
  "title": "Implement auth module",
  "description": "JWT-based auth with refresh tokens",
  "project_id": "uuid-or-null",
  "priority": "high",
  "estimate_minutes": 240,
  "assignee_id": "uuid-or-null",
  "due_date": "2025-02-01"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "title": "Implement auth module",
  "status": "backlog",
  "priority": "high",
  "estimate_minutes": 240,
  "assignee_id": null,
  "project_id": "uuid",
  "due_date": "2025-02-01",
  "source": "manual",
  "github_url": null,
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2025-01-01T10:00:00Z"
}
```

---

### `GET /api/v1/tasks`

List tasks with filtering and pagination.

Query params:
- `project_id` — filter by project
- `status` — `backlog` | `todo` | `in_progress` | `review` | `done` | `cancelled`
- `priority` — `low` | `medium` | `high` | `critical`
- `assignee_id` — filter by assignee
- `limit` (default 20, max 100)
- `offset`

Response `200 OK`:
```json
{
  "data": [ { ...TaskResponse } ],
  "meta": { "total": 37, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/tasks/{task_id}`

Task details.

Response `200 OK`: `TaskResponse`.
Error: `404` when not found or user has no access.

---

### `PATCH /api/v1/tasks/{task_id}`

Update a task. Only the fields the user wants to change (PATCH semantics).

Request: `UpdateTaskRequest` (all fields optional).
Response `200 OK`: updated `TaskResponse`.

Example — change status:
```json
{ "status": "in_progress" }
```

---

### `DELETE /api/v1/tasks/{task_id}`

Delete task (hard delete). Also deletes associated `WorkSession` records.

Response `204 No Content`.

---

### `POST /api/v1/tasks/{task_id}/start`

Start a work session on the task (start the timer).

- If the user already has an active session on a **different** task: `409 Conflict` with information about which task is active.
- If the task has status `backlog` or `todo`: automatically change to `in_progress`.

Response `201 Created`:
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "started_at": "2025-01-01T10:00:00Z",
  "ended_at": null,
  "duration_minutes": null
}
```

---

### `POST /api/v1/tasks/{task_id}/stop`

Stop the active work session (stop the timer).

- `duration_minutes` calculated automatically: `(ended_at - started_at).seconds // 60`
- Minimum 1 minute (sessions under 1 min are recorded as 1 min)

Response `200 OK`:
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "started_at": "2025-01-01T10:00:00Z",
  "ended_at": "2025-01-01T12:30:00Z",
  "duration_minutes": 150
}
```

Error: `404` when there is no active session for this task and user.

---

### `GET /api/v1/tasks/{task_id}/sessions`

Work session history for the task.

Response `200 OK`:
```json
{
  "data": [
    {
      "id": "uuid",
      "started_at": "2025-01-01T10:00:00Z",
      "ended_at": "2025-01-01T12:30:00Z",
      "duration_minutes": 150
    }
  ],
  "total_minutes": 310
}
```

---

## Task Status Transitions

```
backlog → todo → in_progress → review → done
                      ↓                   ↓
                  cancelled           cancelled
```

The service does not strictly enforce transitions — a user can set any status directly (e.g. backlog → done).

**Not yet implemented:** the planned `source: 'github_pr' | 'github_issue'` field for
auto-synced status — `Task` currently only has a free-text `github_pr_url` column,
not a `source` enum, so GitHub-origin tasks are not distinguished from manual ones.

---

## Implementation Status

Implemented — see `routes.py`, `../../../core/schemas/tasks/`
(`CreateTaskRequest`, `UpdateTaskRequest`, `TaskResponse`, `WorkSessionResponse`),
`../../../core/services/task.py` (`TaskService`),
`../../../core/repositories/task.py` (`TaskRepository`),
`../../../core/repositories/work_session.py` (`WorkSessionRepository`),
`../../../core/models/task.py`, `../../../core/models/work_session.py`,
and Alembic migration `0004_create_tasks_and_work_sessions.py`.

## URL Naming Note

Change the router prefix in `routes.py`:

```python
router = APIRouter(prefix="/tasks", tags=["Tasks"])
```
