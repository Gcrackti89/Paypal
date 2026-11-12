from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from backend.worker import celery_app
import structlog

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="backend.tasks.process_webhook_event", bind=True, max_retries=3)
def process_webhook_event(self, webhook_event_id: str):
    """Process a verified webhook event asynchronously."""
    async def _process():
        from backend.database import AsyncSessionLocal
        from backend.models.webhook import WebhookEvent
        from backend.services.paypal import fetch_invoice, map_paypal_status_to_local
        from backend.models.invoice import Invoice, InvoiceLocalStatus
        from backend.models.audit import AuditLog, AuditAction
        from sqlalchemy import select, and_
        import uuid

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(WebhookEvent).where(WebhookEvent.id == uuid.UUID(webhook_event_id))
                )
                event = result.scalar_one_or_none()
                if not event:
                    logger.warning("webhook_event_not_found", id=webhook_event_id)
                    return

                if event.processed:
                    logger.info("webhook_already_processed", id=webhook_event_id)
                    return

                payload = json.loads(event.raw_payload)
                resource = payload.get("resource", {})
                paypal_invoice_id = resource.get("id")

                if not paypal_invoice_id:
                    event.processed = True
                    event.processed_at = datetime.now(timezone.utc)
                    event.processing_error = "No invoice ID in resource"
                    await db.commit()
                    return

                # Fetch authoritative invoice state from PayPal
                from backend.config import settings
                if settings.paypal_configured:
                    try:
                        pp_inv = await fetch_invoice(paypal_invoice_id)
                        pp_status = pp_inv.get("status", "")
                        local_status = map_paypal_status_to_local(pp_status)

                        # Find local invoice
                        inv_result = await db.execute(
                            select(Invoice).where(Invoice.paypal_invoice_id == paypal_invoice_id)
                        )
                        invoice = inv_result.scalar_one_or_none()

                        if invoice:
                            # Only update status if it represents a progression (don't regress)
                            # Prevent out-of-order webhooks from regressing PAID back to SENT
                            STATUS_PRIORITY = {
                                InvoiceLocalStatus.DRAFT.value: 0,
                                InvoiceLocalStatus.PENDING.value: 1,
                                InvoiceLocalStatus.OVERDUE.value: 2,
                                InvoiceLocalStatus.PAID.value: 3,
                                InvoiceLocalStatus.REFUNDED.value: 4,
                                InvoiceLocalStatus.CANCELLED.value: 5,
                            }
                            current_priority = STATUS_PRIORITY.get(invoice.local_status, 0)
                            new_priority = STATUS_PRIORITY.get(local_status, 0)

                            if new_priority >= current_priority or pp_status in ("PAID", "CANCELLED", "REFUNDED", "MARKED_AS_PAID"):
                                old_status = invoice.local_status
                                invoice.local_status = local_status
                                invoice.paypal_status = pp_status
                                invoice.paypal_last_synced_at = datetime.now(timezone.utc)

                                # Handle payment details
                                amounts = pp_inv.get("amount", {})
                                if amounts.get("paid"):
                                    from decimal import Decimal
                                    invoice.amount_paid = Decimal(str(amounts["paid"].get("value", "0")))
                                if amounts.get("due"):
                                    invoice.amount_due = Decimal(str(amounts["due"].get("value", "0")))

                                if local_status == InvoiceLocalStatus.PAID.value and not invoice.paid_at:
                                    invoice.paid_at = datetime.now(timezone.utc)

                                audit = AuditLog(
                                    user_id=invoice.user_id,
                                    action=AuditAction.INVOICE_STATUS_UPDATED.value,
                                    resource_type="invoice",
                                    resource_id=str(invoice.id),
                                    description=f"Status changed from {old_status} to {local_status} via webhook",
                                    metadata_={"webhook_event_id": webhook_event_id, "paypal_event_type": event.event_type},
                                )
                                db.add(audit)
                    except Exception as e:
                        logger.error("webhook_paypal_fetch_failed", error=str(e))
                        event.processing_error = str(e)

                event.processed = True
                event.processed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("webhook_processed", id=webhook_event_id)
            except Exception as e:
                logger.error("webhook_processing_error", id=webhook_event_id, error=str(e))
                event.processing_error = str(e)
                await db.commit()
                raise

    try:
        run_async(_process())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="backend.tasks.scheduled_recovery_scan")
def scheduled_recovery_scan():
    """Run recovery scan for all active users."""
    async def _scan():
        from backend.database import AsyncSessionLocal
        from backend.models.user import User
        from backend.services.recovery import run_recovery_scan
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.is_active == True))
            users = result.scalars().all()
            for user in users:
                try:
                    await run_recovery_scan(db, user.id)
                except Exception as e:
                    logger.error("recovery_scan_failed", user_id=str(user.id), error=str(e))

    run_async(_scan())
    logger.info("scheduled_recovery_scan_complete")


@celery_app.task(name="backend.tasks.scheduled_reconciliation")
def scheduled_reconciliation():
    """Reconcile local invoice status with PayPal for sent/pending invoices."""
    async def _reconcile():
        from backend.database import AsyncSessionLocal
        from backend.models.invoice import Invoice, InvoiceLocalStatus
        from backend.services.paypal import fetch_invoice, map_paypal_status_to_local, get_connection_status
        from sqlalchemy import select, and_
        from datetime import timedelta

        conn = get_connection_status()
        if not conn["configured"]:
            return

        async with AsyncSessionLocal() as db:
            # Reconcile invoices not synced in last 2 hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            result = await db.execute(
                select(Invoice).where(
                    and_(
                        Invoice.local_status.in_([
                            InvoiceLocalStatus.PENDING.value,
                            InvoiceLocalStatus.OVERDUE.value,
                        ]),
                        Invoice.paypal_invoice_id.isnot(None),
                        (Invoice.paypal_last_synced_at < cutoff) | (Invoice.paypal_last_synced_at.is_(None)),
                    )
                ).limit(50)
            )
            invoices = result.scalars().all()
            for invoice in invoices:
                try:
                    pp_inv = await fetch_invoice(invoice.paypal_invoice_id)
                    pp_status = pp_inv.get("status", "")
                    local_status = map_paypal_status_to_local(pp_status)
                    invoice.paypal_status = pp_status
                    invoice.local_status = local_status
                    invoice.paypal_last_synced_at = datetime.now(timezone.utc)
                except Exception as e:
                    logger.warning("reconciliation_fetch_failed", invoice_id=str(invoice.id), error=str(e))
            await db.commit()

    run_async(_reconcile())
