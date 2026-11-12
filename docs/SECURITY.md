# Security Documentation

## Secrets Management

- All secrets are loaded from server-side environment variables only
- `.env` files are in `.gitignore` and must never be committed
- PayPal credentials, JWT secrets, and OpenAI keys are never sent to the browser
- PayPal status endpoint returns only a truncated client_id prefix, never the secret

## Authentication

- Passwords hashed with Argon2 (via pwdlib)
- JWT Bearer tokens with configurable expiry (default 30 minutes)
- All API endpoints except `/health`, `/ready`, `/api/v1/auth/register`, `/api/v1/auth/login`, and `/api/v1/webhooks/paypal` require authentication
- Token ownership enforced in every database query (users can only access their own data)

## Approval Workflow

- Write actions (send invoice, send reminder, cancel invoice) require a valid approval token
- Approval tokens are:
  - Short-lived (15 minutes)
  - Single-use (consumed atomically on first use)
  - Tied to specific user + invoice + action + payload hash
  - Cannot be replayed or used by another user

## Webhook Security

- All incoming webhooks verified with PayPal's signature verification API
- Invalid signatures are rejected with 400
- Webhook event IDs deduplicated with a unique database constraint
- Webhooks acknowledged immediately (HTTP 200) and processed asynchronously

## AI Security

- System prompt includes explicit injection-attack defense rules
- User input is treated as untrusted data throughout the pipeline
- AI totals are never trusted; backend recalculates using Decimal arithmetic
- AI is blocked from executing write operations directly

## Input Validation

- All inputs validated with Pydantic schemas with strict type checking
- Email validation, currency allowlist, positive-only quantities, length limits
- SQL injection protection via SQLAlchemy ORM (parameterized queries)
- Sensitive data never logged (tokens, secrets, payment details)
