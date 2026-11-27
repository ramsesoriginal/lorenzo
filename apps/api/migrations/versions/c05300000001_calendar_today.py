"""A calendar's current date, a field the calendar keeps (ADR 0530)."""

from alembic import op

revision = "c05300000001"
down_revision = "c05240000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE calendar ADD COLUMN today jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE calendar DROP COLUMN today")
