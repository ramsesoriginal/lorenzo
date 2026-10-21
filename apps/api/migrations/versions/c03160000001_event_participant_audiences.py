"""Live Event participant audiences on existing tenant tables (ADR 0316)."""

import sqlalchemy as sa
from alembic import op

revision = "c03160000001"
down_revision = "c03150000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("information", "entity_audience"):
        op.add_column(
            table,
            sa.Column(
                "shared_with_participants", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )


def downgrade() -> None:
    for table in ("information", "entity_audience"):
        op.drop_column(table, "shared_with_participants")
