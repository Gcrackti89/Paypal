from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    description: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
