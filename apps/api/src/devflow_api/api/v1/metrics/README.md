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

Number of tasks completed in the selected period, plus a zero-filled
per-week breakdown of that same period.

Query params:
- `date_from`, `date_to` — ISO 8601 datetimes (default: last 30 days)

Response `200 OK` (actual shape — see `VelocityResponse` in
`../../../core/schemas/metrics/__init__.py`):
```json
{
  "period_from": "2025-01-01T00:00:00Z",
  "period_to": "2025-01-31T00:00:00Z",
  "total_done": 27,
  "weeks": 4.43,
  "average_per_week": 6.09,
  "trend_pct": 12.5,
  "weekly": [
    { "week_start": "2025-01-06", "tasks_completed": 7 },
    { "week_start": "2025-01-13", "tasks_completed": 9 },
    { "week_start": "2025-01-20", "tasks_completed": 11 }
  ]
}
```

`weeks` is the length of the requested period in weeks (a float), **not** a
series — the per-week series is `weekly`. Every ISO week (Monday-anchored,
UTC) in `[period_from, period_to]` gets an entry, zero-filled when empty, so
`sum(p.tasks_completed for p in weekly) == total_done`.

---

### `GET /api/v1/metrics/time-tracking`

Daily active work hours (sum of `WorkSession.duration_seconds` per day).

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

### `GET /api/v1/metrics/pr-trends`

Weekly-bucketed GitHub PR flow for an organization — opened/merged counts
plus review-latency trend. Backs the Dashboard's "Flow" charts.

Query params:
- `organization_id` — required
- `member_user_id` — optional, filters to one org member's authored PRs
  (resolved to a GitHub login; 404 `member_not_linked` if that member has no
  linked GitHub account)
- `weeks` — number of ISO weeks to look back, default 12, 1–52

Response `200 OK` (see `PRTrendsResponse` in
`../../../core/schemas/metrics/__init__.py`):
```json
{
  "period_from": "2025-01-06T00:00:00Z",
  "period_to": "2025-01-31T10:00:00Z",
  "weekly": [
    { "week_start": "2025-01-06", "opened": 5, "merged": 4, "avg_time_to_first_review_h": 6.2 },
    { "week_start": "2025-01-13", "opened": 3, "merged": 2, "avg_time_to_first_review_h": null }
  ]
}
```

`opened` buckets by `created_at_github`; `merged` buckets by `merged_at`
(only PRs with `state == "merged"`). `avg_time_to_first_review_h` is a
**cohort** reading — the average review-wait of PRs *opened* in that week,
not reviewed in that week — so the most recent 1-2 weeks can look faster
than they really are, since slow-to-review PRs there have not been reviewed
yet. Cached like the other endpoints, keyed by
`org_id + author_login + weeks` (not `user_id` — the payload is identical
for every member).

---

## Caching

Metrics queries are expensive — aggregations over many rows. Results must be cached.

**Cache key:** `metrics:{user_id}:{endpoint}:{date_from}:{date_to}`

**TTL:** 60 seconds (`DEVFLOW_API_METRICS_CACHE_TTL_SECONDS`, `../../../core/config.py`).

Implementation: `../../../core/cache.py` — `CacheBackend` Protocol with
`InMemoryCache` (default) and `RedisCache` (used when
`DEVFLOW_API_REDIS_URL` is set; Redis is available in
`infra/docker-compose.yml`).

**Not yet implemented:** invalidation on write (task closed, work session
stopped) — the cache currently relies on TTL expiry only, so metrics can lag
up to 60 seconds behind a just-completed action.

---

## Implementation Status

Implemented — see `routes.py`, `../../../core/schemas/metrics/`, and
`../../../core/services/metrics.py` (`MetricsService`). No dedicated model or
repository — `MetricsService` reads through `TaskRepository` and
`WorkSessionRepository`.
