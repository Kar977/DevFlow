# Reports Routes

Generating and retrieving productivity reports.

Reports are generated asynchronously as background tasks. After submitting a request the user receives a `report_id` and can poll for status until `status` changes to `ready`.

## Endpoints

### `POST /api/v1/reports`

Request a report to be generated.

Request:
```json
{
  "type": "weekly_summary",
  "format": "json",
  "date_from": "2025-01-20T00:00:00Z",
  "date_to": "2025-01-26T00:00:00Z"
}
```

Report types:
- `weekly_summary` — weekly summary: velocity, work hours, completed tasks
- `project_status` — project health metrics (requires `project_id` in request)
- `productivity_overview` — broader productivity overview for a selected period

Formats:
- `json` — returned as `payload` in the response when ready

Response `202 Accepted`:
```json
{
  "id": "uuid",
  "type": "weekly_summary",
  "format": "json",
  "status": "pending",
  "payload": null,
  "error_message": null,
  "generated_at": null,
  "created_at": "2025-01-27T10:00:00Z"
}
```

Generation is triggered by `FastAPI BackgroundTasks` — does not block the response.

---

### `GET /api/v1/reports`

List reports for the authenticated user.

Query params: `limit` (default 20, max 100), `offset` (default 0)

Response `200 OK`:
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "weekly_summary",
      "format": "json",
      "status": "ready",
      "generated_at": "2025-01-27T10:01:05Z",
      "created_at": "2025-01-27T10:00:00Z"
    }
  ],
  "total": 12
}
```

---

### `GET /api/v1/reports/{report_id}`

Retrieve a report. When `status=ready`, `payload` is populated.

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
    "completion_rate": 75.0,
    "work_days": 5,
    "avg_hours_per_day": 6.5
  },
  "error_message": null,
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
status: "ready" + payload populated
    ↓ (or failure)
status: "failed" + error_message
```

---

## Files

- `routes.py` — route handlers
- `../../../core/schemas/reports/` — `CreateReportRequest`, `ReportResponse`, `ReportListResponse`
- `../../../core/services/report.py` — `ReportService` + `run_report_generation` background generator
- `../../../core/repositories/report.py` — `ReportRepository`
- `../../../core/models/report.py` — `Report` model
