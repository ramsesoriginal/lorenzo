"""campaign_gm and tenant_admin_campaign_opt_out attribution

Revision ID: 9aa665f00305
Revises: fae51f1f72bc
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9aa665f00305"
down_revision: str | None = "fae51f1f72bc"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# ADR 0029's phased table names both of these next; ADR 0034/RFC 0006 is the
# campaign-CRUD slice that actually grants/revokes them via PUT/DELETE.
# created_by only, no updated_by - a grant or opt-out row is only ever made
# or revoked, never edited in place, so there's nothing for updated_by to
# mean (ADR 0029's own reasoning). Neither table had created_at either;
# this adds a bare created_at alongside created_by - just enough to answer
# "who did this, and when" - not the full four-column set every other table
# gets.
_TABLES = ("campaign_gm", "tenant_admin_campaign_opt_out")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.add_column(table, sa.Column("created_by", sa.Uuid(), nullable=True))
        op.create_index(op.f(f"ix_{table}_created_by"), table, ["created_by"], unique=False)
        op.create_foreign_key(
            f"{table}_created_by_fkey",
            table,
            "app_user",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"{table}_created_by_fkey", table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_created_by"), table_name=table)
        op.drop_column(table, "created_by")
        op.drop_column(table, "created_at")
