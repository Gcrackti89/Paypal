from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RecoveryActionResponse(BaseModel):
    id: str
    invoice_id: str
    action_type: str
    status: str
    days_overdue: Optional[int]
    previous_reminders: int
    recommended_action: Optional[str]
    draft_message: Optional[str]
    error_message: Optional[str]
    is_auto: bool
    created_at: datetime
    executed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RecoveryScanResponse(BaseModel):
    scanned: int
    overdue_found: int
    recommendations: List[RecoveryActionResponse]


class ApprovalRequestResponse(BaseModel):
    approval_token: str
    action: str
    payload_summary: str
    expires_at: datetime
    invoice_id: str


class ReminderConfirmRequest(BaseModel):
    approval_token: str


class SendInvoiceConfirmRequest(BaseModel):
    approval_token: str
