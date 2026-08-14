"""Task ORM model."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin

# Statuses that mean a task can never be "overdue", regardless of due_date:
# a done task is finished, a cancelled one was deliberately dropped. Shared by
# TaskRepository (count/list overdue queries) and MetricsService (project
# health) so the definition can't drift between the two call sites again.
OVERDUE_EXCLUDED_STATUSES: Final[tuple[str, str]] = ("done", "cancelled")


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of work within a project."""

    __tablename__ = "tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="backlog")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    estimate_minutes: Mapped[int | None] = mapped_column(Integer)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once by TaskService.update_task when status transitions into "done"
    # (and cleared if it later transitions back out) — never written directly
    # by the repository or client-supplied. Falls back to `updated_at` in
    # MetricsService for rows written before this column existed.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    github_pr_url: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    __table_args__ = (
        # Supports the org-wide "my overdue tasks" query (filter by
        # assignee_id, sort by due_date) — see TaskRepository.list_overdue_for_user.
        Index("ix_tasks_assignee_id_due_date", "assignee_id", "due_date"),
    )
