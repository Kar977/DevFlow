# Metrics Routes

Endpoints for retrieving developer productivity metrics.

Metrics are computed by `MetricsService` from data in the `tasks` and `work_sessions` tables.
Require a working tasks module with data.

## Endpoints to Implement

### `GET /api/v1/metrics/summary`

Full productivity summary for a selected period.

Query params:
- `date_from` — ISO 8601 date (default: 30 days ago)
- `date_to` — ISO 8601 date (default: today)

Response `200 OK`:
```json
{
  "velocity": {
    "value": 8.5,
    "previous_value": 6.0,
    "delta_percent": 41.7
  },
  "completion_rate": {
    "value": 72.3,
    "previous_value": 68.0,
    "delta_percent": 6.3
  },
  "active_hours_per_day": {
    "value": 5.2,
    "previous_value": 4.8,
    "delta_percent": 8.3
  },
  "current_streak": 7,
  "date_from": "2025-01-01",
  "date_to": "2025-01-31"
}
```

`previous_value` and `delta_percent` are computed against the equivalent preceding period (e.g. if `date_from/to` = last 30 days, previous = the 30 days before that).

---

### `GET /api/v1/metrics/velocity`

Number of completed tasks per week (last N weeks).

Query params:
- `weeks` — number of weeks to look back (default 8, max 52)

Response `200 OK`:
```json
{
  "current_week": 9,
  "trend": "up",
  "data": [
    { "week_start": "2025-01-06", "tasks_completed": 7 },
    { "week_start": "2025-01-13", "tasks_completed": 9 },
    { "week_start": "2025-01-20", "tasks_completed": 11 }
  ]
}
```

`trend`: `up` when the last 3 weeks are increasing, `down` when decreasing, `stable` otherwise.

---

### `GET /api/v1/metrics/time-tracking`

Daily active work hours (sum of `WorkSession.duration_minutes` per day).

Query params:
- `date_from`, `date_to`

Response `200 OK`:
```json
{
  "total_hours": 87.5,
  "data": [
    { "date": "2025-01-06", "minutes": 320 },
    { "date": "2025-01-07", "minutes": 195 }
  ]
}
```

Days with no sessions are not returned (sparse data).

---

### `GET /api/v1/metrics/completion-rate`

Percentage of tasks completed in a given period.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "value": 72.3,
  "done_count": 47,
  "total_count": 65,
  "breakdown": {
    "done": 47,
    "cancelled": 5,
    "open": 13
  }
}
```

Formula: `done / (done + cancelled + open) * 100`

---

### `GET /api/v1/metrics/estimation-accuracy`

Accuracy of task time estimates.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "ratio": 1.23,
  "category": "under_estimated",
  "tasks_analyzed": 18,
  "breakdown": {
    "accurate": 10,
    "under_estimated": 6,
    "over_estimated": 2
  }
}
```

Categories:
- `accurate`: ratio 0.8–1.2 (actual time within ±20% of estimate)
- `under_estimated`: ratio > 1.2 (took longer than planned)
- `over_estimated`: ratio < 0.8 (took less than planned)

Calculated only for tasks with `status=done` and a filled `estimate_minutes`.

---

### `GET /api/v1/metrics/streaks`

Activity streaks — consecutive days with at least 1 completed task.

Response `200 OK`:
```json
{
  "current_streak": 7,
  "longest_streak": 15,
  "streak_start": "2025-01-20"
}
```

---

### `GET /api/v1/metrics/projects/{project_id}`

Metrics for a specific project.

Query params: `date_from`, `date_to`

Response `200 OK`:
```json
{
  "project_id": "uuid",
  "total_tasks": 42,
  "open_tasks": 15,
  "overdue_tasks": 3,
  "completion_rate": 64.2,
  "health_status": "at_risk",
  "velocity": { ... },
  "time_spent_hours": 156.5
}
```

`health_status`: `healthy` (<10% overdue), `at_risk` (10–30%), `critical` (>30%).

---

## Caching

Metrics queries are expensive — aggregations over many rows. Results must be cached.

**Cache key:** `metrics:{user_id}:{endpoint}:{date_from}:{date_to}`

**TTL:** 5 minutes (short because the user may have just closed a task and want to see the effect)

Implementation:
- Stage 1: in-memory dict in `MetricsService` with `datetime` expiry
- Stage 2: Redis (once Redis is added to the infrastructure)

Cache should be invalidated when:
- A task is closed (`status` → `done`)
- A work session ends (`WorkSession.stop`)

---

## Files to Create

- `routes.py` — route handlers (replace current placeholder)
- `../../../core/schemas/metrics/` — response schemas (described in `core/schemas/README.md`)
- `../../../core/services/metrics.py` — `MetricsService`
- No new models/repositories — `MetricsService` uses `TaskRepository` and `WorkSessionRepository`
