"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # workspaces
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("description", sa.String(500)),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "default_sla_days",
            postgresql.JSONB,
            nullable=False,
            server_default='{"critical":7,"high":14,"medium":30,"low":60,"info":90}',
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # users
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_platform_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("backup_codes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspace_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(40), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "workspace_id", name="uq_membership"),
    )
    op.create_index("ix_membership_workspace", "workspace_memberships", ["workspace_id"])

    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("ip", postgresql.INET),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_session_user", "user_sessions", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_role", sa.String(40)),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(60)),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip", postgresql.INET),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("extra", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("detail", sa.Text),
        sa.Column("agent_session_id", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_workspace_ts", "audit_log", ["workspace_id", "created_at"])
    op.create_index("ix_audit_actor", "audit_log", ["actor_id"])
    op.create_index("ix_audit_action", "audit_log", ["action"])
    op.create_index("ix_audit_agent_session", "audit_log", ["agent_session_id"])

    op.create_table(
        "login_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("ip", postgresql.INET),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("reason", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_login_email_ts", "login_attempts", ["email", "created_at"])

    # engagements
    engagement_status = postgresql.ENUM(
        "planned", "active", "in_reporting", "delivered", "closed", "cancelled",
        name="engagement_status",
    )
    engagement_type = postgresql.ENUM(
        "webapp", "network", "wireless", "mobile", "cloud", "redteam", "social", "other",
        name="engagement_type",
    )
    engagement_status.create(op.get_bind(), checkfirst=True)
    engagement_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "engagements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "type",
            postgresql.ENUM(name="engagement_type", create_type=False),
            nullable=False,
            server_default="webapp",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="engagement_status", create_type=False),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("report_due_date", sa.Date),
        sa.Column("methodology", sa.String(40), nullable=False, server_default="OWASP-WSTG"),
        sa.Column("test_types", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("ingestion_locked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("ingestion_locked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_eng_workspace", "engagements", ["workspace_id"])
    op.create_index("ix_eng_status", "engagements", ["status"])

    op.create_table(
        "scope_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("pattern", sa.String(500), nullable=False),
        sa.Column("include", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scope_engagement", "scope_rules", ["engagement_id"])

    # assets
    asset_type = postgresql.ENUM(
        "host", "domain", "url", "app", "ip", "service", "repo", "person", "other",
        name="asset_type",
    )
    asset_criticality = postgresql.ENUM("low", "medium", "high", "critical", name="asset_criticality")
    asset_type.create(op.get_bind(), checkfirst=True)
    asset_criticality.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(name="asset_type", create_type=False),
            nullable=False,
        ),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("port", sa.Integer),
        sa.Column("protocol", sa.String(20)),
        sa.Column("fqdn", sa.String(500)),
        sa.Column("ip", postgresql.INET),
        sa.Column("environment", sa.String(40)),
        sa.Column(
            "criticality",
            postgresql.ENUM(name="asset_criticality", create_type=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("owner", sa.String(200)),
        sa.Column("business_unit", sa.String(200)),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("extra", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "workspace_id", "type", "value", "port", name="uq_asset_per_workspace"
        ),
    )
    op.create_index("ix_asset_workspace", "assets", ["workspace_id"])
    op.create_index("ix_asset_value", "assets", ["value"])
    op.create_index("ix_asset_fqdn", "assets", ["fqdn"])
    op.create_index("ix_asset_ip", "assets", ["ip"])

    # vulnerabilities
    severity = postgresql.ENUM("critical", "high", "medium", "low", "info", name="severity")
    confidence = postgresql.ENUM("confirmed", "firm", "tentative", name="confidence")
    cwe_category = postgresql.ENUM(
        "injection", "broken_auth", "crypto", "xss", "broken_access", "misconfig",
        "vulnerable_components", "ssrf", "insecure_deserialize", "logging_monitoring",
        "other", name="cwe_category",
    )
    severity.create(op.get_bind(), checkfirst=True)
    confidence.create(op.get_bind(), checkfirst=True)
    cwe_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "vulnerabilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("cve_id", sa.String(40)),
        sa.Column("cwe_id", sa.String(20)),
        sa.Column(
            "cwe_category",
            postgresql.ENUM(name="cwe_category", create_type=False),
            nullable=False,
            server_default="other",
        ),
        sa.Column("source_plugin", sa.String(120)),
        sa.Column("source_plugin_id", sa.String(80)),
        sa.Column("source_references", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column(
            "severity",
            postgresql.ENUM(name="severity", create_type=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("cvss_score", sa.Float),
        sa.Column("cvss_vector", sa.String(80)),
        sa.Column(
            "confidence",
            postgresql.ENUM(name="confidence", create_type=False),
            nullable=False,
            server_default="tentative",
        ),
        sa.Column("remediation_template", sa.Text),
        sa.Column("references", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("fingerprint_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384)),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_draft_impact", sa.Text),
        sa.Column("ai_draft_recommendation", sa.Text),
        sa.Column("ai_drafted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "ai_draft_reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("ai_draft_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("ai_draft_approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "fingerprint_hash", name="uq_vuln_fingerprint"),
    )
    op.create_index("ix_vuln_workspace", "vulnerabilities", ["workspace_id"])
    op.create_index("ix_vuln_severity", "vulnerabilities", ["severity"])
    op.create_index("ix_vuln_cve", "vulnerabilities", ["cve_id"])
    op.create_index("ix_vuln_fingerprint_hash", "vulnerabilities", ["fingerprint_hash"])

    op.create_table(
        "vulnerability_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "vulnerability_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
    )
    op.create_index("ix_vt_vuln", "vulnerability_tags", ["vulnerability_id"])

    # findings
    finding_status = postgresql.ENUM(
        "new", "confirmed", "in_remediation", "resolved",
        "remediated_pending_confirmation", "regressed",
        "false_positive", "accepted_risk", "deferred",
        name="finding_status",
    )
    finding_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vulnerability_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("port", sa.Integer),
        sa.Column("protocol", sa.String(20)),
        sa.Column("evidence_ref", sa.String(500)),
        sa.Column("request", sa.Text),
        sa.Column("response", sa.Text),
        sa.Column("raw_output", sa.Text),
        sa.Column("severity_override", sa.String(20)),
        sa.Column("cvss_score_override", sa.Float),
        sa.Column(
            "status",
            postgresql.ENUM(name="finding_status", create_type=False),
            nullable=False,
            server_default="new",
        ),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("sla_breached", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("resolution_note", sa.Text),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("extra", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "vulnerability_id", "asset_id", "engagement_id", "port",
            name="uq_finding_unique",
        ),
    )
    op.create_index("ix_find_workspace", "findings", ["workspace_id"])
    op.create_index("ix_find_engagement", "findings", ["engagement_id"])
    op.create_index("ix_find_vuln", "findings", ["vulnerability_id"])
    op.create_index("ix_find_status", "findings", ["status"])
    op.create_index("ix_find_severity", "findings", ["severity_override"])

    op.create_table(
        "finding_activity",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fact_finding", "finding_activity", ["finding_id"])

    op.create_table(
        "finding_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("filename", sa.String(400), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("note", sa.String(400)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fev_finding", "finding_evidence", ["finding_id"])

    # report templates + reports
    report_status = postgresql.ENUM(
        "drafting", "pending_review", "changes_requested",
        "approved", "published", "rejected",
        name="report_status",
    )
    report_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "report_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("template_path", sa.String(500), nullable=False),
        sa.Column("schema", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_rtpl_workspace", "report_templates", ["workspace_id"])

    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("report_templates.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="report_status", create_type=False),
            nullable=False,
            server_default="drafting",
        ),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("signed_sha256", sa.String(64)),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "signed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("locked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_rep_engagement", "reports", ["engagement_id"])
    op.create_index("ix_rep_status", "reports", ["status"])

    op.create_table(
        "report_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="report_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("agent_session_id", sa.String(80)),
        sa.Column("note", sa.Text),
        sa.Column("s3_key", sa.String(500)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("size", sa.Integer),
        sa.Column("mime", sa.String(100), nullable=False, server_default="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        sa.Column("draft_payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("report_id", "version_no", name="uq_rv_no"),
    )
    op.create_index("ix_rv_report", "report_versions", ["report_id"])

    # ingestion jobs
    ingestion_format = postgresql.ENUM(
        "nessus", "nmap", "burp", "zap", "nuclei", "json", "unknown",
        name="ingestion_format",
    )
    ingestion_status = postgresql.ENUM(
        "queued", "parsing", "deduping", "done", "failed", "partial",
        name="ingestion_status",
    )
    ingestion_format.create(op.get_bind(), checkfirst=True)
    ingestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_filename", sa.String(400)),
        sa.Column("source_s3_key", sa.String(500)),
        sa.Column(
            "format",
            postgresql.ENUM(name="ingestion_format", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="ingestion_status", create_type=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("raw_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parsed_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_vulns", sa.Integer, nullable=False, server_default="0"),
        sa.Column("merged_vulns", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("regressed_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("remediated_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("log", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ij_workspace", "ingestion_jobs", ["workspace_id"])
    op.create_index("ix_ij_status", "ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.execute("DROP TYPE IF EXISTS ingestion_status")
    op.execute("DROP TYPE IF EXISTS ingestion_format")

    op.drop_table("report_versions")
    op.drop_table("reports")
    op.execute("DROP TYPE IF EXISTS report_status")

    op.drop_table("report_templates")

    op.drop_table("finding_evidence")
    op.drop_table("finding_activity")
    op.drop_table("findings")
    op.execute("DROP TYPE IF EXISTS finding_status")

    op.drop_table("vulnerability_tags")
    op.drop_table("vulnerabilities")
    op.execute("DROP TYPE IF EXISTS cwe_category")
    op.execute("DROP TYPE IF EXISTS confidence")
    op.execute("DROP TYPE IF EXISTS severity")

    op.drop_table("assets")
    op.execute("DROP TYPE IF EXISTS asset_criticality")
    op.execute("DROP TYPE IF EXISTS asset_type")

    op.drop_table("scope_rules")
    op.drop_table("engagements")
    op.execute("DROP TYPE IF EXISTS engagement_type")
    op.execute("DROP TYPE IF EXISTS engagement_status")

    op.drop_table("login_attempts")
    op.drop_table("audit_log")
    op.drop_table("user_sessions")
    op.drop_table("workspace_memberships")
    op.drop_table("users")
    op.drop_table("workspaces")
