"""Test 15: No credentials or tokens appear in API responses/logging."""
from __future__ import annotations
import json
import pytest
from backend.services.paypal import get_connection_status
from backend.config import settings


def test_paypal_status_does_not_expose_client_secret():
    """Test 15a: PayPal status endpoint never returns the client secret."""
    status = get_connection_status()
    status_json = json.dumps(status)
    # Client secret should not appear
    assert settings.PAYPAL_CLIENT_SECRET not in status_json
    # Even if client secret is 'test-client-secret', it must not be in response
    assert "test-client-secret" not in status_json
    assert "client_secret" not in status_json.lower()


def test_paypal_status_client_id_is_truncated():
    """Test 15b: Client ID is truncated, not fully exposed."""
    status = get_connection_status()
    if status["client_id_prefix"]:
        assert "..." in status["client_id_prefix"]
        assert len(status["client_id_prefix"]) < len(settings.PAYPAL_CLIENT_ID)


@pytest.mark.asyncio
async def test_register_response_has_no_password(client):
    """Test 15c: Register response never includes hashed password."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "secure@example.com",
        "password": "SecurePass123",
        "full_name": "Secure User",
    })
    assert resp.status_code == 201
    data = resp.json()
    data_str = json.dumps(data)
    assert "password" not in data_str.lower()
    assert "hashed" not in data_str.lower()


@pytest.mark.asyncio
async def test_login_response_has_no_password(client):
    """Test 15d: Login response never includes password."""
    # Register first
    await client.post("/api/v1/auth/register", json={
        "email": "logintest@example.com",
        "password": "LoginPass123",
        "full_name": "Login User",
    })
    # Login
    resp = await client.post("/api/v1/auth/login", json={
        "email": "logintest@example.com",
        "password": "LoginPass123",
    })
    assert resp.status_code == 200
    data_str = json.dumps(resp.json())
    assert "password" not in data_str.lower()


@pytest.mark.asyncio
async def test_me_endpoint_no_secrets(client, auth_headers):
    """Test 15e: /me endpoint returns only safe user fields."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Should have these safe fields
    assert "id" in data
    assert "email" in data
    assert "full_name" in data
    # Should NOT have sensitive fields
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_invoice_response_no_internal_secrets(client, auth_headers):
    """Test 15f: Invoice response does not leak any internal tokens."""
    resp = await client.post("/api/v1/invoices/drafts", json={
        "customer_name": "Bob",
        "customer_email": "bob@test.com",
        "currency": "USD",
        "line_items": [{"description": "Service", "quantity": "1", "unit_price": "100.00"}],
    }, headers=auth_headers)
    assert resp.status_code == 201
    data_str = json.dumps(resp.json())
    # Should not contain JWT secret or any secret keys
    assert settings.JWT_SECRET_KEY not in data_str
    assert settings.APP_SECRET_KEY not in data_str
