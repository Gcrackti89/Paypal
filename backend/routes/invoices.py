from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.core.exceptions import AppException
from backend.services.invoice import (
    create_invoice_draft, get_invoice, list_invoices,
    prepare_send_invoice, confirm_send_invoice,
)
from backend.services.recovery import prepare_reminder, confirm_reminder
from backend.schemas.invoice import InvoiceDraftRequest, InvoiceResponse, InvoiceListResponse
from backend.schemas.recovery import ApprovalRequestResponse, ReminderConfirmRequest, SendInvoiceConfirmRequest
from datetime import datetime, timezone

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/drafts", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    req: InvoiceDraftRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        invoice = await create_invoice_draft(db, current_user.id, req)
        return _invoice_response(invoice)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("", response_model=InvoiceListResponse)
async def list_invoices_route(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        invoices, total = await list_invoices(db, current_user.id, page, page_size, status_filter, search)
        return InvoiceListResponse(
            items=[_invoice_response(inv) for inv in invoices],
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice_route(
    invoice_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        invoice = await get_invoice(db, invoice_id, current_user.id)
        return _invoice_response(invoice)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{invoice_id}/send/prepare", response_model=ApprovalRequestResponse)
async def prepare_send(
    invoice_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        approval = await prepare_send_invoice(db, invoice_id, current_user.id)
        return ApprovalRequestResponse(
            approval_token=approval.token,
            action=approval.action,
            payload_summary=approval.payload_summary or "",
            expires_at=approval.expires_at,
            invoice_id=str(approval.invoice_id),
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{invoice_id}/send/confirm", response_model=InvoiceResponse)
async def confirm_send(
    invoice_id: uuid.UUID,
    req: SendInvoiceConfirmRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        invoice = await confirm_send_invoice(db, invoice_id, current_user.id, req.approval_token)
        return _invoice_response(invoice)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{invoice_id}/reminders/prepare", response_model=ApprovalRequestResponse)
async def prepare_reminder_route(
    invoice_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        approval = await prepare_reminder(db, invoice_id, current_user.id)
        return ApprovalRequestResponse(
            approval_token=approval.token,
            action=approval.action,
            payload_summary=approval.payload_summary or "",
            expires_at=approval.expires_at,
            invoice_id=str(approval.invoice_id),
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{invoice_id}/reminders/confirm", response_model=dict)
async def confirm_reminder_route(
    invoice_id: uuid.UUID,
    req: ReminderConfirmRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        rec = await confirm_reminder(db, invoice_id, current_user.id, req.approval_token)
        return {"status": "sent", "recovery_action_id": str(rec.id)}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


def _invoice_response(invoice) -> InvoiceResponse:
    from backend.schemas.invoice import LineItemResponse
    items = [
        LineItemResponse(
            id=str(item.id),
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            amount=item.amount,
        )
        for item in (invoice.items or [])
    ]
    return InvoiceResponse(
        id=str(invoice.id),
        customer_name=invoice.customer_name,
        customer_email=invoice.customer_email,
        currency=invoice.currency,
        total_amount=invoice.total_amount,
        amount_due=invoice.amount_due,
        amount_paid=invoice.amount_paid,
        local_status=invoice.local_status,
        paypal_invoice_id=invoice.paypal_invoice_id,
        paypal_invoice_number=invoice.paypal_invoice_number,
        paypal_status=invoice.paypal_status,
        paypal_invoice_url=invoice.paypal_invoice_url,
        due_date=invoice.due_date,
        invoice_date=invoice.invoice_date,
        note=invoice.note,
        ai_created=invoice.ai_created,
        reminder_count_total=invoice.reminder_count_total,
        items=items,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        sent_at=invoice.sent_at,
        paid_at=invoice.paid_at,
    )
