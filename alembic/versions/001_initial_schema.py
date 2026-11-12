"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-10 00:00:00.000000

"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # users                                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------ #
    # merchant_settings                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "merchant_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("auto_reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reminder_days_before_due", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reminder_quiet_hours_start", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("reminder_quiet_hours_end", sa.Integer(), nullable=False, server_default="8"),
        sa.Column(
            "reminder_days_after_due",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="[1, 3, 7]",
        ),
        sa.Column("paypal_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paypal_account_email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_merchant_settings_user_id"),
    )
    op.create_index("ix_merchant_settings_user_id", "merchant_settings", ["user_id"], unique=True)

    # ------------------------------------------------------------------ #
    # customers                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "email", name="uq_customer_user_email"),
    )
    op.create_index("ix_customers_user_id", "customers", ["user_id"])
    op.create_index("ix_customers_email", "customers", ["email"])

    # ------------------------------------------------------------------ #
    # invoices                                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        # PayPal fields
        sa.Column("paypal_invoice_id", sa.String(64), nullable=True),
        sa.Column("paypal_invoice_number", sa.String(64), nullable=True),
        sa.Column("paypal_status", sa.String(64), nullable=True),
        sa.Column("paypal_invoice_url", sa.String(1024), nullable=True),
        sa.Column("paypal_payment_url", sa.String(1024), nullable=True),
        sa.Column("paypal_last_synced_at", sa.DateTime(timezone=True), nullable=True),
        # Invoice details
        sa.Column("local_status", sa.String(64), nullable=False, server_default="DRAFT"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("amount_due", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("amount_paid", sa.Numeric(precision=18, scale=2), nullable=True),
        # Denormalized customer info
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        # Reminder tracking
        sa.Column("reminder_count_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reminder_count_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_count_reset_date", sa.Date(), nullable=True),
        # AI metadata
        sa.Column("ai_created", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_session_id", sa.String(64), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_paypal_invoice_id", "invoices", ["paypal_invoice_id"], unique=True)
    op.create_index("ix_invoices_local_status", "invoices", ["local_status"])
    op.create_index("ix_invoices_user_id_status", "invoices", ["user_id", "local_status"])
    op.create_index("ix_invoices_user_id_due_date", "invoices", ["user_id", "due_date"])

    # ------------------------------------------------------------------ #
    # invoice_items                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # ------------------------------------------------------------------ #
    # approval_requests                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(128), nullable=False),
        sa.Column("payload_summary", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_approval_request_token"),
    )
    op.create_index("ix_approval_requests_user_id", "approval_requests", ["user_id"])
    op.create_index("ix_approval_requests_invoice_id", "approval_requests", ["invoice_id"])
    op.create_index("ix_approval_requests_token", "approval_requests", ["token"], unique=True)

    # ------------------------------------------------------------------ #
    # recovery_actions                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "recovery_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="PENDING"),
        sa.Column("days_overdue", sa.Integer(), nullable=True),
        sa.Column("previous_reminders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("draft_message", sa.Text(), nullable=True),
        sa.Column("paypal_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
    )
    op.create_index("ix_recovery_actions_user_id", "recovery_actions", ["user_id"])
    op.create_index("ix_recovery_actions_invoice_id", "recovery_actions", ["invoice_id"])
    op.create_index("ix_recovery_actions_status", "recovery_actions", ["status"])

    # ------------------------------------------------------------------ #
    # webhook_events                                                       #
    # ------------------------------------------------------------------ #
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("paypal_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("paypal_event_id", name="uq_webhook_paypal_event_id"),
    )
    op.create_index("ix_webhook_events_paypal_event_id", "webhook_events", ["paypal_event_id"], unique=True)
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_resource_id", "webhook_events", ["resource_id"])
    op.create_index("ix_webhook_events_processed", "webhook_events", ["processed"])

    # ------------------------------------------------------------------ #
    # idempotency_records                                                  #
    # ------------------------------------------------------------------ #
    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("key", name="uq_idempotency_key"),
    )
    op.create_index("ix_idempotency_records_key", "idempotency_records", ["key"], unique=True)

    # ------------------------------------------------------------------ #
    # audit_logs                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("idempotency_records")
    op.drop_table("webhook_events")
    op.drop_table("recovery_actions")
    op.drop_table("approval_requests")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("customers")
    op.drop_table("merchant_settings")
    op.drop_table("users")
