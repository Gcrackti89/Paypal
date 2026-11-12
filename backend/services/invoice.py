from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from backend.models.invoice import Invoice, InvoiceItem, InvoiceLocalStatus
from backend.models.customer import Customer
from backend.models.approval import ApprovalRequest, ApprovalAction
from backend.models.audit import AuditLog, AuditAction
from backend.models.idempotency import IdempotencyRecord
from backend.schemas.invoice import InvoiceDraftRequest
from backend.core.security import generate_secure_token, hash_payload
from backend.core.exceptions import (
    NotFoundError, AuthorizationError, ApprovalError,
    PayPalError, PayPalNotConfiguredError, DuplicateError
)
from backend.config import settings
import structlog

logger = structlog.get_logger(__name__)


async def create_invoice_draft(
    db: AsyncSession,
    user_id: uuid.UUID,
    req: InvoiceDraftRequest,
) -> Invoice:
    # Compute totals with Decimal (never trust client-side totals)
    total = Decimal("0")
    items_data = []
    for item in req.line_items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        amount = qty * price
        total += amount
        items_data.append({"description": item.description, "quantity": qty, "unit_price": price, "amount": amount})

    # Upsert customer
    result = await db.execute(
        select(Customer).where(and_(Customer.user_id == user_id, Customer.email == req.customer_email.lower()))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            user_id=user_id,
            name=req.customer_name,
            email=req.customer_email.lower(),
        )
        db.add(customer)
        await db.flush()

    invoice = Invoice(
        user_id=user_id,
        customer_id=customer.id,
        customer_name=req.customer_name,
        customer_email=req.customer_email.lower(),
        currency=req.currency,
        total_amount=total,
        amount_due=total,
        local_status=InvoiceLocalStatus.DRAFT.value,
        due_date=req.due_date,
        invoice_date=date.today(),
        note=req.note,
        memo=req.memo,
        ai_created=req.ai_created,
        ai_session_id=req.ai_session_id,
    )
    db.add(invoice)
    await db.flush()

    for item_data in items_data:
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=item_data["description"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            amount=item_data["amount"],
        )
        db.add(item)

    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.INVOICE_DRAFT_CREATED.value,
        resource_type="invoice",
        resource_id=str(invoice.id),
        description=f"Draft invoice created for {req.customer_email}, total {req.currency} {total}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def get_invoice(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Invoice:
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(and_(Invoice.id == invoice_id, Invoice.user_id == user_id))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice")
    return invoice


async def list_invoices(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    search: str | None = None,
) -> tuple[List[Invoice], int]:
    query = select(Invoice).options(selectinload(Invoice.items)).where(Invoice.user_id == user_id)
    count_query = select(func.count()).select_from(Invoice).where(Invoice.user_id == user_id)

    if status_filter:
        query = query.where(Invoice.local_status == status_filter)
        count_query = count_query.where(Invoice.local_status == status_filter)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Invoice.customer_name.ilike(search_term),
                Invoice.customer_email.ilike(search_term),
                Invoice.paypal_invoice_number.ilike(search_term),
            )
        )
        count_query = count_query.where(
            or_(
                Invoice.customer_name.ilike(search_term),
                Invoice.customer_email.ilike(search_term),
                Invoice.paypal_invoice_number.ilike(search_term),
            )
        )

    total = await db.scalar(count_query)
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(Invoice.created_at.desc()).offset(offset).limit(page_size))
    return result.scalars().all(), total or 0


async def prepare_send_invoice(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ApprovalRequest:
    invoice = await get_invoice(db, invoice_id, user_id)
    if invoice.local_status != InvoiceLocalStatus.DRAFT.value:
        raise ApprovalError(f"Invoice cannot be sent in status: {invoice.local_status}")
    if not settings.paypal_configured:
        raise PayPalNotConfiguredError()

    from backend.services.paypal import create_draft_invoice

    items = []
    for item in invoice.items:
        items.append({"description": item.description, "quantity": str(item.quantity), "unit_price": str(item.unit_price)})

    # Create PayPal draft if not already created
    if not invoice.paypal_invoice_id:
        idem_key = f"create-{invoice.id}"
        pp_resp = await create_draft_invoice(
            customer_name=invoice.customer_name,
            customer_email=invoice.customer_email,
            line_items=items,
            currency=invoice.currency,
            due_date_str=invoice.due_date.isoformat() if invoice.due_date else None,
            note=invoice.note,
            memo=invoice.memo,
            idempotency_key=idem_key,
        )
        invoice.paypal_invoice_id = pp_resp.get("id") or pp_resp.get("href", "").split("/")[-1]
        invoice.paypal_invoice_number = pp_resp.get("detail", {}).get("invoice_number")
        await db.flush()

    # Create approval token
    payload = json.dumps({"action": "SEND_INVOICE", "invoice_id": str(invoice.id), "paypal_id": invoice.paypal_invoice_id})
    token = generate_secure_token()
    from datetime import timedelta
    approval = ApprovalRequest(
        user_id=user_id,
        invoice_id=invoice.id,
        action=ApprovalAction.SEND_INVOICE.value,
        token=token,
        payload_hash=hash_payload(payload),
        payload_summary=f"Send invoice to {invoice.customer_email} for {invoice.currency} {invoice.total_amount}",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(approval)
    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.APPROVAL_CREATED.value,
        resource_type="invoice",
        resource_id=str(invoice.id),
        description=f"Send invoice approval created",
    )
    db.add(audit)
    await db.commit()
    return approval


async def confirm_send_invoice(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
    approval_token: str,
) -> Invoice:
    from backend.services.paypal import send_invoice, fetch_invoice

    # Validate approval
    approval = await _consume_approval(db, approval_token, invoice_id, user_id, ApprovalAction.SEND_INVOICE.value)
    invoice = await get_invoice(db, invoice_id, user_id)

    if invoice.local_status != InvoiceLocalStatus.DRAFT.value:
        raise ApprovalError(f"Invoice already in status: {invoice.local_status}")

    # Send via PayPal
    idem_key = f"send-{invoice.id}-{approval.id}"
    await send_invoice(invoice.paypal_invoice_id, idem_key)

    # Fetch authoritative status
    pp_inv = await fetch_invoice(invoice.paypal_invoice_id)
    pp_status = pp_inv.get("status", "SENT")

    from backend.services.paypal import map_paypal_status_to_local
    invoice.local_status = map_paypal_status_to_local(pp_status)
    invoice.paypal_status = pp_status
    invoice.sent_at = datetime.now(timezone.utc)
    invoice.paypal_last_synced_at = datetime.now(timezone.utc)

    # Try to get invoice URL from PayPal response
    detail = pp_inv.get("detail", {})
    if detail.get("metadata", {}).get("recipient_view_url"):
        invoice.paypal_invoice_url = detail["metadata"]["recipient_view_url"]

    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.INVOICE_SENT.value,
        resource_type="invoice",
        resource_id=str(invoice.id),
        description=f"Invoice sent to {invoice.customer_email}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def _consume_approval(
    db: AsyncSession,
    token: str,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
    action: str,
) -> ApprovalRequest:
    result = await db.execute(
        select(ApprovalRequest).where(
            and_(
                ApprovalRequest.token == token,
                ApprovalRequest.user_id == user_id,
                ApprovalRequest.invoice_id == invoice_id,
                ApprovalRequest.action == action,
                ApprovalRequest.is_consumed == False,
                ApprovalRequest.expires_at > datetime.now(timezone.utc),
            )
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise ApprovalError("Approval token is invalid, expired, or already used")

    # Consume it atomically
    approval.is_consumed = True
    approval.consumed_at = datetime.now(timezone.utc)
    await db.flush()

    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.APPROVAL_CONSUMED.value,
        resource_type="approval_request",
        resource_id=str(approval.id),
        description=f"Approval consumed for action: {action}",
    )
    db.add(audit)
    return approval
