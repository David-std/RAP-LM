"""Vehicle types per street corridor (dataset v1.2, decision D-12).

Revision ID: 0006
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE corridor ADD COLUMN by_vehicle jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE corridor DROP COLUMN by_vehicle;")
