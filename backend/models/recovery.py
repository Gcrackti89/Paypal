from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from decimal import Decimal
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class RecoveryActionType(str, PyEnum):
    REMINDER_SENT = "REMINDER_SENT"
    REMINDER_PREPARED = "REMINDER_PREPARED"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    INVOICE_SENT = "INVOICE_SENT"
    AUTO_REMINDER_SENT = "AUTO_REMINDER_SENT"
    SCAN_DETECTED = "SCAN_DETECTED"


class RecoveryActionStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(64),
        default=RecoveryActionStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    days_overdue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_reminders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    paypal_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id"),
        nullable=True,
    )
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

    invoice = relationship("Invoice", back_populates="recovery_actions")
