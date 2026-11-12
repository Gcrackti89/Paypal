from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class MerchantSettings(Base):
    __tablename__ = "merchant_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    auto_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_days_before_due: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reminder_quiet_hours_start: Mapped[int] = mapped_column(Integer, default=22, nullable=False)  # hour 0-23
    reminder_quiet_hours_end: Mapped[int] = mapped_column(Integer, default=8, nullable=False)  # hour 0-23
    reminder_days_after_due: Mapped[list] = mapped_column(JSON, default=lambda: [1, 3, 7], nullable=False)
    paypal_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paypal_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="merchant_settings")
