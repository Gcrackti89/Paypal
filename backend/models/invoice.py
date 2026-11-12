from __future__ import annotations
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import (
    String, DateTime, Date, ForeignKey, Numeric, Integer,
    Text, Enum, Boolean, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class InvoiceStatus(str, PyEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    SCHEDULED = "SCHEDULED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    UNPAID = "UNPAID"
    MARKED_AS_PAID = "MARKED_AS_PAID"
    MARKED_AS_REFUNDED = "MARKED_AS_REFUNDED"


class InvoiceLocalStatus(str, PyEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"       # Sent, awaiting payment
    OVERDUE = "OVERDUE"       # Past due date, unpaid
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_user_id_status", "user_id", "local_status"),
        Index("ix_invoices_user_id_due_date", "user_id", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # PayPal fields
    paypal_invoice_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    paypal_invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_invoice_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    paypal_payment_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    paypal_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Invoice details
    local_status: Mapped[str] = mapped_column(
        String(64),
        default=InvoiceLocalStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    amount_due: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)

    # Customer info (denormalized for history)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reminder tracking
    reminder_count_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reminder_count_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # AI metadata
    ai_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

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
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    recovery_actions = relationship("RecoveryAction", back_populates="invoice", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    invoice = relationship("Invoice", back_populates="items")
