"""Urban-environment profile per explained unit (decision D-12).

Revision ID: 0007
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE unit_explanation ADD COLUMN context_profile jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE unit_explanation DROP COLUMN context_profile;")
