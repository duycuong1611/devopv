"""initial relayops schema

Revision ID: 20260622_0001
Revises:
Create Date: 2026-06-22 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260622_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("delivery_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("repository", sa.String(length=255), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("delivery_id", name="uq_webhook_events_delivery_id"),
    )
    op.create_index("ix_webhook_events_delivery_id", "webhook_events", ["delivery_id"])
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_repository", "webhook_events", ["repository"])
    op.create_index("ix_webhook_events_received_at", "webhook_events", ["received_at"])

    op.create_table(
        "deployment_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=50), server_default="deployment", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("logs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["webhook_events.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_deployment_jobs_event_id", "deployment_jobs", ["event_id"])
    op.create_index("ix_deployment_jobs_status", "deployment_jobs", ["status"])
    op.create_index("ix_deployment_jobs_created_at", "deployment_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_deployment_jobs_created_at", table_name="deployment_jobs")
    op.drop_index("ix_deployment_jobs_status", table_name="deployment_jobs")
    op.drop_index("ix_deployment_jobs_event_id", table_name="deployment_jobs")
    op.drop_table("deployment_jobs")
    op.drop_index("ix_webhook_events_received_at", table_name="webhook_events")
    op.drop_index("ix_webhook_events_repository", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_index("ix_webhook_events_delivery_id", table_name="webhook_events")
    op.drop_table("webhook_events")
