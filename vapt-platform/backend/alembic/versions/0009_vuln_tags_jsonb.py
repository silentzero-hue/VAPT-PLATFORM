"""Fix vulnerabilities.tags to JSONB (was VARCHAR[] in 0001).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The 0001 migration created vulnerabilities.tags as postgresql.ARRAY
    # but the model declares it as JSONB. INSERTs fail with
    # "column tags is of type character varying[] but expression is of
    # type jsonb" until they're aligned. Convert the column.
    # 1. Drop the array default since it can't be cast to jsonb.
    op.execute("ALTER TABLE vulnerabilities ALTER COLUMN tags DROP DEFAULT")
    # 2. Convert the column type, coercing NULL → '[]'.
    op.execute(
        "ALTER TABLE vulnerabilities "
        "ALTER COLUMN tags TYPE JSONB USING "
        "CASE WHEN tags IS NULL THEN '[]'::jsonb "
        "ELSE to_jsonb(tags) END"
    )
    # 3. Restore the JSONB default so future inserts work.
    op.execute(
        "ALTER TABLE vulnerabilities "
        "ALTER COLUMN tags SET DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE vulnerabilities "
        "ALTER COLUMN tags TYPE VARCHAR[] USING "
        "ARRAY(SELECT jsonb_array_elements_text(tags))::varchar[]"
    )
