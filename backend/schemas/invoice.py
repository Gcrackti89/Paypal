from __future__ import annotations
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
import re

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "SEK", "NOK", "DKK"}


class LineItemRequest(BaseModel):
    description: str = Field(min_length=1, max_length=1024)
    quantity: Decimal = Field(gt=Decimal("0"), le=Decimal("9999.99"))
    unit_price: Decimal = Field(ge=Decimal("0"), le=Decimal("999999.99"))

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class InvoiceDraftRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    currency: str = Field(default="USD", min_length=3, max_length=3)
    line_items: List[LineItemRequest] = Field(min_length=1, max_length=50)
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=4000)
    memo: Optional[str] = Field(default=None, max_length=4000)
    ai_created: bool = False
    ai_session_id: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency {v} not supported. Use one of: {', '.join(sorted(SUPPORTED_CURRENCIES))}")
        return v

    @model_validator(mode="after")
    def validate_due_date(self):
        if self.due_date and self.due_date < date.today():
            raise ValueError("Due date cannot be in the past")
        return self


class LineItemResponse(BaseModel):
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: str
    customer_name: str
    customer_email: str
    currency: str
    total_amount: Decimal
    amount_due: Optional[Decimal]
    amount_paid: Optional[Decimal]
    local_status: str
    paypal_invoice_id: Optional[str]
    paypal_invoice_number: Optional[str]
    paypal_status: Optional[str]
    paypal_invoice_url: Optional[str]
    due_date: Optional[date]
    invoice_date: Optional[date]
    note: Optional[str]
    ai_created: bool
    reminder_count_total: int
    items: List[LineItemResponse] = []
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]
    paid_at: Optional[datetime]

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    items: List[InvoiceResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
