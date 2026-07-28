"""add nessus_servers, nessus_scan_cache, multi_scan_jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nessus_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("access_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("request_timeout", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("only_completed_scans", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(40), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Index("ix_ns_workspace", "workspace_id", unique=True),
    )
    op.create_table(
        "nessus_scan_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nessus_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(400), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("policy", sa.String(200), nullable=True),
        sa.Column("scan_type", sa.String(40), nullable=True),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_meta", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Index("ix_nsc_server_scan", "server_id", "scan_id", unique=True),
    )
    op.create_table(
        "multi_scan_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scan_ingestion_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("baseline_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Index("ix_msj_workspace", "workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("multi_scan_jobs")
    op.drop_table("nessus_scan_cache")
    op.drop_table("nessus_servers")
