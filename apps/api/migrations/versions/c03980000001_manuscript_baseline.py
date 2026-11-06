"""Copied manuscript comparison baseline (ADR 0398)."""

from alembic import op

revision = "c03980000001"
down_revision = "c03830000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE repository_copy_link_entity ADD COLUMN manuscript_baseline jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE repository_copy_link_entity DROP COLUMN manuscript_baseline")
