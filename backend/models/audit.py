from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class AuditAction(str, PyEnum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGGED_IN = "USER_LOGGED_IN"
    USER_LOGGED_OUT = "USER_LOGGED_OUT"
    INVOICE_CREATED = "INVOICE_CREATED"
    INVOICE_DRAFT_CREATED = "INVOICE_DRAFT_CREATED"
    INVOICE_SENT = "INVOICE_SENT"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    INVOICE_STATUS_UPDATED = "INVOICE_STATUS_UPDATED"
    REMINDER_PREPARED = "REMINDER_PREPARED"
    REMINDER_SENT = "REMINDER_SENT"
    REMINDER_SKIPPED = "REMINDER_SKIPPED"
    APPROVAL_CREATED = "APPROVAL_CREATED"
    APPROVAL_CONSUMED = "APPROVAL_CONSUMED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    WEBHOOK_PROCESSED = "WEBHOOK_PROCESSED"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    RECOVERY_SCAN_RUN = "RECOVERY_SCAN_RUN"
    AI_COMMAND = "AI_COMMAND"
    PAYPAL_API_CALL = "PAYPAL_API_CALL"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user = relationship("User", back_populates="audit_logs")
