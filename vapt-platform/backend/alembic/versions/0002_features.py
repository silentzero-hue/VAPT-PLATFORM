"""v2 schema: 12 new tables, 4 new columns on existing tables.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) New enums
    retest_status = postgresql.ENUM(
        "scheduled", "in_progress", "completed", "cancelled",
        name="retest_status",
    )
    retest_status.create(op.get_bind(), checkfirst=True)
    webhook_status = postgresql.ENUM(
        "pending", "succeeded", "failed", "given_up",
        name="webhook_delivery_status",
    )
    webhook_status.create(op.get_bind(), checkfirst=True)
    notif_kind = postgresql.ENUM(
        "mention", "finding.regressed", "finding.resolved",
        "report.pending_review", "report.approved", "report.published",
        "agent.run_completed", "webhook.failed", "ingestion.failed", "retest.due",
        name="notification_kind",
    )
    notif_kind.create(op.get_bind(), checkfirst=True)

    # 2) New columns on existing tables
    op.add_column(
        "findings",
        sa.Column("risk_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column(
            "risk_components",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_find_risk", "findings", ["risk_score"])
    op.add_column(
        "findings",
        sa.Column("threat_intel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "finding_evidence",
        sa.Column("evidence_blob_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.drop_column("finding_evidence", "s3_key")
    op.drop_column("finding_evidence", "size")
    op.drop_column("finding_evidence", "mime")
    op.drop_column("finding_evidence", "sha256")

    # 3) New tables — order matters (FK targets first)
    op.create_table(
        "evidence_blobs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime", sa.String(120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column(
            "uploaded_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("ref_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_referenced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_eb_sha256", "evidence_blobs", ["sha256"], unique=True)

    op.create_table(
        "threat_intel_cache",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("cve_id", sa.String(40), nullable=False),
        sa.Column("cvss_v3_vector", sa.String(120)),
        sa.Column("cvss_v3_score", sa.Float()),
        sa.Column("cvss_v2_score", sa.Float()),
        sa.Column("nvd_published", sa.DateTime(timezone=True)),
        sa.Column("nvd_description", sa.String(2000)),
        sa.Column(
            "nvd_references", postgresql.JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column("epss_score", sa.Float()),
        sa.Column("epss_percentile", sa.Float()),
        sa.Column("epss_updated", sa.DateTime(timezone=True)),
        sa.Column("kev_listed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("kev_due_date", sa.DateTime(timezone=True)),
        sa.Column("kev_added_at", sa.DateTime(timezone=True)),
        sa.Column("kev_ransomware_use", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_refresh_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetch_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ti_workspace_cve", "threat_intel_cache", ["workspace_id", "cve_id"], unique=True)
    op.create_index("ix_ti_cve", "threat_intel_cache", ["cve_id"])

    op.create_table(
        "finding_comments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "finding_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "parent_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finding_comments.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column(
            "author_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "mentions", postgresql.ARRAY(sa.String),
            nullable=False, server_default="{}",
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fc_finding", "finding_comments", ["finding_id"])
    op.create_index("ix_fc_parent", "finding_comments", ["parent_id"])
    op.create_index("ix_fc_workspace", "finding_comments", ["workspace_id"])

    op.create_table(
        "comment_mentions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "comment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finding_comments.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_cm_user", "comment_mentions", ["user_id"])
    op.create_index("ix_cm_comment", "comment_mentions", ["comment_id"])

    op.create_table(
        "retest_cycles",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "engagement_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "retest_engagement_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("scheduled_for", sa.Date()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            postgresql.ENUM(name="retest_status", create_type=False),
            nullable=False, server_default="scheduled",
        ),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_rc_eng", "retest_cycles", ["engagement_id"])
    op.create_index("ix_rc_workspace", "retest_cycles", ["workspace_id"])

    op.create_table(
        "api_tokens",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False),
        sa.Column(
            "scopes", postgresql.ARRAY(sa.String),
            nullable=False, server_default="{}",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", sa.String(64)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_at_workspace", "api_tokens", ["workspace_id"])
    op.create_index("ix_at_hash", "api_tokens", ["token_hash"], unique=True)

    op.create_table(
        "webhook_endpoints",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column(
            "events", postgresql.ARRAY(sa.String),
            nullable=False, server_default="{}",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_we_workspace", "webhook_endpoints", ["workspace_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "endpoint_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(60)),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            postgresql.ENUM(name="webhook_delivery_status", create_type=False),
            nullable=False, server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", sa.Text()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_wd_endpoint", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_wd_event", "webhook_deliveries", ["event"])

    op.create_table(
        "portal_shares",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("max_views", sa.Integer()),
        sa.Column("current_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("require_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("password_hash", sa.String(255)),
        sa.Column(
            "allowed_emails", postgresql.ARRAY(sa.String),
            nullable=False, server_default="{}",
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(200)),
        sa.Column("watermark_with_viewer", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_access_at", sa.DateTime(timezone=True)),
        sa.Column("access_log", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ps_token", "portal_shares", ["token_hash"], unique=True)
    op.create_index("ix_ps_workspace", "portal_shares", ["workspace_id"])

    op.create_table(
        "agent_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "engagement_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("agent_session_id", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("tool_results", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text()),
        sa.Column("vulns_drafted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_rendered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ar_engagement", "agent_runs", ["engagement_id"])
    op.create_index("ix_ar_session", "agent_runs", ["agent_session_id"], unique=True)
    op.create_index("ix_ar_workspace", "agent_runs", ["workspace_id"])

    op.create_table(
        "agent_draft_diffs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "vulnerability_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("agent_session_id", sa.String(80), nullable=False),
        sa.Column(
            "engagement_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "reviewer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("original_impact", sa.Text()),
        sa.Column("final_impact", sa.Text()),
        sa.Column("original_recommendation", sa.Text()),
        sa.Column("final_recommendation", sa.Text()),
        sa.Column("impact_similarity", sa.Float()),
        sa.Column("recommendation_similarity", sa.Float()),
        sa.Column("edit_seconds", sa.Integer()),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_add_vuln", "agent_draft_diffs", ["vulnerability_id"])
    op.create_index("ix_add_workspace", "agent_draft_diffs", ["workspace_id"])

    op.create_table(
        "ldap_configs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("server_url", sa.String(500), nullable=False),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("bind_dn", sa.String(500), nullable=False),
        sa.Column("bind_password_ciphertext", sa.Text(), nullable=False),
        sa.Column("user_search_base", sa.String(500), nullable=False),
        sa.Column("user_search_filter", sa.String(500), nullable=False, server_default="(uid={username})"),
        sa.Column("group_search_base", sa.String(500)),
        sa.Column("group_member_attr", sa.String(60), nullable=False, server_default="member"),
        sa.Column("attribute_map", postgresql.JSONB(), nullable=False, server_default='{"email":"mail","full_name":"cn","username":"uid"}'),
        sa.Column("default_role", sa.String(40), nullable=False, server_default="viewer"),
        sa.Column("group_role_map", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(40)),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_lc_workspace", "ldap_configs", ["workspace_id"], unique=True)

    op.create_table(
        "ldap_user_mappings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("ldap_dn", sa.String(500), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_in_ldap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_lum_user", "ldap_user_mappings", ["user_id"], unique=True)
    op.create_index("ix_lum_dn", "ldap_user_mappings", ["ldap_dn"], unique=True)

    op.create_table(
        "notifications",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "kind", postgresql.ENUM(name="notification_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(60)),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("email_sent_at", sa.DateTime(timezone=True)),
        sa.Column("email_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_n_user_read", "notifications", ["user_id", "read_at"])
    op.create_index("ix_n_workspace", "notifications", ["workspace_id"])

    op.create_table(
        "notification_preferences",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_digest", sa.String(20), nullable=False, server_default="instant"),
        sa.Column("muted_kinds", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_np_user", "notification_preferences", ["user_id"], unique=True)

    # Deferred FKs (the target tables are created later in this migration)
    op.create_foreign_key(
        "fk_findings_threat_intel",
        "findings", "threat_intel_cache",
        ["threat_intel_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_finding_evidence_blob",
        "finding_evidence", "evidence_blobs",
        ["evidence_blob_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_finding_evidence_blob", "finding_evidence", type_="foreignkey")
    op.drop_constraint("fk_findings_threat_intel", "findings", type_="foreignkey")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notification_kind")
    op.drop_table("ldap_user_mappings")
    op.drop_table("ldap_configs")
    op.drop_table("agent_draft_diffs")
    op.drop_table("agent_runs")
    op.drop_table("portal_shares")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
    op.execute("DROP TYPE IF EXISTS webhook_delivery_status")
    op.drop_table("api_tokens")
    op.drop_table("retest_cycles")
    op.execute("DROP TYPE IF EXISTS retest_status")
    op.drop_table("comment_mentions")
    op.drop_table("finding_comments")
    op.drop_table("threat_intel_cache")
    op.add_column("finding_evidence", sa.Column("mime", sa.String(100), nullable=False, server_default=""))
    op.add_column("finding_evidence", sa.Column("size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("finding_evidence", sa.Column("sha256", sa.String(64), nullable=False, server_default=""))
    op.add_column("finding_evidence", sa.Column("s3_key", sa.String(500), nullable=False, server_default=""))
    op.drop_column("finding_evidence", "evidence_blob_id")
    op.drop_column("findings", "threat_intel_id")
    op.drop_index("ix_find_risk", "findings")
    op.drop_column("findings", "risk_components")
    op.drop_column("findings", "risk_score")
    op.drop_table("evidence_blobs")
