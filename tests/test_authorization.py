"""Test 3: User cannot access another user's invoice or customer."""
from __future__ import annotations
import pytest
from tests.conftest import create_test_invoice


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_invoice(client, auth_headers, second_user_headers):
    """User A's invoice is not accessible by User B."""
    # User A creates an invoice
    invoice = await create_test_invoice(client, auth_headers)
    invoice_id = invoice["id"]

    # User B tries to access it
    resp = await client.get(f"/api/v1/invoices/{invoice_id}", headers=second_user_headers)
    assert resp.status_code == 404  # Not found (not 403) to avoid leaking existence


@pytest.mark.asyncio
async def test_user_cannot_send_other_users_invoice(client, auth_headers, second_user_headers):
    """User B cannot prepare send for User A's invoice."""
    invoice = await create_test_invoice(client, auth_headers)
    invoice_id = invoice["id"]

    resp = await client.post(f"/api/v1/invoices/{invoice_id}/send/prepare", headers=second_user_headers)
    # Either 404 or 403 is acceptable
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_user_sees_only_own_invoices(client, auth_headers, second_user_headers):
    """List endpoint only returns invoices for the authenticated user."""
    # User A creates 2 invoices
    await create_test_invoice(client, auth_headers)
    await create_test_invoice(client, auth_headers, customer_email="alice2@example.com")
    # User B creates 1 invoice
    await create_test_invoice(client, second_user_headers, customer_email="bob@example.com")

    resp_a = await client.get("/api/v1/invoices", headers=auth_headers)
    resp_b = await client.get("/api/v1/invoices", headers=second_user_headers)

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    # User A sees 2, User B sees 1
    assert resp_a.json()["total"] == 2
    assert resp_b.json()["total"] == 1


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client):
    """Unauthenticated requests to protected endpoints return 401."""
    resp = await client.get("/api/v1/invoices")
    assert resp.status_code == 401

    resp2 = await client.get("/api/v1/dashboard/summary")
    assert resp2.status_code == 401
