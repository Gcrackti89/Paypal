"""Tests 6 & 7: PayPal OAuth token caching and error handling."""
from __future__ import annotations
import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
import respx
import httpx
from backend.services import paypal as paypal_service


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Clear token cache before each test."""
    paypal_service._clear_token_cache()
    yield
    paypal_service._clear_token_cache()


@pytest.mark.asyncio
async def test_oauth_token_is_cached():
    """Token is reused on subsequent calls within expiry window."""
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": "test-token-123", "expires_in": 3600}
        return mock_resp

    with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        token1 = await paypal_service._get_access_token()
        token2 = await paypal_service._get_access_token()
        token3 = await paypal_service._get_access_token()

    assert token1 == "test-token-123"
    assert token2 == "test-token-123"
    assert token3 == "test-token-123"
    assert call_count == 1  # Only one OAuth call made


@pytest.mark.asyncio
async def test_oauth_token_refreshed_when_expired():
    """Token is refreshed when it expires."""
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": f"token-{call_count}", "expires_in": 1}  # expires in 1s
        return mock_resp

    with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        token1 = await paypal_service._get_access_token()
        # Expire the cache manually
        paypal_service._token_cache["expires_at"] = time.time() - 10
        token2 = await paypal_service._get_access_token()

    assert call_count == 2
    assert token1 != token2


@pytest.mark.asyncio
async def test_paypal_not_configured_raises_error():
    """PayPalNotConfiguredError raised when credentials are missing."""
    from backend.core.exceptions import PayPalNotConfiguredError
    with patch("backend.services.paypal.settings") as mock_settings:
        mock_settings.paypal_configured = False
        with pytest.raises(PayPalNotConfiguredError):
            await paypal_service._get_access_token()


@pytest.mark.asyncio
async def test_paypal_401_raises_paypal_error():
    """HTTP 401 from PayPal raises PayPalError."""
    from backend.core.exceptions import PayPalError

    async def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )
        return mock_resp

    with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        with pytest.raises(PayPalError):
            await paypal_service._get_access_token()


@pytest.mark.asyncio
async def test_paypal_timeout_raises_paypal_error():
    """Timeout raises PayPalError, not raw exception."""
    from backend.core.exceptions import PayPalError

    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.raise_for_status = MagicMock()
    token_resp.json.return_value = {"access_token": "test-token", "expires_in": 3600}

    call_count = 0

    async def mock_request(method, path, **kwargs):
        nonlocal call_count
        call_count += 1
        if path.endswith("/v1/oauth2/token") or "oauth2" in str(path):
            return token_resp
        raise httpx.TimeoutException("Timed out")

    with patch.object(httpx.AsyncClient, "post", return_value=token_resp), \
         patch.object(httpx.AsyncClient, "request", side_effect=mock_request):
        # Pre-cache token
        paypal_service._token_cache["access_token"] = "test-token"
        paypal_service._token_cache["expires_at"] = time.time() + 3600

        with pytest.raises(PayPalError) as exc_info:
            await paypal_service.fetch_invoice("PP-INV-001")
        assert "timed out" in str(exc_info.value.message).lower()
