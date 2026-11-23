# ruff: noqa: E501  (SQL DDL reads best on one line)
"""Severity and exposure components and historical breakdown per result (D-10).

Nullable columns: runs published before D-10 keep null values (shown as
"not available" by the API, never as zero).

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE risk_result
            ADD COLUMN severity_value double precision CHECK (severity_value IS NULL OR severity_value >= 0),
            ADD COLUMN severity_index double precision CHECK (severity_index IS NULL OR severity_index BETWEEN 0 AND 100),
            ADD COLUMN exposure_ratio double precision CHECK (exposure_ratio IS NULL OR exposure_ratio >= 0),
            ADD COLUMN exposure_index double precision CHECK (exposure_index IS NULL OR exposure_index BETWEEN 0 AND 100),
            ADD COLUMN breakdown jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE risk_result DROP COLUMN severity_value, DROP COLUMN severity_index,
            DROP COLUMN exposure_ratio, DROP COLUMN exposure_index, DROP COLUMN breakdown;
        """
    )
