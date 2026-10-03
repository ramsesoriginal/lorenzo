"""tenant.npcs_shared_with_gms

Revision ID: d4e8a1b6c2f7
Revises: c3a9e1d5b7f2
Create Date: 2026-10-03 12:00:00.000000

ADR 0152: whether every GM of the tenant sees, and acts for, the beings in no
campaign. On by default, so no tenant's behaviour changes until an administrator
turns it off.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8a1b6c2f7"
down_revision: str | None = "c3a9e1d5b7f2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "npcs_shared_with_gms", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "npcs_shared_with_gms")
