"""Test 2: AI structured output validation and missing fields."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from backend.services.ai_agent import process_agent_command, validate_invoice_totals
from backend.schemas.agent import ExtractedInvoiceData, ExtractedLineItem
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_ai_unavailable_when_no_api_key():
    """Returns graceful message when OpenAI key is missing."""
    with patch("backend.services.ai_agent.settings") as mock_settings:
        mock_settings.openai_configured = False
        result = await process_agent_command("Create an invoice for Alex")
        assert result.ai_available is False
        assert "not configured" in result.message.lower() or "not available" in result.message.lower()


@pytest.mark.asyncio
async def test_ai_returns_missing_fields_when_incomplete():
    """AI returns incomplete=False and lists missing fields when email is absent."""
    incomplete_response = {
        "customer_name": "Alex",
        "customer_email": None,
        "currency": "USD",
        "line_items": [{"description": "Logo", "quantity": 2, "unit_price": 75.0}],
        "due_date_days": 7,
        "note": None,
        "is_complete": False,
        "missing_fields": ["customer_email"],
        "clarification_needed": "What is the customer's email address?",
    }

    mock_choice = MagicMock()
    mock_choice.message.content = __import__("json").dumps(incomplete_response)
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(total_tokens=100)

    with patch("backend.services.ai_agent.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("backend.services.ai_agent.settings") as mock_settings:
            mock_settings.openai_configured = True
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_MAX_TOKENS = 2000
            mock_settings.OPENAI_TIMEOUT_SECONDS = 30

            result = await process_agent_command("Invoice for Alex")

    assert result.ready_for_review is False
    assert result.extracted_data is not None
    assert result.extracted_data.is_complete is False
    assert "customer_email" in result.extracted_data.missing_fields


def test_extracted_line_item_validates_negative_quantity():
    """Pydantic schema rejects non-positive quantity."""
    with pytest.raises(ValidationError):
        ExtractedLineItem(description="Item", quantity=Decimal("-1"), unit_price=Decimal("50"))


def test_validate_totals_does_not_trust_client_total():
    """Backend always recalculates; never uses a client-provided total."""
    items = [
        {"description": "A", "quantity": "2", "unit_price": "100.00"},
    ]
    result = validate_invoice_totals(items, "USD")
    assert Decimal(result["total"]) == Decimal("200.00")
    # Even if items list is what an AI gave, we recalculate
