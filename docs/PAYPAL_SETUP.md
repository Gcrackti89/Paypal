# PayPal Sandbox Setup Guide

## Overview

This app uses PayPal REST API v2 for invoice operations. You must use Sandbox for development and testing. Live mode requires a verified PayPal Business account from a supported country.

## Step 1: Create a PayPal Developer Account

1. Go to https://developer.paypal.com
2. Sign in with your personal PayPal account (create one if needed)
3. Navigate to "My Apps & Credentials"

## Step 2: Create a Sandbox REST App

1. Under "Sandbox" tab, click "Create App"
2. Give it a name: e.g., "RecoverIQ Dev"
3. Select app type: Merchant
4. Click Create App
5. Copy **Client ID** → set as `PAYPAL_CLIENT_ID` in `.env`
6. Click **Show** next to Secret → copy as `PAYPAL_CLIENT_SECRET` in `.env`

## Step 3: Enable Required Features

In your app settings, ensure these are enabled:
- Invoicing (should be enabled by default)
- Webhooks

## Step 4: Set Up Webhooks

Webhooks require a **public HTTPS URL**. For local development, use ngrok:

```bash
# Install ngrok: https://ngrok.com
ngrok http 8000
# Note the https URL, e.g. https://abc123.ngrok.io
```

1. In PayPal Developer Dashboard → Your App → Webhooks
2. Click "Add Webhook"
3. Set URL: `https://your-ngrok-url.ngrok.io/api/v1/webhooks/paypal`
4. Subscribe to these events:
   - `INVOICING.INVOICE.CREATED`
   - `INVOICING.INVOICE.SENT`
   - `INVOICING.INVOICE.PAID`
   - `INVOICING.INVOICE.CANCELLED`
   - `INVOICING.INVOICE.REFUNDED`
   - `INVOICING.INVOICE.UPDATED`
   - `INVOICING.INVOICE.SCHEDULED`
5. Click Save
6. Copy **Webhook ID** → set as `PAYPAL_WEBHOOK_ID` in `.env`

## Step 5: Sandbox Test Accounts

1. Go to https://developer.paypal.com/dashboard/accounts
2. PayPal creates default Business and Personal accounts
3. Use the **Business** account to send invoices
4. Use the **Personal** account to simulate paying invoices

## Step 6: Verify Configuration

```bash
# Start the API and check:
curl http://localhost:8000/api/v1/integrations/paypal/status
# Should show: {"configured": true, "environment": "sandbox", ...}
```

## Sandbox vs Live Separation

|                 | Sandbox                              | Live                        |
|-----------------|--------------------------------------|-----------------------------|
| Base URL        | `https://api-m.sandbox.paypal.com`   | `https://api-m.paypal.com`  |
| Credentials     | Sandbox Client ID/Secret             | Live Client ID/Secret       |
| Transactions    | Fake / simulated                     | Real money                  |
| Webhook events  | Test only                            | Real events                 |

## Country Eligibility Warning

**Bangladesh is not currently a supported PayPal merchant country.**

This means:
- A Bangladesh-based developer cannot create a live PayPal Business account
- Live REST API credentials are not available from Bangladesh
- Sandbox works fine for development and demonstrations

For production, you need:
1. A PayPal-eligible merchant from a supported country
2. A verified PayPal Business account
3. Live app credentials from https://developer.paypal.com
4. HTTPS webhook endpoint
5. Explicit `PAYPAL_ENV=live` and updated `PAYPAL_BASE_URL` in production config

**Never use a VPN, false address, or another person's identity to bypass eligibility.**
