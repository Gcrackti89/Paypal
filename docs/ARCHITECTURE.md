# Architecture Overview

## Component Diagram

```
[Browser]
    | HTTPS
[Next.js Frontend] --HTTP--> [FastAPI Backend]
                                    |      |
                                    |      |
                             +--[PostgreSQL]--+
                                    |      |
                             +--[Redis]------+
                                    |      |
                             +--[Celery Worker]
                                    |      |
                             +--[Celery Beat]
                                    |
 [PayPal API] <---HTTPS------------+
 [OpenAI API] <---HTTPS------------+
```

## Key Design Decisions

### 1. Human-in-the-loop Approval
Every write action (send invoice, send reminder, cancel) requires a two-step process:
1. `prepare` endpoint creates a short-lived, single-use approval token
2. `confirm` endpoint validates the token and executes the action

This prevents the AI from triggering PayPal actions without explicit merchant consent.

### 2. Webhook as Trigger, Not Proof
Webhooks are used only as triggers to fetch the authoritative invoice status from PayPal.
We never mark an invoice as paid based solely on the webhook payload.

### 3. Decimal Arithmetic
All monetary calculations use Python's `Decimal` type. We never use `float` for money.

### 4. Status Priority System
Invoice status transitions are protected by a priority system that prevents out-of-order webhooks from regressing an invoice to a lower-priority state (e.g., SENT event cannot override PAID status).

### 5. Idempotency
- PayPal write requests use `PayPal-Request-Id` header
- Webhook events deduplicated by `paypal_event_id` (unique constraint)
- Approval tokens are single-use

### 6. Tenant Isolation
Every database query includes `WHERE user_id = :current_user_id`.
There is no shared state between users except the system-level infrastructure.

## API Flow: Create and Send Invoice

```
1. POST /api/v1/agent/commands {message: "Invoice Alex for..."}
   -> AI extracts: customer, items, currency, due date
2. POST /api/v1/invoices/drafts {customer_name, items, ...}
   -> Creates local draft + PayPal draft invoice
3. POST /api/v1/invoices/{id}/send/prepare
   -> Creates approval token (15 min TTL)
   -> Returns: {approval_token, payload_summary, expires_at}
4. UI shows confirmation modal with exact action details
5. POST /api/v1/invoices/{id}/send/confirm {approval_token}
   -> Validates + consumes token (atomic)
   -> Calls PayPal /send endpoint
   -> Fetches authoritative PayPal status
   -> Updates local status
   -> Writes audit log
```
