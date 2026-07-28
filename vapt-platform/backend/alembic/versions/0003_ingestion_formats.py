"""Expand ingestion_format enum to cover all supported scanner outputs.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'openvas'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'qualys'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'trivy'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'snyk'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'prowler'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'testssl'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'wpscan'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'nikto'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'metasploit'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'aws_inspector'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'kube_bench'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'sarif'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'cyclonedx'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'spdx'")
    op.execute("ALTER TYPE ingestion_format ADD VALUE IF NOT EXISTS 'legacy_db'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for an enum; would require full type rebuild.
    # We document this as a one-way expansion. The original six values remain.
    pass
