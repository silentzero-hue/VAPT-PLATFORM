"""Fix missing `role` enum (was in models but never created in 0001).

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The Role enum was referenced in models/user.py from 0001 onwards
    # but the CREATE TYPE statement was never emitted. Re-add it here so
    # INSERTs into workspace_memberships.role / users.role work.
    role = postgresql.ENUM(
        "platform_admin",
        "admin",
        "senior_analyst",
        "analyst",
        "viewer",
        name="role",
        create_type=True,
    )
    role.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS role")
