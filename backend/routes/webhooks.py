from __future__ import annotations
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db_session
from backend.models.webhook import WebhookEvent
from backend.models.audit import AuditLog, AuditAction
from backend.services.paypal import verify_webhook_signature
from backend.config import settings
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Supported event types from PayPal documentation
SUPPORTED_EVENTS = {
    "INVOICING.INVOICE.CREATED",
    "INVOICING.INVOICE.SENT",
    "INVOICING.INVOICE.PAID",
    "INVOICING.INVOICE.CANCELLED",
    "INVOICING.INVOICE.REFUNDED",
    "INVOICING.INVOICE.UPDATED",
    "INVOICING.INVOICE.SCHEDULED",
}


@router.post("/paypal", status_code=status.HTTP_200_OK)
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    # 1. Verify webhook signature BEFORE processing anything
    if settings.paypal_configured and settings.PAYPAL_WEBHOOK_ID:
        auth_algo = request.headers.get("PAYPAL-AUTH-ALGO", "")
        cert_url = request.headers.get("PAYPAL-CERT-URL", "")
        transmission_id = request.headers.get("PAYPAL-TRANSMISSION-ID", "")
        transmission_sig = request.headers.get("PAYPAL-TRANSMISSION-SIG", "")
        transmission_time = request.headers.get("PAYPAL-TRANSMISSION-TIME", "")

        if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
            logger.warning("webhook_missing_headers")
            raise HTTPException(status_code=400, detail="Missing webhook verification headers")

        is_valid = await verify_webhook_signature(
            auth_algo=auth_algo,
            cert_url=cert_url,
            transmission_id=transmission_id,
            transmission_sig=transmission_sig,
            transmission_time=transmission_time,
            webhook_id=settings.PAYPAL_WEBHOOK_ID,
            event_body=body_str,
        )
        if not is_valid:
            logger.warning("webhook_signature_invalid", transmission_id=transmission_id)
            audit = AuditLog(
                action=AuditAction.WEBHOOK_REJECTED.value,
                description="Invalid webhook signature",
                metadata_={"transmission_id": transmission_id},
            )
            db.add(audit)
            await db.commit()
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        # PayPal not configured - in dev mode, accept unverified for testing
        if settings.APP_ENV == "production":
            raise HTTPException(status_code=503, detail="Webhook verification not configured")
        logger.warning("webhook_unverified_dev_mode")

    # 2. Parse payload
    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("id")
    event_type = payload.get("event_type", "")
    resource = payload.get("resource", {})

    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event ID")

    # 3. Idempotency check - deduplicate by PayPal event ID
    existing = await db.execute(
        select(WebhookEvent).where(WebhookEvent.paypal_event_id == event_id)
    )
    if existing.scalar_one_or_none():
        logger.info("webhook_duplicate_ignored", event_id=event_id)
        return {"status": "duplicate", "event_id": event_id}

    # 4. Persist event record
    event_record = WebhookEvent(
        paypal_event_id=event_id,
        event_type=event_type,
        resource_type=resource.get("resource_type"),
        resource_id=resource.get("id"),
        raw_payload=body_str,
        processed=False,
    )
    db.add(event_record)

    audit = AuditLog(
        action=AuditAction.WEBHOOK_RECEIVED.value,
        description=f"Webhook received: {event_type}",
        metadata_={"event_id": event_id, "event_type": event_type},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(event_record)

    # 5. Enqueue async processing
    if event_type in SUPPORTED_EVENTS:
        from backend.tasks import process_webhook_event
        process_webhook_event.apply_async(
            args=[str(event_record.id)],
            queue=settings.WEBHOOK_PROCESSING_QUEUE,
        )

    return {"status": "accepted", "event_id": event_id}
