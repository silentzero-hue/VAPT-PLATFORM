"""Security hardening: TOTP lockout columns, TOTP-secret size for Fernet,
NessusScanCache created_at rename, partial unique index for findings/ports.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. TOTP-specific lockout (parallel to failed_login_count)
    op.add_column(
        "users",
        sa.Column("totp_failed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("totp_locked_until", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Resize totp_secret to hold Fernet ciphertext (was plaintext base32).
    #    Existing rows (if any) are kept as-is; the auth service treats any
    #    string that does NOT decrypt as no TOTP configured, which is safe.
    op.alter_column("users", "totp_secret", type_=sa.String(512), existing_type=sa.String(64))

    # 3. Replace the NULL-unsafe unique constraint on findings with two
    #    NULLS-distinct partial indexes. Postgres treats NULLs as distinct
    #    in regular unique constraints, so a (vuln, asset, engagement, NULL)
    #    tuple could be inserted N times. Splitting into port-IS-NULL and
    #    port-IS-NOT-NULL partial indexes makes duplicates impossible.
    op.drop_constraint("uq_finding_unique", "findings", type_="unique")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_finding_unique_port
        ON findings (vulnerability_id, asset_id, engagement_id, port)
        WHERE port IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_finding_unique_noport
        ON findings (vulnerability_id, asset_id, engagement_id)
        WHERE port IS NULL
        """
    )

    # 4. Same fix for assets: (workspace_id, type, value, port) with port
    #    included so the same host:port on multiple protocols stays distinct.
    op.drop_constraint("uq_asset_per_workspace", "assets", type_="unique")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_per_ws
        ON assets (workspace_id, type, value, port)
        WHERE port IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_per_ws_noport
        ON assets (workspace_id, type, value)
        WHERE port IS NULL
        """
    )

    # 5. Workspace scope indexes that were missing
    op.create_index("ix_ij_submitted_by", "ingestion_jobs", ["submitted_by"])
    op.create_index("ix_fact_actor", "finding_activity", ["actor_id"])
    op.create_index("ix_find_threat_intel", "findings", ["threat_intel_id"])
    op.create_index("ix_fev_blob", "finding_evidence", ["evidence_blob_id"])
    op.create_index("ix_fc_author", "finding_comments", ["author_id"])
    op.create_index("ix_lum_workspace", "ldap_user_mappings", ["workspace_id"])
    op.create_index("ix_retest_workspace", "retest_cycles", ["workspace_id"])
    op.create_index("ix_retest_retest_eng", "retest_cycles", ["retest_engagement_id"])
    op.create_index("ix_portal_creator", "portal_shares", ["created_by"])
    op.create_index("ix_token_creator", "api_tokens", ["created_by"])
    op.create_index("ix_wh_workspace", "webhook_deliveries", ["workspace_id"])
    op.create_index("ix_msc_actor", "agent_runs", ["actor_id"])
    op.create_index("ix_add_reviewer", "agent_draft_diffs", ["reviewer_id"])
    op.create_index("ix_add_engagement", "agent_draft_diffs", ["engagement_id"])

    # 6. Engagement code unique per workspace
    op.create_unique_constraint("uq_eng_ws_code", "engagements", ["workspace_id", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_eng_ws_code", "engagements", type_="unique")
    op.drop_index("ix_add_engagement", "agent_draft_diffs")
    op.drop_index("ix_add_reviewer", "agent_draft_diffs")
    op.drop_index("ix_msc_actor", "agent_runs")
    op.drop_index("ix_wh_workspace", "webhook_deliveries")
    op.drop_index("ix_token_creator", "api_tokens")
    op.drop_index("ix_portal_creator", "portal_shares")
    op.drop_index("ix_retest_retest_eng", "retest_cycles")
    op.drop_index("ix_retest_workspace", "retest_cycles")
    op.drop_index("ix_lum_workspace", "ldap_user_mappings")
    op.drop_index("ix_fc_author", "finding_comments")
    op.drop_index("ix_fev_blob", "finding_evidence")
    op.drop_index("ix_find_threat_intel", "findings")
    op.drop_index("ix_fact_actor", "finding_activity")
    op.drop_index("ix_ij_submitted_by", "ingestion_jobs")

    op.execute("DROP INDEX IF EXISTS uq_asset_per_ws_noport")
    op.execute("DROP INDEX IF EXISTS uq_asset_per_ws")
    op.execute("DROP INDEX IF EXISTS uq_finding_unique_noport")
    op.execute("DROP INDEX IF EXISTS uq_finding_unique_port")
    op.execute(
        "ALTER TABLE assets ADD CONSTRAINT uq_asset_per_workspace "
        "UNIQUE (workspace_id, type, value, port)"
    )
    op.execute(
        "ALTER TABLE findings ADD CONSTRAINT uq_finding_unique "
        "UNIQUE (vulnerability_id, asset_id, engagement_id, port)"
    )

    op.alter_column("users", "totp_secret", type_=sa.String(64), existing_type=sa.String(512))
    op.drop_column("users", "totp_locked_until")
    op.drop_column("users", "totp_failed_count")
