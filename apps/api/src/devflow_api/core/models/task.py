"""Task ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


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
    github_pr_url: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
