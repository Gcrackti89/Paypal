# PayPal RecoverIQ — implementation and live-readiness requirements

## 1. Product scope

Build an AI-assisted, human-supervised revenue recovery application for freelancers and small businesses. The app must:

1. Connect to one PayPal merchant REST app using OAuth 2.0 client credentials.
2. Create a draft invoice through PayPal Invoicing API v2.
3. Show a validated invoice preview and require explicit merchant approval before sending.
4. Send the invoice through PayPal and persist the PayPal invoice ID, invoice number, amount, currency, due date and status.
5. Receive and verify PayPal Invoicing webhooks.
6. Deduplicate webhook event IDs and process verified events asynchronously.
7. Fetch the current PayPal invoice resource before changing local payment state; webhook events are triggers, not final proof of a fully paid invoice.
8. Find overdue/unpaid invoices, create a reminder recommendation and require approval unless the merchant has explicitly enabled a narrowly scoped reminder policy.
9. Check current invoice status immediately before every reminder; never remind paid, cancelled or otherwise ineligible invoices.
10. Enforce a local reminder cap of no more than two reminders per invoice per day, matching PayPal's documented API limit.
11. Maintain an audit log for AI recommendations, approvals, PayPal requests, webhook events and state changes.
12. Provide a dashboard for outstanding amount, overdue invoices, paid invoices and recent recovery actions.

## 2. Recommended architecture

- Backend: FastAPI, Python 3.12, SQLAlchemy async, PostgreSQL.
- PayPal integration: direct REST calls through HTTPX; do not expose client secret to the browser.
- AI: OpenAI API with constrained structured output / function calling. The model may recommend or request an action, but backend policy code validates every tool call.
- Job processing: Celery + Redis. Use Celery Beat for scheduled overdue-invoice scans; do not use an in-process timer for production scheduling.
- Frontend: Next.js + TypeScript + Tailwind CSS. The JavaScript dependencies belong in `package.json`, not Python `requirements.txt`.
- Database migrations: Alembic.
- Hosting: deploy the API and Celery worker/beat as separate processes; use managed PostgreSQL and Redis; publish webhook endpoint over HTTPS.

## 3. PayPal REST endpoints used

Base URL:
- Sandbox: `https://api-m.sandbox.paypal.com`
- Live: `https://api-m.paypal.com`

OAuth:
- `POST /v1/oauth2/token` using HTTP Basic authentication with Client ID and Client Secret.
- Cache access tokens until shortly before expiry; do not request a new token for every API call.

Invoicing API v2:
- `POST /v2/invoicing/invoices` — create draft invoice.
- `GET /v2/invoicing/invoices/{invoice_id}` — fetch authoritative current status.
- `POST /v2/invoicing/invoices/{invoice_id}/send` — send after user approval.
- `POST /v2/invoicing/invoices/{invoice_id}/remind` — send PayPal invoice reminder.
- `POST /v2/invoicing/search-invoices` — find invoices using supported search criteria.
- `POST /v2/invoicing/invoices/{invoice_id}/cancel` — cancel only after explicit merchant approval.

Webhook verification:
- Use PayPal's `POST /v1/notifications/verify-webhook-signature` endpoint, or implement the official cryptographic verification exactly. Never trust an unverified webhook payload.
- Register the webhook against the exact REST app whose credentials create/send the invoices.

Recommended Invoicing event subscriptions (confirm names in the live/sandbox app dashboard):
- `INVOICING.INVOICE.CREATED`
- `INVOICING.INVOICE.SENT`
- `INVOICING.INVOICE.PAID`
- `INVOICING.INVOICE.CANCELLED`
- `INVOICING.INVOICE.REFUNDED`
- `INVOICING.INVOICE.UPDATED`
- `INVOICING.INVOICE.SCHEDULED`

Important: PayPal documents `INVOICING.INVOICE.PAID` for invoice payment activity that can include partially paid or pending payment states. Always fetch the current invoice and interpret its actual status/balance before marking the local invoice as fully paid or stopping/starting collection actions.

## 4. AI agent boundaries

The AI agent may:
- Extract invoice/customer details from merchant instructions.
- Summarize invoice aging and payment activity.
- Recommend a follow-up time and draft a reminder note.
- Call read-only tools such as list/search invoices and get invoice details.
- Prepare a proposed reminder or cancellation for review.

The AI agent must NOT:
- Calculate or alter authoritative totals without deterministic backend validation.
- Send an invoice, reminder, cancel an invoice, issue a refund or otherwise move money without the required merchant authorization.
- Mark an invoice paid based only on an AI inference or a webhook payload.
- Change customer bank/payment details or bypass PayPal controls.

Use server-side allowlists, typed Pydantic schemas, ownership checks, confirmation tokens, idempotency keys, and audit records for all write actions.

## 5. Reliability and security requirements

- Store secrets only in a secrets manager or server-side environment variables.
- Never commit `.env`; rotate any exposed credentials immediately.
- Use HTTPS in deployed environments.
- Verify webhook signatures before processing; persist event IDs with a unique constraint to make processing idempotent.
- Acknowledge verified webhooks quickly with HTTP 2xx and enqueue processing; process asynchronously.
- Expect duplicate and out-of-order webhook deliveries.
- Use `PayPal-Request-Id` on supported write requests and maintain a local idempotency table as a second safeguard.
- Cache OAuth tokens and use bounded timeouts/retries with exponential backoff for transient network/5xx/429 errors. Do not retry non-retryable validation/authorization errors blindly.
- Use webhooks as the primary status signal; use scheduled reconciliation as a fallback, not aggressive polling.
- Enforce per-user authorization and database row ownership; use database transactions for state transitions.
- Add rate limiting, structured logs, health checks, backups, migrations and error monitoring before production.
- Redact access tokens, client secrets, full webhook headers and sensitive payer details from logs.

## 6. Environment and infrastructure

Required:
- Python 3.12.x
- PostgreSQL 16+ (or managed PostgreSQL compatible with asyncpg)
- Redis 7+ (or managed Redis compatible with Celery)
- HTTPS public URL for PayPal webhook delivery
- PayPal Developer app with Invoicing API access and configured webhook ID
- OpenAI API key and a model enabled for that API account

For the recommended Next.js frontend:
- Node.js 22 LTS or newer supported LTS
- npm/pnpm and a `package.json` for the frontend dependencies

## 7. Sandbox-to-live gate

Do not set `PAYPAL_ENV=live` until all of the following are true:
- The business/account owner is legally eligible to hold and operate a PayPal Business account in a supported country.
- The PayPal Business account is verified and Invoicing is enabled.
- The live REST app and live Client ID/Secret are issued by PayPal.
- Live webhook URL and event subscriptions are configured.
- End-to-end test cases pass, including duplicate webhooks, out-of-order events, partial payments, failed requests, overdue reminders, cancellations and paid invoices.
- Merchant authorization and audit logging are active.

Never use a false address, VPN, borrowed identity or another person's credentials to bypass country eligibility. If the project owner cannot obtain live PayPal merchant credentials in their jurisdiction, use Sandbox for the hackathon and arrange a legitimate eligible merchant account for production, or choose a payment provider supported for the actual operating country.

## 8. Install and run dependencies

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env`, fill in Sandbox credentials and configure PostgreSQL and Redis before starting the API and worker.
