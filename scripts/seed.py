#!/usr/bin/env python
"""Seed demo data for hackathon demonstration.
All seed data is clearly labelled DEMO and uses no real PayPal invoices.
Run: python scripts/seed.py
"""
from __future__ import annotations
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from decimal import Decimal
from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.models.customer import Customer
from backend.models.invoice import Invoice, InvoiceItem, InvoiceLocalStatus
from backend.models.recovery import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from backend.models.audit import AuditLog, AuditAction
from backend.models.merchant_settings import MerchantSettings
from backend.core.security import hash_password
from sqlalchemy import select

# DEMO credentials - change before use
DEMO_EMAIL = "demo@recoveriq.example.com"
DEMO_PASSWORD = "DemoPass123!"
DEMO_NAME = "Demo Merchant [SANDBOX]"

DEMO_CUSTOMERS = [
    {"name": "Alice Johnson [DEMO]", "email": "alice.demo@example.com", "company": "Acme Corp [DEMO]"},
    {"name": "Bob Williams [DEMO]", "email": "bob.demo@example.com", "company": "Tech Startup [DEMO]"},
    {"name": "Carol Davis [DEMO]", "email": "carol.demo@example.com", "company": "Design Studio [DEMO]"},
]

DEMO_INVOICES = [
    {
        "customer_idx": 0,
        "items": [{"desc": "Web Design [DEMO]", "qty": "3", "price": "500.00"}],
        "due_offset": -10,  # 10 days ago - OVERDUE
        "status": InvoiceLocalStatus.OVERDUE.value,
        "paypal_id": None,  # No real PayPal ID
        "reminders": 1,
    },
    {
        "customer_idx": 1,
        "items": [
            {"desc": "Logo Design [DEMO]", "qty": "2", "price": "150.00"},
            {"desc": "Business Cards [DEMO]", "qty": "1", "price": "75.00"},
        ],
        "due_offset": -3,  # 3 days ago - OVERDUE
        "status": InvoiceLocalStatus.OVERDUE.value,
        "paypal_id": None,
        "reminders": 0,
    },
    {
        "customer_idx": 2,
        "items": [{"desc": "SEO Consulting [DEMO]", "qty": "5", "price": "120.00"}],
        "due_offset": 7,  # Due in 7 days - PENDING
        "status": InvoiceLocalStatus.PENDING.value,
        "paypal_id": None,
        "reminders": 0,
    },
    {
        "customer_idx": 0,
        "items": [{"desc": "Content Writing [DEMO]", "qty": "10", "price": "50.00"}],
        "due_offset": -30,  # Paid last month
        "status": InvoiceLocalStatus.PAID.value,
        "paypal_id": None,
        "reminders": 2,
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if demo user exists
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()

        if user:
            print(f"Demo user already exists: {DEMO_EMAIL}")
        else:
            user = User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=DEMO_NAME,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()

            settings = MerchantSettings(user_id=user.id, timezone="UTC")
            db.add(settings)
            print(f"Created demo user: {DEMO_EMAIL}")

        # Create customers
        customers = []
        for c_data in DEMO_CUSTOMERS:
            result = await db.execute(
                select(Customer).where(Customer.user_id == user.id, Customer.email == c_data["email"])
            )
            customer = result.scalar_one_or_none()
            if not customer:
                customer = Customer(
                    user_id=user.id,
                    name=c_data["name"],
                    email=c_data["email"],
                    company=c_data["company"],
                )
                db.add(customer)
                await db.flush()
                customers.append(customer)
                print(f"  Created customer: {c_data['name']}")
            else:
                customers.append(customer)

        # Create invoices
        for inv_data in DEMO_INVOICES:
            customer = customers[inv_data["customer_idx"]]
            due_date = date.today() + timedelta(days=inv_data["due_offset"])

            total = sum(Decimal(it["qty"]) * Decimal(it["price"]) for it in inv_data["items"])

            invoice = Invoice(
                user_id=user.id,
                customer_id=customer.id,
                customer_name=customer.name,
                customer_email=customer.email,
                currency="USD",
                total_amount=total,
                amount_due=total if inv_data["status"] != InvoiceLocalStatus.PAID.value else Decimal("0"),
                amount_paid=total if inv_data["status"] == InvoiceLocalStatus.PAID.value else Decimal("0"),
                local_status=inv_data["status"],
                due_date=due_date,
                invoice_date=due_date - timedelta(days=14),
                note="[DEMO DATA - No real PayPal transaction]",
                ai_created=False,
                reminder_count_total=inv_data["reminders"],
            )
            db.add(invoice)
            await db.flush()

            for it in inv_data["items"]:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=it["desc"],
                    quantity=Decimal(it["qty"]),
                    unit_price=Decimal(it["price"]),
                    amount=Decimal(it["qty"]) * Decimal(it["price"]),
                )
                db.add(item)

            print(f"  Created invoice: {customer.name} - ${total} ({inv_data['status']})")

            # Audit entry
            audit = AuditLog(
                user_id=user.id,
                action=AuditAction.INVOICE_DRAFT_CREATED.value,
                resource_type="invoice",
                resource_id=str(invoice.id),
                description=f"[SEED] Demo invoice created for {customer.email}",
            )
            db.add(audit)

        await db.commit()
        print("\n✅ Demo data seeded successfully!")
        print(f"   Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print("   NOTE: All data is marked [DEMO] - no real PayPal transactions.")


if __name__ == "__main__":
    asyncio.run(seed())
