"""add missing index on player campaign_id

Revision ID: 6b57c96d3505
Revises: afa33fd441a2
Create Date: 2026-09-09 23:31:58.901112

"""

from collections.abc import Sequence

from alembic import op

revision: str = "6b57c96d3505"
down_revision: str | None = "afa33fd441a2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # player.py has always declared campaign_id: ... index=True, but
    # 0e2ac3f5758d_create_campaign_and_player_tables.py never actually
    # created it - only tenant_id and user_id got their own index there.
    # UniqueConstraint("campaign_id", "user_id") on that same migration
    # incidentally backs campaign_id with a composite unique index, but
    # that's a different index (different name, different shape) from
    # the plain single-column one the model's own metadata expects -
    # confirmed via `alembic check` flagging exactly this gap.
    op.create_index(op.f("ix_player_campaign_id"), "player", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_player_campaign_id"), table_name="player")
