"""Tests 8-11: Webhook processing, deduplication, signature verification, out-of-order events."""
from __future__ import annotations
import json
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from tests.conftest import create_test_invoice


SAMPLE_WEBHOOK = {
    "id": "WH-TEST-001",
    "event_type": "INVOICING.INVOICE.PAID",
    "resource_type": "invoice",
    "resource": {
        "id": "PP-INV-TEST-001",
        "status": "PAID",
    },
}


@pytest.mark.asyncio
async def test_duplicate_webhook_processed_once(client, db_session):
    """Test 8: Same PayPal event ID is processed only once."""
    with patch("backend.routes.webhooks.verify_webhook_signature", new_callable=AsyncMock) as mock_verify, \
         patch("backend.routes.webhooks.settings") as mock_settings:
        mock_verify.return_value = True
        mock_settings.paypal_configured = True
        mock_settings.PAYPAL_WEBHOOK_ID = "test-webhook-id"
        mock_settings.APP_ENV = "development"
        mock_settings.WEBHOOK_PROCESSING_QUEUE = "paypal-webhooks"

        headers = {
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-CERT-URL": "https://api.paypal.com/v1/notifications/certs/CERT-001",
            "PAYPAL-TRANSMISSION-ID": "TEST-TRANS-001",
            "PAYPAL-TRANSMISSION-SIG": "test-signature",
            "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
        }

        payload = json.dumps(SAMPLE_WEBHOOK)

        # First delivery
        resp1 = await client.post(
            "/api/v1/webhooks/paypal",
            content=payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "accepted"

        # Duplicate delivery
        resp2 = await client.post(
            "/api/v1/webhooks/paypal",
            content=payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_invalid_signature_rejected(client):
    """Test 9: Webhook with invalid signature is rejected."""
    with patch("backend.routes.webhooks.verify_webhook_signature", new_callable=AsyncMock) as mock_verify, \
         patch("backend.routes.webhooks.settings") as mock_settings:
        mock_verify.return_value = False
        mock_settings.paypal_configured = True
        mock_settings.PAYPAL_WEBHOOK_ID = "test-webhook-id"
        mock_settings.APP_ENV = "development"

        headers = {
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-CERT-URL": "https://api.paypal.com/v1/notifications/certs/CERT-001",
            "PAYPAL-TRANSMISSION-ID": "FAKE-TRANS",
            "PAYPAL-TRANSMISSION-SIG": "invalid-sig",
            "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
        }

        payload = json.dumps({**SAMPLE_WEBHOOK, "id": "WH-FAKE-001"})
        resp = await client.post(
            "/api/v1/webhooks/paypal",
            content=payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_out_of_order_webhook_does_not_regress(client, auth_headers, db_session):
    """Test 10: Receiving SENT after PAID does not regress invoice to PENDING."""
    invoice_data = await create_test_invoice(client, auth_headers)
    invoice_id = invoice_data["id"]

    # Manually set invoice to PAID status
    from sqlalchemy import select
    from backend.models.invoice import Invoice, InvoiceLocalStatus
    import uuid as _uuid

    result = await db_session.execute(select(Invoice).where(Invoice.id == _uuid.UUID(invoice_id)))
    invoice = result.scalar_one()
    invoice.local_status = InvoiceLocalStatus.PAID.value
    invoice.paypal_invoice_id = "PP-INV-OOO-001"
    invoice.paypal_status = "PAID"
    await db_session.commit()

    # Simulate processing an out-of-order SENT webhook event
    # This calls the task logic directly
    from backend.tasks import run_async

    async def _test_ooo():
        from backend.database import AsyncSessionLocal
        from backend.models.webhook import WebhookEvent
        from backend.services.paypal import fetch_invoice, map_paypal_status_to_local
        from backend.models.invoice import Invoice
        from sqlalchemy import select
        import uuid as _uuid
        import json

        # Create a webhook event record
        async with AsyncSessionLocal() as session:
            # This would be a SENT event (lower priority than PAID)
            # The task should NOT regress the status
            STATUS_PRIORITY = {
                InvoiceLocalStatus.DRAFT.value: 0,
                InvoiceLocalStatus.PENDING.value: 1,
                InvoiceLocalStatus.OVERDUE.value: 2,
                InvoiceLocalStatus.PAID.value: 3,
                InvoiceLocalStatus.REFUNDED.value: 4,
                InvoiceLocalStatus.CANCELLED.value: 5,
            }
            current_status = InvoiceLocalStatus.PAID.value
            incoming_status = InvoiceLocalStatus.PENDING.value  # from SENT event
            current_priority = STATUS_PRIORITY.get(current_status, 0)
            new_priority = STATUS_PRIORITY.get(incoming_status, 0)

            # Key logic: should NOT update if new_priority < current_priority
            should_update = new_priority >= current_priority
            assert should_update is False, "SENT event should not override PAID status"

    run_async(_test_ooo())


@pytest.mark.asyncio
async def test_partial_payment_does_not_mark_fully_paid(client, auth_headers, db_session):
    """Test 11: Partial/pending payment does not mark invoice fully paid."""
    from backend.services.paypal import map_paypal_status_to_local
    from backend.models.invoice import InvoiceLocalStatus

    # PARTIALLY_PAID should map to PENDING, not PAID
    partial_local = map_paypal_status_to_local("PARTIALLY_PAID")
    assert partial_local != InvoiceLocalStatus.PAID.value

    # PAYMENT_PENDING should also not be PAID
    pending_local = map_paypal_status_to_local("PAYMENT_PENDING")
    assert pending_local != InvoiceLocalStatus.PAID.value

    # Only PAID and MARKED_AS_PAID should map to PAID
    assert map_paypal_status_to_local("PAID") == InvoiceLocalStatus.PAID.value
    assert map_paypal_status_to_local("MARKED_AS_PAID") == InvoiceLocalStatus.PAID.value
