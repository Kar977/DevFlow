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

### `GET /api/v1/metrics/pr-dashboard`

The Flow dashboard's 5 KPI tiles for one organization (optionally filtered to
one member's authored PRs). Computed by `PRMetricsService.get_pr_dashboard`.

Query params:
- `organization_id` — required
- `member_user_id` — optional, filters to one org member's authored PRs
  (resolved to a GitHub login). The member must belong to the same org as
  the caller — `403` if not, regardless of role; `404 member_not_linked` if
  they're a member but never connected a GitHub account.
- `date_from`, `date_to` — optional ISO dates. When **both** are omitted,
  the window defaults to the organization's current sprint (see
  `GET /organizations/{org_id}/settings`), or the plain Monday-anchored ISO
  week when no cadence is configured.

Response `200 OK` (see `PRDashboardResponse` in
`../../../core/schemas/metrics/__init__.py` for the full field-by-field
window semantics):
```json
{
  "period_from": "2026-08-17T00:00:00Z",
  "period_to": "2026-08-24T00:00:00Z",
  "stale_pr_count": 3,
  "stale_threshold_days": 5,
  "awaiting_first_review": 2,
  "time_to_first_review": 14.2,
  "time_to_first_review_prev": 19.8,
  "review_velocity": 9.1,
  "weekly_throughput": 6,
  "review_ratio": 0.71,
  "cohort_size": 7,
  "reviewed_in_cohort": 5
}
```

Key semantics that differ by field:
- `stale_pr_count` / `awaiting_first_review` are **point-in-time** — open
  PRs read against "now", not scoped to `period_from`/`period_to`.
  `stale_pr_count` measures inactivity (`max(created_at_github,
  updated_at_github, first_review_at)`), not age — an old PR that was
  reviewed yesterday is not stale.
- `time_to_first_review`, `review_ratio`, `cohort_size`, `reviewed_in_cohort`
  are computed over the **cohort** — PRs *opened* within
  `period_from`/`period_to` — the same population `/pr-trends` and
  `/org-trends` use, so this tile and those charts no longer disagree.
  `time_to_first_review_prev` is the same metric over the immediately
  preceding window of equal length, for a delta.
- `review_velocity` is a **fixed rolling 7-day** window (PRs whose *first
  review* landed in the last 7 days), independent of `period_from`/
  `period_to` — kept for parity with `/org-trends`' `review_velocity_h`
  series, which uses the same definition.
- `weekly_throughput` (PRs merged) follows `period_from`/`period_to`, unlike
  `review_velocity`.

Cached like `/pr-trends`, keyed by `org_id + author_login + date_from +
date_to + the org's cadence/threshold settings` — an admin changing the
stale threshold or sprint cadence self-heals within one TTL.

---

### `GET /api/v1/metrics/pr-trends`

Weekly-bucketed GitHub PR flow for an organization — opened/merged counts
plus review-latency trend. Backs the Dashboard's "Flow" charts.

Query params:
- `organization_id` — required
- `member_user_id` — optional, filters to one org member's authored PRs
  (resolved to a GitHub login; must belong to the same org as the caller —
  403 if not; 404 `member_not_linked` if that member has no linked GitHub
  account)
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

### `GET /api/v1/metrics/trends`

Long-range weekly history for the 4 productivity metrics (`tasks_completed`,
`active_hours`, `completion_rate`, `estimation_ratio`), backed by persisted
`metric_snapshots` rows for closed weeks — see `MetricSnapshotService`.
Unlike `/velocity` etc. (always "current vs previous period"), this covers
up to 104 weeks in one response.

Query params: `weeks` — number of weekly points to return, default 26, 2–104
(the horizon always includes the current, still-open week, computed live
and never persisted).

Response `200 OK` (see `MetricTrendsResponse` in
`../../../core/schemas/metrics/__init__.py`):
```json
{
  "period_from": "2025-08-04T00:00:00Z",
  "period_to": "2026-01-31T10:00:00Z",
  "weeks": 26,
  "series": [
    {
      "metric_key": "tasks_completed",
      "points": [
        { "week_start": "2025-08-04", "value": 5.0 },
        { "week_start": "2025-08-11", "value": 0.0 }
      ]
    }
  ]
}
```

`value: null` means "computed, no sample that week" (e.g. no task both
estimated and worked on) — distinct from `0.0`, a metric that legitimately
counted zero. Closed weeks are captured once and then immutable; a later
edit to source data does not retroactively update an already-persisted
week.

---

### `GET /api/v1/metrics/org-trends`

Same long-range mechanism as `/trends`, for 4 of the 5 PR-flow KPIs
(`pr_opened`, `pr_merged`, `review_velocity_h`, `review_ratio`).
`stale_pr_count` is excluded — it's a point-in-time reading that can't be
reconstructed for a past week from current data.

Query params:
- `organization_id` — required
- `weeks` — default 26, 2–104

For a shorter, always-live view (no persistence, ≤52 weeks) see
`/pr-trends` above — the two endpoints intentionally overlap in what they
cover; `/pr-trends` was not rewritten to read from snapshots because that
would be a breaking response-shape change for no benefit to its existing
caller (`PRDashboardTab`'s "Flow" charts).

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
