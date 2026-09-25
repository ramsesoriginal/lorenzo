"""item.in_public_catalog: the public catalog (ADR 0116)

Revision ID: 93647604e820
Revises: d56420c00f9f
Create Date: 2026-09-25 08:13:00.100598

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "93647604e820"
down_revision: str | None = "d56420c00f9f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Every existing item stays out of the public catalog until a GM puts it there.
    op.add_column(
        "item",
        sa.Column("in_public_catalog", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("item", "in_public_catalog")
