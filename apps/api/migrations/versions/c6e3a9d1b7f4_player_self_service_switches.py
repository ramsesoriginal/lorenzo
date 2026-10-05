"""player self-service switches

Revision ID: c6e3a9d1b7f4
Revises: b5d2c8f1a4e7
Create Date: 2026-10-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6e3a9d1b7f4"
down_revision: str | None = "b5d2c8f1a4e7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ADR 0185 - the campaign's general setting, on for every existing
    # campaign (what the API did before), and a player's override of it, NULL
    # (no override) for every existing player. No new table: RLS and the
    # same-tenant keys are the two tables' own.
    op.add_column(
        "campaign",
        sa.Column("player_self_service", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("player", sa.Column("self_service", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("player", "self_service")
    op.drop_column("campaign", "player_self_service")
