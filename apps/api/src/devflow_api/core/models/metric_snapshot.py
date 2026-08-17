"""MetricSnapshot ORM model — persisted weekly values for long-range trends.

Every metric in this codebase today (`MetricsService`, `PRMetricsService`) is
computed on the fly from raw rows for a "current vs previous period" window.
That's fine for a 30-day dashboard but doesn't scale to a 6-12 month trend
chart, and there is no way to see a horizon longer than "this period vs the
last one". This table stores one row per *closed* ISO week (Monday-anchored,
UTC) per metric, written lazily by `MetricSnapshotService` the first time a
trend endpoint is asked to cover that week — see that module for the backfill
algorithm. There is no scheduler in this codebase (no APScheduler/Celery/cron,
just FastAPI `BackgroundTasks`), so a proactive nightly job was ruled out for
this iteration.

Design notes
------------
- Generic across both metric domains: ``scope="user"`` for the 4
  productivity metrics (`MetricsService`), ``scope="org"`` for 4 of the 5
  PR-flow KPIs (`PRMetricsService`). ``stale_pr_count`` is deliberately
  excluded — it's a point-in-time reading ("how many PRs are stale *right
  now*") that can't be reconstructed for a past week from current data, so a
  lazy backfill has nothing correct to write.
- A row's presence means "this week was computed", independent of its value:
  ``metric_value`` is nullable because some KPIs (`review_velocity_h`,
  `estimation_ratio`, ...) are legitimately undefined when there's no
  sample in that week. Counting metrics store ``0.0``, not ``NULL``, for an
  empty week.
- Closed weeks are immutable once written — a later edit to the source data
  (e.g. a task's `completed_at` changing after the fact) does not update an
  already-captured snapshot. The escape hatch is
  `MetricSnapshotService.recompute_user_trends` (``POST
  /metrics/trends/recompute``), which deletes and lets the normal lazy
  backfill rewrite. User scope only — see that service's docstring.
- User-scope rows bucket by the user's own local time, not UTC — a stored
  `timezone` on `User` shifts the week grid; org scope stays UTC-anchored.
  See `devflow_api.core.services.period` and
  `devflow_api.core.services.metric_snapshot`.
- No `repository_id` column: no KPI is computed per-repository today, and
  nothing would read it. Adding a nullable column later is a small migration
  if that need arises — see `docs/reconciliation-report.md` item 5.
- Append-only, so this uses `UUIDPrimaryKeyMixin` only (not `TimestampMixin`)
  with its own `captured_at`, matching `TaskStatusChange`.
"""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import UUIDPrimaryKeyMixin

# Metric keys captured per scope. Shared with MetricSnapshotService so the
# set of keys backfilled for a week can't drift from what a trend response
# advertises in `series`.
USER_METRIC_KEYS: Final[tuple[str, ...]] = (
    "tasks_completed",
    "active_hours",
    "completion_rate",
    "estimation_ratio",
)
ORG_METRIC_KEYS: Final[tuple[str, ...]] = (
    "pr_opened",
    "pr_merged",
    "review_velocity_h",
    "review_ratio",
)


class MetricSnapshot(UUIDPrimaryKeyMixin, Base):
    """One metric's value for one closed ISO week, for one user or org."""

    __tablename__ = "metric_snapshots"

    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    metric_key: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metric_value: Mapped[float | None] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(scope = 'user' AND user_id IS NOT NULL AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL AND user_id IS NULL)",
            name="ck_metric_snapshots_scope_matches_owner",
        ),
        # Plain UNIQUE would let NULL user_id/org_id values duplicate freely
        # (SQL treats NULL <> NULL), so scope-specific partial indexes are
        # used instead — one per scope, matching the 0013 partial-unique-index
        # precedent. Backs both the write-time on_conflict_do_nothing() and
        # the read-time "one row per (owner, metric, week)" query.
        Index(
            "uq_metric_snapshots_user_metric_week",
            "user_id",
            "metric_key",
            "period_start",
            unique=True,
            postgresql_where=text("scope = 'user'"),
        ),
        Index(
            "uq_metric_snapshots_org_metric_week",
            "org_id",
            "metric_key",
            "period_start",
            unique=True,
            postgresql_where=text("scope = 'org'"),
        ),
        # Backs MetricSnapshotService's per-owner trend read (fetch every
        # captured week for this user/org across all metric keys at once).
        Index("ix_metric_snapshots_user_id_period_start", "user_id", "period_start"),
        Index("ix_metric_snapshots_org_id_period_start", "org_id", "period_start"),
    )
