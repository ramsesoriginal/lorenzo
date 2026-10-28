"""What a Map only draws: its view (ADR 0354)."""

from alembic import op

revision = "c03540000001"
down_revision = "c03520000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE map ADD COLUMN view jsonb NULL, "
        "ADD CONSTRAINT map_view_object CHECK (view IS NULL OR jsonb_typeof(view) = 'object')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE map DROP COLUMN view")
