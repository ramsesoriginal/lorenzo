"""create campaign_gm and orga_campaign_opt_out tables

Revision ID: f1fe7e3cc925
Revises: 91d78aeb6caf
Create Date: 2026-09-09 02:47:22.894757

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1fe7e3cc925"
down_revision: str | None = "91d78aeb6caf"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLES = ("campaign_gm", "orga_campaign_opt_out")


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    for table in _TABLES:
        op.create_table(
            table,
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("campaign_id", sa.UUID(), nullable=False),
            sa.PrimaryKeyConstraint("tenant_id", "user_id", "campaign_id"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        )
        _enable_rls(table)


def downgrade() -> None:
    op.drop_table("orga_campaign_opt_out")
    op.drop_table("campaign_gm")
