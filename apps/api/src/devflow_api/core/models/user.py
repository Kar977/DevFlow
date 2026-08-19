"""User ORM model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    # IANA zone name (e.g. "Europe/Warsaw"). NULL means "unknown" and every
    # consumer treats that as UTC — see devflow_api.core.services.period.
    timezone: Mapped[str | None] = mapped_column(String(64))
