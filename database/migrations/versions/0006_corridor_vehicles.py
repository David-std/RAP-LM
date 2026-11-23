"""Vehicle types and recorded contributing factors per street corridor (D-12).

Revision ID: 0006
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE corridor ADD COLUMN by_vehicle jsonb, ADD COLUMN by_factor jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE corridor DROP COLUMN by_vehicle, DROP COLUMN by_factor;")
