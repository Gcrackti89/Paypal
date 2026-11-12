from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.models.audit import AuditLog
from backend.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    user_id = current_user.id
    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)
    )
    total = count_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset).limit(page_size)
    )
    logs = result.scalars().all()
    return AuditLogListResponse(
        items=[AuditLogResponse(
            id=str(log.id),
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            description=log.description,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )
