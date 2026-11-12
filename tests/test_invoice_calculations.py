"""Test 1: Invoice total calculation uses Decimal and validates invalid inputs."""
from __future__ import annotations
import pytest
from decimal import Decimal
from backend.services.ai_agent import validate_invoice_totals


def test_decimal_total_calculation():
    """Backend calculates totals with Decimal precision."""
    items = [
        {"description": "Service A", "quantity": "3", "unit_price": "99.99"},
        {"description": "Service B", "quantity": "1", "unit_price": "0.01"},
    ]
    result = validate_invoice_totals(items, "USD")
    assert result["errors"] == []
    total = Decimal(result["total"])
    assert total == Decimal("299.98")  # 3*99.99 + 0.01

def test_invalid_quantity_rejected():
    items = [{"description": "Item", "quantity": "-1", "unit_price": "50.00"}]
    result = validate_invoice_totals(items, "USD")
    assert any("quantity" in e for e in result["errors"])

def test_zero_quantity_rejected():
    items = [{"description": "Item", "quantity": "0", "unit_price": "50.00"}]
    result = validate_invoice_totals(items, "USD")
    assert any("quantity" in e for e in result["errors"])

def test_negative_price_rejected():
    items = [{"description": "Item", "quantity": "1", "unit_price": "-10.00"}]
    result = validate_invoice_totals(items, "USD")
    assert any("unit_price" in e or "price" in e for e in result["errors"])

def test_invalid_currency_rejected():
    items = [{"description": "Item", "quantity": "1", "unit_price": "10.00"}]
    result = validate_invoice_totals(items, "XYZ")
    assert any("currency" in e.lower() or "XYZ" in e for e in result["errors"])

def test_empty_description_rejected():
    items = [{"description": "", "quantity": "1", "unit_price": "10.00"}]
    result = validate_invoice_totals(items, "USD")
    assert any("description" in e for e in result["errors"])

def test_non_numeric_quantity_rejected():
    items = [{"description": "Item", "quantity": "abc", "unit_price": "10.00"}]
    result = validate_invoice_totals(items, "USD")
    assert len(result["errors"]) > 0

@pytest.mark.asyncio
async def test_api_invoice_total_server_calculated(client, auth_headers):
    """API endpoint always uses server-side total, not client-provided."""
    resp = await client.post("/api/v1/invoices/drafts", json={
        "customer_name": "Bob",
        "customer_email": "bob@example.com",
        "currency": "USD",
        "line_items": [{"description": "Service", "quantity": "3", "unit_price": "50.00"}],
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    # Server should calculate 3 * 50 = 150
    assert Decimal(data["total_amount"]) == Decimal("150.00")
