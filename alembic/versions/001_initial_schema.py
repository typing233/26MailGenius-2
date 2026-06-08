"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("uq_users_tenant_email_active", "users", ["tenant_id", "email"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    # User Roles
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_user_roles", "user_roles", ["user_id", "tenant_id", "role"])

    # Refresh Tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Subscribers
    op.create_table(
        "subscribers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("custom_fields", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_subscribers_tenant_id", "subscribers", ["tenant_id"])
    op.create_index("uq_subscribers_tenant_email_active", "subscribers", ["tenant_id", "email"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_subscribers_tenant_status", "subscribers", ["tenant_id", "status"])

    # Mailing Lists
    op.create_table(
        "mailing_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("list_type", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mailing_lists_tenant_id", "mailing_lists", ["tenant_id"])
    op.create_index("uq_mailing_lists_tenant_name_active", "mailing_lists", ["tenant_id", "name"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    # List Subscribers (M2M)
    op.create_table(
        "list_subscribers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailing_lists.id"), nullable=False),
        sa.Column("subscriber_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscribers.id"), nullable=False),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_list_subscribers_tenant_id", "list_subscribers", ["tenant_id"])
    op.create_index("ix_list_subscribers_list", "list_subscribers", ["list_id"])
    op.create_index("ix_list_subscribers_subscriber", "list_subscribers", ["subscriber_id"])
    op.create_index("uq_list_subscribers_active", "list_subscribers", ["tenant_id", "list_id", "subscriber_id"], unique=True, postgresql_where=sa.text("unsubscribed_at IS NULL"))

    # Confirmation Tokens
    op.create_table(
        "confirmation_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("subscriber_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscribers.id"), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailing_lists.id"), nullable=True),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_confirmation_tokens_tenant_id", "confirmation_tokens", ["tenant_id"])

    # Import Jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dedup_key", sa.String(255), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_rows", sa.Integer, server_default=sa.text("0")),
        sa.Column("processed_rows", sa.Integer, server_default=sa.text("0")),
        sa.Column("success_rows", sa.Integer, server_default=sa.text("0")),
        sa.Column("error_rows", sa.Integer, server_default=sa.text("0")),
        sa.Column("error_details", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_jobs_tenant_id", "import_jobs", ["tenant_id"])

    # Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_tenant_entity", "audit_logs", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", sa.text("created_at DESC")])

    # Embed Form Configs
    op.create_table(
        "embed_form_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailing_lists.id"), nullable=False),
        sa.Column("allowed_domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("honeypot_field_name", sa.String(50), nullable=False, server_default="website"),
        sa.Column("captcha_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("captcha_provider", sa.String(20), nullable=True),
        sa.Column("captcha_site_key", sa.String(255), nullable=True),
        sa.Column("captcha_secret_key", sa.String(255), nullable=True),
        sa.Column("rate_limit_per_ip", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("custom_css", sa.Text, nullable=True),
        sa.Column("redirect_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_embed_form_configs_tenant_id", "embed_form_configs", ["tenant_id"])

    # Send Queue Jobs
    op.create_table(
        "send_queue_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscriber_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscribers.id"), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailing_lists.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_send_queue_status_scheduled", "send_queue_jobs", ["status", "scheduled_at"])
    op.create_index("ix_send_queue_tenant_campaign", "send_queue_jobs", ["tenant_id", "campaign_id"])


def downgrade() -> None:
    op.drop_table("send_queue_jobs")
    op.drop_table("embed_form_configs")
    op.drop_table("audit_logs")
    op.drop_table("import_jobs")
    op.drop_table("confirmation_tokens")
    op.drop_table("list_subscribers")
    op.drop_table("mailing_lists")
    op.drop_table("subscribers")
    op.drop_table("refresh_tokens")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("tenants")
