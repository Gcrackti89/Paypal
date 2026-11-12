from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.core.exceptions import AppException
from backend.services.recovery import run_recovery_scan, get_recovery_queue
from backend.schemas.recovery import RecoveryScanResponse, RecoveryActionResponse

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/scan", response_model=RecoveryScanResponse)
async def trigger_recovery_scan(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        result = await run_recovery_scan(db, current_user.id)
        return RecoveryScanResponse(
            scanned=result["scanned"],
            overdue_found=result["overdue_found"],
            recommendations=[RecoveryActionResponse(
                id=str(r.id),
                invoice_id=str(r.invoice_id),
                action_type=r.action_type,
                status=r.status,
                days_overdue=r.days_overdue,
                previous_reminders=r.previous_reminders,
                recommended_action=r.recommended_action,
                draft_message=r.draft_message,
                error_message=r.error_message,
                is_auto=r.is_auto,
                created_at=r.created_at,
                executed_at=r.executed_at,
            ) for r in result["recommendations"]],
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/queue")
async def get_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        items, total = await get_recovery_queue(db, current_user.id, page, page_size)
        return {
            "items": [RecoveryActionResponse(
                id=str(r.id),
                invoice_id=str(r.invoice_id),
                action_type=r.action_type,
                status=r.status,
                days_overdue=r.days_overdue,
                previous_reminders=r.previous_reminders,
                recommended_action=r.recommended_action,
                draft_message=r.draft_message,
                error_message=r.error_message,
                is_auto=r.is_auto,
                created_at=r.created_at,
                executed_at=r.executed_at,
            ) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
