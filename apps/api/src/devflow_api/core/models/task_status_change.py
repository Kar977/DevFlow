"""TaskStatusChange ORM model — an audit trail of Task.status transitions."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import UUIDPrimaryKeyMixin


class TaskStatusChange(UUIDPrimaryKeyMixin, Base):
    """One recorded transition of `Task.status`.

    Written exclusively by `TaskService` (on task creation and on every real
    status change in `update_task`) — never by a repository directly. `Task`
    itself has no relationship() back to this table; traversal is via an
    explicit join, matching the rest of this package.

    `from_status` is `None` in two distinct cases: the row recorded a task's
    creation (there was no prior status), or the row was produced by the
    0017 migration backfill for pre-existing tasks (the real prior status is
    unknown). `changed_by` is `None` for backfilled rows for the same reason
    — no caller was recorded at the time.
    """

    __tablename__ = "task_status_changes"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Backs both a future "history for this task" endpoint and a future
        # cycle-time-per-stage metric — both read in changed_at order.
        Index("ix_task_status_changes_task_id_changed_at", "task_id", "changed_at"),
    )
