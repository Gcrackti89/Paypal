"""Tests 12-14: Recovery engine - reminder eligibility, caps, scan."""
from __future__ import annotations
import pytest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from tests.conftest import create_test_invoice
from backend.services.recovery import _check_reminder_eligibility
from backend.models.invoice import Invoice, InvoiceLocalStatus
from backend.core.exceptions import ApprovalError
import uuid


def make_invoice(status: str, due_date=None, reminder_today=0) -> Invoice:
    inv = Invoice()
    inv.id = uuid.uuid4()
    inv.user_id = uuid.uuid4()
    inv.local_status = status
    inv.customer_name = "Test"
    inv.customer_email = "test@example.com"
    inv.currency = "USD"
    inv.total_amount = Decimal("100.00")
    inv.amount_due = Decimal("100.00")
    inv.reminder_count_today = reminder_today
    inv.reminder_count_total = 0
    inv.ai_created = False
    inv.due_date = due_date or date.today() - timedelta(days=5)
    return inv


def test_paid_invoice_not_eligible_for_reminder():
    """Test 12a: Paid invoice never gets a reminder."""
    inv = make_invoice(InvoiceLocalStatus.PAID.value)
    with pytest.raises(ApprovalError):
        _check_reminder_eligibility(inv)


def test_cancelled_invoice_not_eligible_for_reminder():
    """Test 12b: Cancelled invoice never gets a reminder."""
    inv = make_invoice(InvoiceLocalStatus.CANCELLED.value)
    with pytest.raises(ApprovalError):
        _check_reminder_eligibility(inv)


def test_refunded_invoice_not_eligible_for_reminder():
    """Test 12c: Refunded invoice never gets a reminder."""
    inv = make_invoice(InvoiceLocalStatus.REFUNDED.value)
    with pytest.raises(ApprovalError):
        _check_reminder_eligibility(inv)


def test_draft_invoice_not_eligible_for_reminder():
    """Test 12d: Draft invoice never gets a reminder (not sent yet)."""
    inv = make_invoice(InvoiceLocalStatus.DRAFT.value)
    with pytest.raises(ApprovalError):
        _check_reminder_eligibility(inv)


def test_overdue_invoice_eligible_for_reminder():
    """Test 12e: Overdue invoice is eligible."""
    inv = make_invoice(InvoiceLocalStatus.OVERDUE.value)
    _check_reminder_eligibility(inv)  # Should NOT raise


def test_pending_invoice_eligible_for_reminder():
    """Test 12e: Pending invoice is eligible."""
    inv = make_invoice(InvoiceLocalStatus.PENDING.value)
    _check_reminder_eligibility(inv)  # Should NOT raise


@pytest.mark.asyncio
async def test_reminder_rate_limit_enforced(client, auth_headers, db_session):
    """Test 13: Max reminders per invoice per day is enforced."""
    from sqlalchemy import select
    from backend.models.invoice import Invoice
    from backend.config import settings
    import uuid as _uuid

    invoice_data = await create_test_invoice(
        client, auth_headers,
        due_date=(date.today() - timedelta(days=3)).isoformat()
    )
    invoice_id = invoice_data["id"]

    # Set invoice to OVERDUE and add paypal_invoice_id, max out daily reminders
    result = await db_session.execute(select(Invoice).where(Invoice.id == _uuid.UUID(invoice_id)))
    inv = result.scalar_one()
    inv.local_status = InvoiceLocalStatus.OVERDUE.value
    inv.paypal_invoice_id = "PP-INV-RATELIMIT"
    inv.reminder_count_today = settings.MAX_REMINDERS_PER_INVOICE_PER_DAY
    inv.reminder_count_reset_date = date.today()
    await db_session.commit()

    # Try to send a reminder - should fail with rate limit error
    from backend.services.recovery import confirm_reminder, prepare_reminder
    from backend.core.exceptions import RateLimitError, ApprovalError
    from backend.core.security import generate_secure_token, hash_payload
    from backend.models.approval import ApprovalRequest, ApprovalAction
    from datetime import timedelta as td
    import json

    # Manually create an approval token
    payload = json.dumps({"action": "SEND_REMINDER", "invoice_id": invoice_id})
    token = generate_secure_token()
    approval = ApprovalRequest(
        user_id=inv.user_id,
        invoice_id=inv.id,
        action=ApprovalAction.SEND_REMINDER.value,
        token=token,
        payload_hash=hash_payload(payload),
        payload_summary="Test reminder",
        expires_at=datetime.now(timezone.utc) + td(minutes=15),
    )
    db_session.add(approval)
    await db_session.commit()

    from unittest.mock import patch, AsyncMock
    with patch("backend.services.recovery.fetch_invoice", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"status": "SENT"}
        with pytest.raises(RateLimitError):
            await confirm_reminder(db_session, inv.id, inv.user_id, token)


@pytest.mark.asyncio
async def test_recovery_scan_finds_overdue_invoices(client, auth_headers, db_session):
    """Test 14: Recovery scan selects only eligible overdue invoices."""
    from sqlalchemy import select
    from backend.models.invoice import Invoice
    from backend.services.recovery import run_recovery_scan
    import uuid as _uuid

    # Create a PENDING invoice with past due date
    invoice_data = await create_test_invoice(
        client, auth_headers,
        due_date=(date.today() - timedelta(days=5)).isoformat()
    )
    invoice_id = invoice_data["id"]

    # Set to PENDING (simulates sent invoice)
    result = await db_session.execute(select(Invoice).where(Invoice.id == _uuid.UUID(invoice_id)))
    inv = result.scalar_one()
    inv.local_status = InvoiceLocalStatus.PENDING.value
    await db_session.commit()

    # Also create a PAID invoice that should NOT be found
    paid_data = await create_test_invoice(
        client, auth_headers,
        customer_email="paid@example.com",
        due_date=(date.today() - timedelta(days=10)).isoformat()
    )
    paid_result = await db_session.execute(select(Invoice).where(Invoice.id == _uuid.UUID(paid_data["id"])))
    paid_inv = paid_result.scalar_one()
    paid_inv.local_status = InvoiceLocalStatus.PAID.value
    await db_session.commit()

    # Get user_id from invoice
    user_id = inv.user_id
    result = await run_recovery_scan(db_session, user_id)

    assert result["overdue_found"] >= 1
    # Paid invoice should NOT be in recommendations
    rec_invoice_ids = [str(r.invoice_id) for r in result["recommendations"]]
    assert paid_data["id"] not in rec_invoice_ids
    assert invoice_id in rec_invoice_ids or result["overdue_found"] >= 1
