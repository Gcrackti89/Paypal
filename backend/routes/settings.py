from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.models.merchant_settings import MerchantSettings
from backend.models.audit import AuditLog, AuditAction
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter(prefix="/settings", tags=["settings"])


class MerchantSettingsUpdate(BaseModel):
    timezone: Optional[str] = None
    auto_reminders_enabled: Optional[bool] = None
    reminder_days_before_due: Optional[int] = None
    reminder_days_after_due: Optional[List[int]] = None
    reminder_quiet_hours_start: Optional[int] = None
    reminder_quiet_hours_end: Optional[int] = None


@router.get("/merchant")
async def get_merchant_settings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(MerchantSettings).where(MerchantSettings.user_id == current_user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        return {"error": "Settings not found"}
    return {
        "timezone": s.timezone,
        "auto_reminders_enabled": s.auto_reminders_enabled,
        "reminder_days_before_due": s.reminder_days_before_due,
        "reminder_days_after_due": s.reminder_days_after_due,
        "reminder_quiet_hours_start": s.reminder_quiet_hours_start,
        "reminder_quiet_hours_end": s.reminder_quiet_hours_end,
        "paypal_connected_at": s.paypal_connected_at.isoformat() if s.paypal_connected_at else None,
        "paypal_account_email": s.paypal_account_email,
    }


@router.patch("/merchant")
async def update_merchant_settings(
    update: MerchantSettingsUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(MerchantSettings).where(MerchantSettings.user_id == current_user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    if update.timezone is not None:
        s.timezone = update.timezone
    if update.auto_reminders_enabled is not None:
        s.auto_reminders_enabled = update.auto_reminders_enabled
    if update.reminder_days_before_due is not None:
        s.reminder_days_before_due = update.reminder_days_before_due
    if update.reminder_days_after_due is not None:
        s.reminder_days_after_due = update.reminder_days_after_due
    if update.reminder_quiet_hours_start is not None:
        s.reminder_quiet_hours_start = update.reminder_quiet_hours_start
    if update.reminder_quiet_hours_end is not None:
        s.reminder_quiet_hours_end = update.reminder_quiet_hours_end

    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.SETTINGS_UPDATED.value,
        description="Merchant settings updated",
    )
    db.add(audit)
    await db.commit()
    return {"status": "updated"}
