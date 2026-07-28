"""Fix findings.evidence_ref length (was VARCHAR(500), should be Text).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # claude.md notes this is the "string too long" fix. Truncating
    # long plugin output silently loses data; widen to Text.
    op.alter_column(
        "findings",
        "evidence_ref",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "findings",
        "evidence_ref",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
