"""Gradient influence map per explained unit (D-09).

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE unit_explanation ADD COLUMN saliency jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE unit_explanation DROP COLUMN saliency;")
