"""Tests 4 & 5: Invoice send approval system."""
from __future__ import annotations
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from tests.conftest import create_test_invoice


@pytest.mark.asyncio
async def test_invoice_send_requires_valid_approval(client, auth_headers):
    """Sending an invoice without an approval token fails."""
    invoice = await create_test_invoice(client, auth_headers)
    invoice_id = invoice["id"]

    # Try to confirm without preparing first
    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/send/confirm",
        json={"approval_token": "made-up-token"},
        headers=auth_headers,
    )
    assert resp.status_code in (409, 404, 400)  # Approval required


@pytest.mark.asyncio
async def test_approval_token_cannot_be_replayed(client, auth_headers, db_session):
    """An approval token can only be used once."""
    invoice = await create_test_invoice(client, auth_headers)
    invoice_id = invoice["id"]

    # Mock PayPal API calls
    with patch("backend.services.invoice.create_draft_invoice", new_callable=AsyncMock) as mock_create, \
         patch("backend.services.invoice.send_invoice", new_callable=AsyncMock) as mock_send, \
         patch("backend.services.invoice.fetch_invoice", new_callable=AsyncMock) as mock_fetch:

        mock_create.return_value = {"id": "PP-INV-001", "detail": {"invoice_number": "INV-001"}}
        mock_send.return_value = {}
        mock_fetch.return_value = {"status": "SENT", "detail": {}}

        # Prepare approval
        prep_resp = await client.post(
            f"/api/v1/invoices/{invoice_id}/send/prepare",
            headers=auth_headers,
        )
        assert prep_resp.status_code == 200
        token = prep_resp.json()["approval_token"]

        # First use - should succeed
        confirm_resp = await client.post(
            f"/api/v1/invoices/{invoice_id}/send/confirm",
            json={"approval_token": token},
            headers=auth_headers,
        )
        assert confirm_resp.status_code == 200

        # Second use - should fail (token consumed)
        replay_resp = await client.post(
            f"/api/v1/invoices/{invoice_id}/send/confirm",
            json={"approval_token": token},
            headers=auth_headers,
        )
        assert replay_resp.status_code in (409, 400)


@pytest.mark.asyncio
async def test_approval_token_wrong_user_rejected(client, auth_headers, second_user_headers):
    """User B cannot use User A's approval token."""
    invoice = await create_test_invoice(client, auth_headers)
    invoice_id = invoice["id"]

    with patch("backend.services.invoice.create_draft_invoice", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {"id": "PP-INV-002", "detail": {"invoice_number": "INV-002"}}
        prep_resp = await client.post(
            f"/api/v1/invoices/{invoice_id}/send/prepare",
            headers=auth_headers,
        )
        token = prep_resp.json()["approval_token"]

    # User B tries to use User A's token on User A's invoice
    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/send/confirm",
        json={"approval_token": token},
        headers=second_user_headers,
    )
    assert resp.status_code in (404, 409, 403)
