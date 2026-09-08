"""create tenant table

Revision ID: 98586dc358a7
Revises:
Create Date: 2026-09-08 15:55:59.222372

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "98586dc358a7"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tenant")
