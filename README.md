# PayPal RecoverIQ

> **AI-assisted, human-supervised revenue recovery platform for freelancers and small businesses.**
>
> Recover revenue. Reduce manual follow-up.

⚠️ **SANDBOX STATUS**: This application runs in PayPal Sandbox mode by default. No real money is moved. See [Production Readiness](#production-readiness) before going live.

## What It Does

PayPal RecoverIQ helps freelancers and small businesses:
- **Create invoices** via AI natural language ("Invoice Alex for 2 logo designs at $75 each, due in 7 days")
- **Send invoices** through PayPal with explicit human approval
- **Detect overdue invoices** automatically via scheduled scans
- **Send payment reminders** with AI-drafted messages and merchant approval
- **Verify payments** from PayPal webhooks (fetches authoritative status, never trusts webhook alone)
- **Track everything** in a full audit trail

## Architecture

```
Frontend (Next.js 14 + TypeScript + Tailwind)
        │
        │  HTTP API (/api/v1/*)
        ↓
Backend API (FastAPI + Python 3.12)
        ├── Auth (JWT Bearer tokens, Argon2 password hashing)
        ├── Invoice Service (creates/sends/reminds via PayPal REST API v2)
        ├── AI Agent (OpenAI structured extraction, approval-gated actions)
        ├── Recovery Engine (overdue scan, reminder scheduling)
        └── Webhook Handler (PayPal signature verification, idempotent processing)
        │
        ├── PostgreSQL (data, audit logs, idempotency)
        ├── Redis (Celery broker)
        └── Celery Worker + Beat (background jobs, scheduled scans)
```

## Features

- ✅ JWT authentication with Argon2 password hashing
- ✅ AI invoice creation from natural language (OpenAI GPT-4o-mini)
- ✅ PayPal Invoicing REST API v2 integration (Sandbox)
- ✅ Approval workflow — all write actions require explicit human confirmation
- ✅ Webhook processing with signature verification and idempotent deduplication
- ✅ Recovery engine with overdue detection and reminder drafting
- ✅ Rate limiting (max 2 reminders per invoice per day)
- ✅ Celery + Redis background workers and Beat scheduler
- ✅ PostgreSQL with 10+ tables, Decimal money, UTC timestamps
- ✅ Audit log for all actions
- ✅ Responsive dashboard, invoices, AI chat, recovery, settings, audit pages
- ✅ Sandbox mode banner in UI
- ✅ 15 backend acceptance tests

## Prerequisites

- Python 3.12+
- Node.js 20 LTS+
- PostgreSQL 16+
- Redis 7+
- (Optional) PayPal Developer account for Sandbox
- (Optional) OpenAI API key for AI features

## Local Setup

### Windows PowerShell

```powershell
# 1. Clone and enter project
cd E:\PayPal

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r "requirements (3).txt"

# 4. Copy and fill environment variables
Copy-Item .env.example .env
# Edit .env with your values (notepad .env)

# 5. Run database migrations
alembic upgrade head

# 6. (Optional) Seed demo data
python scripts/seed.py

# 7. Start the API server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 8. In a new terminal: Start Celery worker
.venv\Scripts\Activate.ps1
celery -A backend.worker.celery_app worker --loglevel=info -Q default,paypal-webhooks

# 9. In another terminal: Start Celery Beat scheduler
.venv\Scripts\Activate.ps1
celery -A backend.worker.celery_app beat --loglevel=info

# 10. Frontend
cd frontend
npm install
npm run dev
```

> **Note for Windows users:** Celery on Windows requires the `gevent` pool.
> Add `-P gevent` to the worker command if you see threading issues:
> `celery -A backend.worker.celery_app worker --loglevel=info -P gevent -Q default,paypal-webhooks`

### macOS/Linux

```bash
# 1. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Copy and fill environment variables
cp .env.example .env
# Edit .env with your values

# 4. Run database migrations
alembic upgrade head

# 5. (Optional) Seed demo data
python scripts/seed.py

# 6. Start the API (in separate terminals)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
celery -A backend.worker.celery_app worker --loglevel=info -Q default,paypal-webhooks
celery -A backend.worker.celery_app beat --loglevel=info

# 7. Frontend
cd frontend && npm install && npm run dev
```

### Docker Compose (easiest)

```bash
# Copy env file
cp .env.example .env   # Windows: Copy-Item .env.example .env
# Edit .env with your credentials

# Start everything
docker compose up --build

# API:      http://localhost:8000
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

## Required Environment Variables

| Variable                    | Required    | Description                                |
|-----------------------------|-------------|--------------------------------------------|
| `DATABASE_URL`              | Yes         | PostgreSQL async connection URL            |
| `REDIS_URL`                 | Yes         | Redis connection URL                       |
| `APP_SECRET_KEY`            | Yes         | App secret (32+ bytes, random)             |
| `JWT_SECRET_KEY`            | Yes         | JWT signing secret (different from above)  |
| `PAYPAL_CLIENT_ID`          | For PayPal  | PayPal REST app Client ID                  |
| `PAYPAL_CLIENT_SECRET`      | For PayPal  | PayPal REST app Client Secret              |
| `PAYPAL_WEBHOOK_ID`         | For webhooks| Webhook registration ID                    |
| `OPENAI_API_KEY`            | For AI      | OpenAI API key                             |
| `OPENAI_MODEL`              | No          | Model name (default: `gpt-4o-mini`)        |

See `.env.example` for the full list of options with descriptions.
**Never commit `.env` or any real credentials to Git.**

## Database Migrations

```bash
# Apply all migrations (run this after first setup and after updates)
alembic upgrade head

# Check current migration version
alembic current

# Create a new migration after changing models
alembic revision --autogenerate -m "describe your change"

# Roll back one step
alembic downgrade -1
```

## PayPal Sandbox Setup

See [docs/PAYPAL_SETUP.md](docs/PAYPAL_SETUP.md) for detailed step-by-step instructions.

**Quick start:**
1. Go to https://developer.paypal.com/dashboard/
2. Create a Sandbox REST app (type: Merchant)
3. Copy Client ID and Secret to `.env`
4. For webhooks, expose your local server via ngrok: `ngrok http 8000`
5. Register webhook URL: `https://your-ngrok-url/api/v1/webhooks/paypal`
6. Subscribe to `INVOICING.INVOICE.*` events
7. Copy Webhook ID to `.env`

## Running Tests

```bash
# Install test dependencies (if not already installed)
pip install aiosqlite pytest-asyncio pytest-cov httpx

# Run all tests
pytest

# With coverage report
pytest --cov=backend --cov-report=html
# Open htmlcov/index.html to view

# Run a specific test file
pytest tests/test_invoice_calculations.py -v

# Run with verbose output
pytest -v --tb=short
```

## Frontend Checks

```bash
cd frontend
npm install

npm run typecheck   # TypeScript type checking
npm run lint        # ESLint
npm run build       # Production build (catches build errors)
npm run dev         # Development server (http://localhost:3000)
```

## API Documentation

Interactive API docs are available once the backend is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

Key endpoints:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Obtain JWT token |
| GET | `/api/v1/invoices` | List invoices |
| POST | `/api/v1/invoices/drafts` | Create draft invoice |
| POST | `/api/v1/invoices/{id}/send/prepare` | Prepare send (returns approval token) |
| POST | `/api/v1/invoices/{id}/send/confirm` | Confirm send (consumes token, calls PayPal) |
| POST | `/api/v1/agent/commands` | AI invoice extraction |
| GET | `/api/v1/recovery/overdue` | List overdue invoices |
| POST | `/api/v1/webhooks/paypal` | PayPal webhook receiver |
| GET | `/api/v1/audit` | Audit log |
| GET | `/api/v1/integrations/paypal/status` | PayPal integration status |
| GET | `/health` | Health check |

## Troubleshooting

### `alembic: command not found`
Ensure your virtual environment is activated. The `alembic` binary is installed inside `.venv`.

### `asyncpg` connection errors
Ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct. For Docker, run `docker compose up postgres` first.

### Celery worker won't start on Windows
Install gevent: `pip install gevent` and use the `-P gevent` flag.

### PayPal API returns 401
Your `PAYPAL_CLIENT_ID` or `PAYPAL_CLIENT_SECRET` is incorrect. Verify them in the PayPal Developer Dashboard under your Sandbox app.

### Webhook signature verification fails
1. Ensure `PAYPAL_WEBHOOK_ID` matches the ID in your PayPal Dashboard
2. Webhook URL must match exactly (including path, no trailing slash)
3. For local testing, use ngrok with a stable URL (or ngrok with a fixed subdomain)

### OpenAI errors
Set `OPENAI_API_KEY` in `.env`. AI features degrade gracefully — you can still use manual invoice creation without an API key.

### Frontend can't reach the API
Ensure `NEXT_PUBLIC_API_URL` is set correctly. For local dev: `http://localhost:8000/api/v1`.

## Production Readiness

⚠️ **This app is NOT production-ready out of the box.** See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) for the full checklist.

**Bangladesh Country Eligibility Note**: As of November 2026, Bangladesh is not listed as a supported country for PayPal merchant accounts. This means a Bangladesh-based developer/business cannot obtain live PayPal REST API credentials for a PayPal Business account. This app is designed to run in Sandbox mode for the hackathon. For production use, you need a PayPal-eligible merchant account from a supported country, obtained through legitimate means only (no VPN workarounds, no borrowed identity).

Before going live you must:
1. Obtain verified live PayPal Business credentials from an eligible country
2. Set `PAYPAL_ENV=live` and `PAYPAL_BASE_URL=https://api-m.paypal.com`
3. Store all secrets in a secrets manager (not in `.env`)
4. Enable HTTPS, configure CORS for production domain
5. Set up monitoring, alerting, and database backups

## Project Structure

```
E:\PayPal\
├── backend/                    # FastAPI backend
│   ├── core/                   # Security, exceptions, dependencies
│   ├── models/                 # SQLAlchemy ORM models (10+ tables)
│   ├── routes/                 # API route handlers (auth, invoices, agent, etc.)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic (auth, paypal, ai, recovery)
│   ├── config.py               # Pydantic settings (reads from .env)
│   ├── database.py             # Async DB engine + session factory
│   ├── main.py                 # FastAPI app factory, middleware, routes
│   ├── worker.py               # Celery app configuration
│   └── tasks.py                # Celery task definitions
├── frontend/                   # Next.js 14 frontend
│   ├── app/                    # App Router pages
│   ├── components/             # Reusable React components
│   ├── lib/                    # API client, auth context, utilities
│   └── Dockerfile.frontend     # Frontend container image
├── alembic/                    # Database migration framework
│   ├── versions/               # Individual migration scripts
│   └── env.py                  # Alembic configuration
├── tests/                      # Backend test suite (15 tests)
│   ├── conftest.py             # Shared fixtures
│   └── test_*.py               # Test modules
├── scripts/
│   └── seed.py                 # Demo data seeder
├── docs/
│   ├── ARCHITECTURE.md         # System design and decisions
│   ├── PAYPAL_SETUP.md         # PayPal sandbox setup guide
│   ├── PRODUCTION_READINESS.md # Production checklist
│   └── SECURITY.md             # Security documentation
├── docker-compose.yml          # Full stack Docker Compose
├── Dockerfile                  # Backend container image
├── .env.example                # Environment variable template
├── .gitignore
└── README.md
```

## Security Notes

- See [docs/SECURITY.md](docs/SECURITY.md) for the full security documentation.
- Approval tokens are short-lived (15 min), single-use, and bound to a specific action.
- Webhook payloads are always verified against PayPal's signature API before processing.
- All monetary math uses `Decimal`, never `float`.
- Every DB query is scoped to the authenticated user — no cross-tenant data leakage.
