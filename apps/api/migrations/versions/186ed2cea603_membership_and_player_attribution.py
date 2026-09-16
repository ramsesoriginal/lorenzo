"""membership and player attribution

Revision ID: 186ed2cea603
Revises: d9746a3eaf87
Create Date: 2026-09-15 18:51:28.175518

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "186ed2cea603"
down_revision: str | None = "d9746a3eaf87"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# ADR 0029's phased table names both of these last: membership/player CRUD
# (ADR 0036/RFC 0007) is what actually writes to either table. Both get the
# full created_by/updated_by pair (nullable, ON DELETE SET NULL, indexed) -
# not campaign_gm/tenant_admin_campaign_opt_out's lighter created_by-only
# shape, matching entity/campaign/character/tenant's own precedent: a
# membership's role can genuinely be changed after creation (PATCH), and
# player gets both despite having no PATCH at all, for consistency with how
# player.updated_at already exists today for the identical
# never-actually-updated reason.
_TABLES = ("membership", "player")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("created_by", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("updated_by", sa.Uuid(), nullable=True))
        op.create_index(op.f(f"ix_{table}_created_by"), table, ["created_by"], unique=False)
        op.create_index(op.f(f"ix_{table}_updated_by"), table, ["updated_by"], unique=False)
        op.create_foreign_key(
            f"{table}_created_by_fkey",
            table,
            "app_user",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            f"{table}_updated_by_fkey",
            table,
            "app_user",
            ["updated_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"{table}_updated_by_fkey", table, type_="foreignkey")
        op.drop_constraint(f"{table}_created_by_fkey", table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_updated_by"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_created_by"), table_name=table)
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")
