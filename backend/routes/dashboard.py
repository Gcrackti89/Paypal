from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.models.invoice import Invoice, InvoiceLocalStatus
from backend.models.recovery import RecoveryAction, RecoveryActionStatus
from decimal import Decimal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    user_id = current_user.id

    async def _sum(status_list):
        result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                and_(Invoice.user_id == user_id, Invoice.local_status.in_(status_list))
            )
        )
        return result.scalar() or Decimal("0")

    async def _count(status_list):
        result = await db.execute(
            select(func.count()).select_from(Invoice).where(
                and_(Invoice.user_id == user_id, Invoice.local_status.in_(status_list))
            )
        )
        return result.scalar() or 0

    outstanding_amount = await _sum([
        InvoiceLocalStatus.PENDING.value,
        InvoiceLocalStatus.OVERDUE.value,
    ])
    overdue_total = await _sum([InvoiceLocalStatus.OVERDUE.value])
    paid_total = await _sum([InvoiceLocalStatus.PAID.value])
    open_count = await _count([
        InvoiceLocalStatus.PENDING.value,
        InvoiceLocalStatus.OVERDUE.value,
        InvoiceLocalStatus.DRAFT.value,
    ])
    overdue_count = await _count([InvoiceLocalStatus.OVERDUE.value])

    # Recent recovery actions
    recent_actions = await db.execute(
        select(RecoveryAction).where(
            and_(
                RecoveryAction.user_id == user_id,
                RecoveryAction.status == RecoveryActionStatus.EXECUTED.value,
            )
        ).order_by(RecoveryAction.executed_at.desc()).limit(5)
    )
    recent = recent_actions.scalars().all()

    # Recovery queue size
    queue_count_result = await db.execute(
        select(func.count()).select_from(RecoveryAction).where(
            and_(
                RecoveryAction.user_id == user_id,
                RecoveryAction.status == RecoveryActionStatus.PENDING.value,
            )
        )
    )
    queue_count = queue_count_result.scalar() or 0

    return {
        "outstanding_amount": str(outstanding_amount),
        "overdue_total": str(overdue_total),
        "paid_total": str(paid_total),
        "open_invoices_count": open_count,
        "overdue_count": overdue_count,
        "recovery_queue_size": queue_count,
        "recent_recoveries": [
            {
                "id": str(r.id),
                "invoice_id": str(r.invoice_id),
                "action_type": r.action_type,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in recent
        ],
    }
