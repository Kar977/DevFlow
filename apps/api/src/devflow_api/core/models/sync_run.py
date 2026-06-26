"""SyncRun ORM model — tracks each GitHub sync execution."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    prs_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
