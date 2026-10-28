"""A Map's theme name (ADR 0352)."""

from alembic import op

revision = "c03520000001"
down_revision = "c03360000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE map ADD COLUMN theme_hint text NULL, "
        "ADD CONSTRAINT map_theme_hint_length "
        "CHECK (theme_hint IS NULL OR char_length(theme_hint) BETWEEN 1 AND 32)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE map DROP COLUMN theme_hint")
