"""stat definitions: an optional minimum and maximum

ADR 0403. A standing such as honor has a scale (minus ten to ten). Two nullable columns bound the
own values of an int or float definition; a write outside them is refused by the API, and a
computed value is not clamped.

Revision ID: c04030000001
Revises: c03990000001
Create Date: 2026-11-06 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c04030000001"
down_revision: str | None = "c03990000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stat_definition", sa.Column("min_value", sa.Float(), nullable=True))
    op.add_column("stat_definition", sa.Column("max_value", sa.Float(), nullable=True))
    op.create_check_constraint(
        "stat_definition_scale_order",
        "stat_definition",
        "min_value IS NULL OR max_value IS NULL OR min_value <= max_value",
    )
    op.create_check_constraint(
        "stat_definition_scale_numeric",
        "stat_definition",
        "(min_value IS NULL AND max_value IS NULL) OR value_type::text IN ('int', 'float')",
    )


def downgrade() -> None:
    op.drop_constraint("stat_definition_scale_numeric", "stat_definition")
    op.drop_constraint("stat_definition_scale_order", "stat_definition")
    op.drop_column("stat_definition", "max_value")
    op.drop_column("stat_definition", "min_value")
