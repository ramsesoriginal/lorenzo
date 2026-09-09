"""create campaign and player tables

Revision ID: 0e2ac3f5758d
Revises: 8d9ec377f48a
Create Date: 2026-09-09 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0e2ac3f5758d"
down_revision: str | None = "8d9ec377f48a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = ("campaign", "player")


def _enable_rls(table: str) -> None:
    # Standard tenant_isolation shape - no self-access carve-out like
    # membership's (ADR 0023), nothing here needs a cross-tenant read.
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "campaign",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("game_system", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_campaign_tenant_id"), "campaign", ["tenant_id"], unique=False)

    op.create_table(
        "player",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        # Denormalized copy of campaign.tenant_id, not irreducible - see
        # ADR 0024 for why this one doesn't need to lead a composite PK
        # the way membership.tenant_id does.
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("campaign_id", "user_id"),
    )
    op.create_index(op.f("ix_player_tenant_id"), "player", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_player_user_id"), "player", ["user_id"], unique=False)

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_player_user_id"), table_name="player")
    op.drop_index(op.f("ix_player_tenant_id"), table_name="player")
    op.drop_table("player")
    op.drop_index(op.f("ix_campaign_tenant_id"), table_name="campaign")
    op.drop_table("campaign")
