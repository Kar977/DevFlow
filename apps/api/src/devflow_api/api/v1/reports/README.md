# Reports Routes

Generating and retrieving productivity reports.

Reports are generated asynchronously as background tasks. After submitting a request the user receives a `report_id` and can poll for status until `status` changes to `ready`.

## Endpoints to Implement

### `POST /api/v1/reports`

Request a report to be generated.

Request:
```json
{
  "type": "weekly_summary",
  "format": "json",
  "date_from": "2025-01-20",
  "date_to": "2025-01-26"
}
```

Report types:
- `weekly_summary` — weekly summary: velocity, work hours, completed tasks
- `project_status` — project status (requires `project_id` in request)
- `productivity_overview` — broader productivity overview for a selected period

Formats:
- `json` — returned as `payload` in response
- `csv` — download link in `file_url`

Response `202 Accepted`:
```json
{
  "id": "uuid",
  "type": "weekly_summary",
  "format": "json",
  "status": "pending",
  "payload": null,
  "file_url": null,
  "generated_at": null,
  "created_at": "2025-01-27T10:00:00Z"
}
```

Generation is triggered by `FastAPI BackgroundTasks` — does not block the response.

---

### `GET /api/v1/reports`

List reports for the authenticated user.

Query params: `limit`, `offset`

Response `200 OK`:
```json
{
  "data": [
    {
      "id": "uuid",
      "type": "weekly_summary",
      "format": "json",
      "status": "ready",
      "generated_at": "2025-01-27T10:01:05Z",
      "created_at": "2025-01-27T10:00:00Z"
    }
  ],
  "meta": { "total": 12, "limit": 20, "offset": 0 }
}
```

---

### `GET /api/v1/reports/{report_id}`

Retrieve a report. When `status=ready`, `payload` or `file_url` are populated.

Response `200 OK`:
```json
{
  "id": "uuid",
  "type": "weekly_summary",
  "format": "json",
  "status": "ready",
  "payload": {
    "period": { "from": "2025-01-20", "to": "2025-01-26" },
    "tasks_completed": 9,
    "total_work_hours": 32.5,
    "velocity": 9,
    "top_projects": [ ... ]
  },
  "file_url": null,
  "generated_at": "2025-01-27T10:01:05Z"
}
```

When `status=pending` or `generating`: payload is null, client should poll again.
When `status=failed`: payload null, `error_message` explains the failure.

---

### `DELETE /api/v1/reports/{report_id}`

Delete a report.

Response `204 No Content`.
Error: `403` when the report belongs to another user.

---

## Report Lifecycle

```
POST /reports → status: "pending"
    ↓ (background task starts)
status: "generating"
    ↓ (success)
status: "ready" + payload/file_url populated
    ↓ (or failure)
status: "failed" + error_message
```

---

## Weekly Summary Payload Structure

```json
{
  "period": {
    "from": "2025-01-20",
    "to": "2025-01-26"
  },
  "tasks_completed": 9,
  "tasks_created": 12,
  "total_work_hours": 32.5,
  "work_days": 5,
  "avg_hours_per_day": 6.5,
  "velocity": 9,
  "completion_rate": 75.0,
  "top_projects": [
    { "name": "DevFlow Backend", "tasks_completed": 6 }
  ],
  "tasks": [
    {
      "id": "uuid",
      "title": "Implement auth",
      "status": "done",
      "project": "DevFlow Backend",
      "work_minutes": 210
    }
  ]
}
```

---

## Files to Create

- `routes.py` — route handlers (replace current placeholder)
- `../../../core/schemas/reports/` — `CreateReportRequest`, `ReportResponse`
- `../../../core/services/report.py` — `ReportService` + background task generator
- `../../../core/repositories/report.py` — `ReportRepository`
- `../../../core/models/report.py` — `Report` model
- Alembic migration: `reports` table
