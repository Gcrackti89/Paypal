from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class AgentCommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = Field(default=None, max_length=50)


class ExtractedLineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal


class ExtractedInvoiceData(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    currency: str = "USD"
    line_items: Optional[List[ExtractedLineItem]] = None
    due_date_days: Optional[int] = None
    note: Optional[str] = None
    is_complete: bool = False
    missing_fields: List[str] = []
    clarification_needed: Optional[str] = None


class AgentResponse(BaseModel):
    session_id: str
    message: str
    extracted_data: Optional[ExtractedInvoiceData] = None
    invoice_preview: Optional[dict] = None
    ready_for_review: bool = False
    error: Optional[str] = None
    ai_available: bool = True
