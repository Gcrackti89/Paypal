# Production Readiness Checklist

## Status: SANDBOX ONLY

This application is currently **Sandbox-ready** (suitable for hackathon demonstration) but **NOT production-ready** for live PayPal transactions.

## Hard Blockers for Live Mode

### PayPal Account Eligibility
- [ ] Business owner has a PayPal Business account from a **PayPal-supported country**
  - **Bangladesh is NOT currently supported as a PayPal merchant country**
  - Supported countries: https://www.paypal.com/webapps/mpp/country-worldwide
- [ ] PayPal Business account is verified and in good standing
- [ ] Live REST app created in developer.paypal.com
- [ ] Live Client ID and Client Secret obtained
- [ ] Invoicing API access confirmed on live app

### Technical Requirements
- [ ] HTTPS with valid TLS certificate (required for PayPal webhooks)
- [ ] `PAYPAL_ENV=live` and `PAYPAL_BASE_URL=https://api-m.paypal.com` in production config
- [ ] Live webhook URL registered in PayPal dashboard
- [ ] Live Webhook ID set in `PAYPAL_WEBHOOK_ID`
- [ ] All live credentials in secrets manager (not plain .env)

### Security Requirements
- [ ] Secrets stored in AWS Secrets Manager / HashiCorp Vault / similar
- [ ] No `.env` file in production deployment
- [ ] Database using TLS/SSL connection
- [ ] Redis secured with password/TLS
- [ ] CORS origins restricted to production domain only
- [ ] Rate limiting configured for production traffic levels
- [ ] Sentry or equivalent error monitoring enabled

### Operational Requirements
- [ ] Database backups configured
- [ ] Monitoring and alerting set up
- [ ] Log aggregation set up
- [ ] Database migrations tested on production-equivalent data
- [ ] End-to-end production test with real sandbox → live migration

## What Works in Sandbox Mode

- Full invoice creation, sending, reminders, cancellation
- Webhook reception and processing
- AI invoice extraction
- Recovery scanning and recommendations
- Audit logging
- All frontend pages
- All backend tests

## Deployment Architecture (Recommended)

```
Cloud Provider (AWS / GCP / Azure)
├── API: Container (ECS / Cloud Run / App Service)
├── Worker: Container (same image, different CMD)
├── Beat: Container (same image, different CMD)
├── Database: Managed PostgreSQL (RDS / Cloud SQL)
├── Redis: Managed Redis (ElastiCache / Memorystore)
├── Secrets: AWS Secrets Manager / GCP Secret Manager
└── Frontend: Vercel / Next.js deployed separately
```
