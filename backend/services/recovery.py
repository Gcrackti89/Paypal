from __future__ import annotations
import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from backend.models.invoice import Invoice, InvoiceLocalStatus
from backend.models.recovery import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from backend.models.approval import ApprovalRequest, ApprovalAction
from backend.models.audit import AuditLog, AuditAction
from backend.core.security import generate_secure_token, hash_payload
from backend.core.exceptions import ApprovalError, RateLimitError, NotFoundError
from backend.config import settings
import json
import structlog

logger = structlog.get_logger(__name__)

# Statuses eligible for reminders
REMINDER_ELIGIBLE_PAYPAL_STATUSES = {"SENT", "UNPAID", "PARTIALLY_PAID"}
NOT_ELIGIBLE_LOCAL_STATUSES = {
    InvoiceLocalStatus.PAID.value,
    InvoiceLocalStatus.CANCELLED.value,
    InvoiceLocalStatus.REFUNDED.value,
    InvoiceLocalStatus.DRAFT.value,
}


async def run_recovery_scan(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Scan for overdue invoices and create recovery recommendations."""
    today = date.today()

    # Find sent/unpaid invoices past due date
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.user_id == user_id,
                Invoice.local_status.in_([
                    InvoiceLocalStatus.PENDING.value,
                    InvoiceLocalStatus.OVERDUE.value,
                ]),
                Invoice.due_date <= today,
                Invoice.due_date.isnot(None),
            )
        )
    )
    overdue_invoices = result.scalars().all()

    recommendations = []
    for invoice in overdue_invoices:
        # Mark as overdue if not already
        if invoice.local_status == InvoiceLocalStatus.PENDING.value:
            invoice.local_status = InvoiceLocalStatus.OVERDUE.value
            await db.flush()

        days_overdue = (today - invoice.due_date).days

        # Check if already has a pending recommendation
        existing = await db.execute(
            select(RecoveryAction).where(
                and_(
                    RecoveryAction.invoice_id == invoice.id,
                    RecoveryAction.status == RecoveryActionStatus.PENDING.value,
                    RecoveryAction.action_type == RecoveryActionType.REMINDER_PREPARED.value,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Create recommendation
        draft_msg = _draft_reminder_message(invoice, days_overdue)
        rec = RecoveryAction(
            user_id=user_id,
            invoice_id=invoice.id,
            action_type=RecoveryActionType.REMINDER_PREPARED.value,
            status=RecoveryActionStatus.PENDING.value,
            days_overdue=days_overdue,
            previous_reminders=invoice.reminder_count_total,
            recommended_action="Send payment reminder",
            draft_message=draft_msg,
        )
        db.add(rec)
        recommendations.append(rec)

    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.RECOVERY_SCAN_RUN.value,
        description=f"Recovery scan: {len(overdue_invoices)} overdue, {len(recommendations)} new recommendations",
        metadata_={"overdue_count": len(overdue_invoices), "new_recs": len(recommendations)},
    )
    db.add(audit)
    await db.commit()

    # Reload recommendations with IDs
    for rec in recommendations:
        await db.refresh(rec)

    return {
        "scanned": len(overdue_invoices),
        "overdue_found": len(overdue_invoices),
        "recommendations": recommendations,
    }


async def prepare_reminder(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
    recovery_action_id: uuid.UUID | None = None,
) -> ApprovalRequest:
    """Prepare a reminder send approval."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == user_id)
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice")

    # Check eligibility
    _check_reminder_eligibility(invoice)

    # Fetch authoritative PayPal status before proceeding
    if invoice.paypal_invoice_id and settings.paypal_configured:
        from backend.services.paypal import fetch_invoice, map_paypal_status_to_local
        try:
            pp_inv = await fetch_invoice(invoice.paypal_invoice_id)
            pp_status = pp_inv.get("status", "")
            invoice.paypal_status = pp_status
            invoice.paypal_last_synced_at = datetime.now(timezone.utc)
            local_status = map_paypal_status_to_local(pp_status)
            invoice.local_status = local_status
            await db.flush()
            # Re-check after sync
            _check_reminder_eligibility(invoice)
        except Exception as e:
            logger.warning("paypal_prefetch_failed", error=str(e))

    payload = json.dumps({"action": "SEND_REMINDER", "invoice_id": str(invoice.id)})
    token = generate_secure_token()
    from datetime import timedelta
    approval = ApprovalRequest(
        user_id=user_id,
        invoice_id=invoice.id,
        action=ApprovalAction.SEND_REMINDER.value,
        token=token,
        payload_hash=hash_payload(payload),
        payload_summary=f"Send reminder to {invoice.customer_email} for {invoice.currency} {invoice.total_amount}",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(approval)
    await db.commit()
    return approval


async def confirm_reminder(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
    approval_token: str,
) -> RecoveryAction:
    """Execute a confirmed reminder after approval."""
    from sqlalchemy.orm import selectinload
    from backend.services.invoice import _consume_approval
    from backend.services.paypal import send_reminder, fetch_invoice, map_paypal_status_to_local

    approval = await _consume_approval(db, approval_token, invoice_id, user_id, ApprovalAction.SEND_REMINDER.value)

    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == user_id)
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice")

    # Final eligibility check immediately before sending
    _check_reminder_eligibility(invoice)

    # Rate limit: max 2 reminders per invoice per day
    today = date.today()
    if invoice.reminder_count_reset_date != today:
        invoice.reminder_count_today = 0
        invoice.reminder_count_reset_date = today

    if invoice.reminder_count_today >= settings.MAX_REMINDERS_PER_INVOICE_PER_DAY:
        raise RateLimitError(f"Maximum {settings.MAX_REMINDERS_PER_INVOICE_PER_DAY} reminders per invoice per day")

    # Fetch current PayPal status as final check
    if invoice.paypal_invoice_id and settings.paypal_configured:
        pp_inv = await fetch_invoice(invoice.paypal_invoice_id)
        pp_status = pp_inv.get("status", "")
        invoice.paypal_status = pp_status
        local_status = map_paypal_status_to_local(pp_status)
        invoice.local_status = local_status
        await db.flush()
        # One more check
        _check_reminder_eligibility(invoice)

    # Send reminder
    idem_key = f"remind-{invoice.id}-{approval.id}"
    if invoice.paypal_invoice_id and settings.paypal_configured:
        await send_reminder(invoice.paypal_invoice_id, idem_key)

    # Update counts
    invoice.reminder_count_today += 1
    invoice.reminder_count_total += 1
    invoice.last_reminder_sent_at = datetime.now(timezone.utc)
    await db.flush()

    rec = RecoveryAction(
        user_id=user_id,
        invoice_id=invoice.id,
        action_type=RecoveryActionType.REMINDER_SENT.value,
        status=RecoveryActionStatus.EXECUTED.value,
        previous_reminders=invoice.reminder_count_total - 1,
        executed_at=datetime.now(timezone.utc),
        approval_request_id=approval.id,
    )
    db.add(rec)
    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.REMINDER_SENT.value,
        resource_type="invoice",
        resource_id=str(invoice.id),
        description=f"Reminder #{invoice.reminder_count_total} sent",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(rec)
    return rec


def _check_reminder_eligibility(invoice: Invoice) -> None:
    """Raise if invoice is not eligible for reminders."""
    if invoice.local_status in NOT_ELIGIBLE_LOCAL_STATUSES:
        raise ApprovalError(f"Invoice is not eligible for reminders (status: {invoice.local_status})")


def _draft_reminder_message(invoice: Invoice, days_overdue: int) -> str:
    return (
        f"Hi {invoice.customer_name},\n\n"
        f"This is a friendly reminder that invoice #{invoice.paypal_invoice_number or invoice.id} "
        f"for {invoice.currency} {invoice.total_amount} was due {days_overdue} day{'s' if days_overdue != 1 else ''} ago.\n\n"
        f"Please arrange payment at your earliest convenience.\n\n"
        f"Thank you!"
    )


async def get_recovery_queue(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list, int]:
    query = select(RecoveryAction).where(
        and_(
            RecoveryAction.user_id == user_id,
            RecoveryAction.status == RecoveryActionStatus.PENDING.value,
        )
    )
    count_query = select(func.count()).select_from(RecoveryAction).where(
        and_(
            RecoveryAction.user_id == user_id,
            RecoveryAction.status == RecoveryActionStatus.PENDING.value,
        )
    )
    total = await db.scalar(count_query)
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(RecoveryAction.created_at.desc()).offset(offset).limit(page_size))
    return result.scalars().all(), total or 0
