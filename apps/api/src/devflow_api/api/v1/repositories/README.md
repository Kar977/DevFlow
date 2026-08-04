# Projects Routes

The `repositories` router handles the **developer projects** domain.

A project is a container for tasks. It can be personal (no `org_id`) or belong to an organization.
Optionally linked to a GitHub repository via `github_repo_url`.

## Endpoints to Implement

### `POST /api/v1/projects`

Create a new project.

Request:
```json
{
  "name": "DevFlow Backend",
  "description": "API for DevFlow Insight",
  "org_id": "uuid-or-null",
  "github_repo_url": "https://github.com/owner/repo"
}
```

Response `201 Created`:
```json
{
  "id": "uuid",
  "name": "DevFlow Backend",
  "description": "API for DevFlow Insight",
  "status": "active",
  "org_id": null,
  "github_repo_url": "https://github.com/owner/repo",
  "created_at": "2025-01-01T10:00:00Z"
}
```

If `org_id` is provided, the service verifies that the user is a member of that org.

---

### `GET /api/v1/projects`

List the user's projects (personal + from orgs they belong to).

Query params:
- `org_id` — filter by organization
- `status` — `active` | `archived` (default: `active`)
- `limit` — (default 20, max 100)
- `offset`

Response `200 OK`:
```json
{
  "data": [ { ...ProjectResponse } ],
  "meta": { "total": 5, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/projects/{project_id}`

Project details with task statistics.

Response `200 OK`:
```json
{
  "id": "uuid",
  "name": "DevFlow Backend",
  "status": "active",
  "stats": {
    "total_tasks": 42,
    "open_tasks": 15,
    "overdue_tasks": 3,
    "completion_rate": 64.2
  },
  ...
}
```

---

### `PATCH /api/v1/projects/{project_id}`

Update project. All fields optional.

Request: `UpdateProjectRequest`.
Response `200 OK`: updated `ProjectResponse`.

---

### `DELETE /api/v1/projects/{project_id}`

Archive the project (sets `status` to `archived`, does not delete from DB).
Project tasks remain intact.

Response `204 No Content`.

---

## Implementation Status

Implemented — see `routes.py`, `../../../core/schemas/projects/`
(`CreateProjectRequest`, `UpdateProjectRequest`, `ProjectResponse`),
`../../../core/services/project.py` (`ProjectService`),
`../../../core/repositories/project.py` (`ProjectRepository`),
`../../../core/models/project.py`, and Alembic migration `0003_create_projects.py`.

**Not yet implemented:** `ProjectStatsResponse` — `GET /projects/{id}` does not
return a nested `stats` object (total/open/overdue task counts).

## URL Naming Note

The endpoint URL is `/api/v1/projects`, but the router directory in code (`api/v1/repositories/`) keeps its original name for scaffold continuity. Change the router prefix in `routes.py`:

```python
router = APIRouter(prefix="/projects", tags=["Projects"])
```
