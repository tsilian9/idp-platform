"""Initial schema — environments and audit_logs tables

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    environment_tier = postgresql.ENUM("dev", "staging", "prod", name="environment_tier")
    environment_status = postgresql.ENUM(
        "Pending", "Provisioning", "Ready", "Failed", "Deleting",
        name="environment_status",
    )
    environment_tier.create(op.get_bind(), checkfirst=True)
    environment_status.create(op.get_bind(), checkfirst=True)

    # environments table
    op.create_table(
        "environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(63), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("tier", sa.Enum("dev", "staging", "prod", name="environment_tier"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("Pending", "Provisioning", "Ready", "Failed", "Deleting", name="environment_status"),
            nullable=False,
        ),
        sa.Column("database_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("namespace", sa.String(63), nullable=True),
        sa.Column("message", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_environments_name", "environments", ["name"], unique=True)
    op.create_index("ix_environments_owner", "environments", ["owner"])
    op.create_index("ix_environments_status", "environments", ["status"])

    # audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_environment_id", "audit_logs", ["environment_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("environments")
    op.execute("DROP TYPE IF EXISTS environment_status")
    op.execute("DROP TYPE IF EXISTS environment_tier")
