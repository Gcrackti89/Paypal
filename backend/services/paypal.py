from __future__ import annotations
import json
import time
import uuid
import base64
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Any
from contextlib import asynccontextmanager
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from backend.config import settings
from backend.core.exceptions import PayPalError, PayPalNotConfiguredError
import structlog

logger = structlog.get_logger(__name__)

# Token cache
_token_cache: dict = {"access_token": None, "expires_at": 0.0}


def _is_retryable(exc: Exception) -> bool:
    """Only retry on transient network errors or 5xx/429."""
    if isinstance(exc, PayPalError):
        return getattr(exc, '_status_code', 0) in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.PAYPAL_BASE_URL,
        timeout=settings.PAYPAL_HTTP_TIMEOUT_SECONDS,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )


async def _get_access_token() -> str:
    """Get cached OAuth2 access token or request a new one."""
    if not settings.paypal_configured:
        raise PayPalNotConfiguredError()

    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]

    credentials = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with _get_client() as client:
        try:
            resp = await client.post(
                "/v1/oauth2/token",
                content=b"grant_type=client_credentials",
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            _token_cache["access_token"] = data["access_token"]
            _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
            logger.info("paypal_token_refreshed", expires_in=data.get("expires_in"))
            return _token_cache["access_token"]
        except httpx.HTTPStatusError as e:
            logger.error("paypal_oauth_failed", status=e.response.status_code)
            raise PayPalError("PayPal authentication failed. Check your Client ID and Secret.", status_code=502)


def _clear_token_cache():
    """Clear the token cache (for testing)."""
    _token_cache["access_token"] = None
    _token_cache["expires_at"] = 0.0


async def _paypal_request(
    method: str,
    path: str,
    json_body: dict | None = None,
    request_id: str | None = None,
) -> dict:
    """Make an authenticated PayPal API request."""
    token = await _get_access_token()
    headers: dict = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id

    async with _get_client() as client:
        try:
            resp = await client.request(
                method,
                path,
                json=json_body,
                headers=headers,
            )
            if resp.status_code == 404:
                raise PayPalError("PayPal resource not found", status_code=404)
            if resp.status_code == 422:
                detail = resp.text[:500] if resp.text else "Unprocessable entity"
                raise PayPalError(f"PayPal validation error: {detail}", status_code=422)
            if resp.status_code >= 400:
                err_code = resp.status_code
                err = PayPalError(f"PayPal returned {resp.status_code}", status_code=502)
                err._status_code = err_code
                raise err
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()
        except httpx.TimeoutException:
            raise PayPalError("PayPal request timed out. Try again.", status_code=504)
        except httpx.NetworkError:
            raise PayPalError("Network error communicating with PayPal.", status_code=503)


async def create_draft_invoice(
    customer_name: str,
    customer_email: str,
    line_items: list[dict],
    currency: str,
    due_date_str: str | None,
    note: str | None,
    memo: str | None,
    idempotency_key: str,
) -> dict:
    """Create a draft invoice in PayPal."""
    items_payload = []
    for item in line_items:
        items_payload.append({
            "name": item["description"][:100],
            "description": item["description"][:1000],
            "quantity": str(item["quantity"]),
            "unit_amount": {"currency_code": currency, "value": str(item["unit_price"])},
        })

    payload: dict = {
        "detail": {
            "currency_code": currency,
            "payment_term": {"term_type": "DUE_ON_DATE_SPECIFIED"} if due_date_str else {"term_type": "NO_DUE_DATE"},
        },
        "primary_recipients": [{
            "billing_info": {
                "name": {"given_name": customer_name.split()[0], "surname": " ".join(customer_name.split()[1:]) or "."},
                "email_address": customer_email,
            },
        }],
        "items": items_payload,
    }
    if due_date_str:
        payload["detail"]["payment_term"]["due_date"] = due_date_str
    if note:
        payload["detail"]["note"] = note[:4000]
    if memo:
        payload["detail"]["memo"] = memo[:500]

    return await _paypal_request("POST", "/v2/invoicing/invoices", json_body=payload, request_id=idempotency_key)


async def fetch_invoice(paypal_invoice_id: str) -> dict:
    """Fetch authoritative invoice state from PayPal."""
    return await _paypal_request("GET", f"/v2/invoicing/invoices/{paypal_invoice_id}")


async def send_invoice(
    paypal_invoice_id: str,
    idempotency_key: str,
    subject: str | None = None,
    note: str | None = None,
    send_to_recipient: bool = True,
) -> dict:
    """Send a draft PayPal invoice to the customer."""
    payload: dict = {"send_to_invoicer": True, "send_to_recipient": send_to_recipient}
    if subject:
        payload["subject"] = subject[:200]
    if note:
        payload["note"] = note[:4000]
    return await _paypal_request(
        "POST", f"/v2/invoicing/invoices/{paypal_invoice_id}/send",
        json_body=payload, request_id=idempotency_key,
    )


async def send_reminder(
    paypal_invoice_id: str,
    idempotency_key: str,
    subject: str | None = None,
    note: str | None = None,
) -> dict:
    """Send a reminder for a PayPal invoice."""
    payload: dict = {"send_to_invoicer": True, "send_to_recipient": True}
    if subject:
        payload["subject"] = subject[:200]
    if note:
        payload["note"] = note[:4000]
    return await _paypal_request(
        "POST", f"/v2/invoicing/invoices/{paypal_invoice_id}/remind",
        json_body=payload, request_id=idempotency_key,
    )


async def cancel_invoice(paypal_invoice_id: str, idempotency_key: str, note: str | None = None) -> dict:
    """Cancel a PayPal invoice."""
    payload: dict = {"send_to_invoicer": True, "send_to_recipient": True}
    if note:
        payload["note"] = note[:4000]
    return await _paypal_request(
        "POST", f"/v2/invoicing/invoices/{paypal_invoice_id}/cancel",
        json_body=payload, request_id=idempotency_key,
    )


async def search_invoices(page: int = 1, page_size: int = 20, status_filter: list[str] | None = None) -> dict:
    """Search/list PayPal invoices."""
    payload: dict = {"page": page, "page_size": page_size, "use_total_count": True}
    if status_filter:
        payload["status"] = status_filter
    return await _paypal_request("POST", "/v2/invoicing/search-invoices", json_body=payload)


async def verify_webhook_signature(
    auth_algo: str,
    cert_url: str,
    transmission_id: str,
    transmission_sig: str,
    transmission_time: str,
    webhook_id: str,
    event_body: str,
) -> bool:
    """Verify webhook signature via PayPal API."""
    if not settings.paypal_configured:
        return False
    payload = {
        "auth_algo": auth_algo,
        "cert_url": cert_url,
        "transmission_id": transmission_id,
        "transmission_sig": transmission_sig,
        "transmission_time": transmission_time,
        "webhook_id": webhook_id,
        "webhook_event": json.loads(event_body) if isinstance(event_body, str) else event_body,
    }
    try:
        result = await _paypal_request("POST", "/v1/notifications/verify-webhook-signature", json_body=payload)
        return result.get("verification_status") == "SUCCESS"
    except PayPalError:
        return False


def map_paypal_status_to_local(paypal_status: str) -> str:
    """Map PayPal invoice status to local InvoiceLocalStatus."""
    from backend.models.invoice import InvoiceLocalStatus
    mapping = {
        "DRAFT": InvoiceLocalStatus.DRAFT.value,
        "SENT": InvoiceLocalStatus.PENDING.value,
        "SCHEDULED": InvoiceLocalStatus.PENDING.value,
        "PARTIALLY_PAID": InvoiceLocalStatus.PENDING.value,
        "PAYMENT_PENDING": InvoiceLocalStatus.PENDING.value,
        "PAID": InvoiceLocalStatus.PAID.value,
        "CANCELLED": InvoiceLocalStatus.CANCELLED.value,
        "REFUNDED": InvoiceLocalStatus.REFUNDED.value,
        "UNPAID": InvoiceLocalStatus.PENDING.value,
        "MARKED_AS_PAID": InvoiceLocalStatus.PAID.value,
        "MARKED_AS_REFUNDED": InvoiceLocalStatus.REFUNDED.value,
    }
    return mapping.get(paypal_status.upper(), InvoiceLocalStatus.PENDING.value)


def get_connection_status() -> dict:
    """Return PayPal connection status (no secrets)."""
    return {
        "configured": settings.paypal_configured,
        "environment": settings.PAYPAL_ENV,
        "base_url": settings.PAYPAL_BASE_URL,
        "is_sandbox": settings.is_sandbox,
        "has_webhook_id": bool(settings.PAYPAL_WEBHOOK_ID),
        "client_id_prefix": settings.PAYPAL_CLIENT_ID[:8] + "..." if settings.PAYPAL_CLIENT_ID else None,
    }
