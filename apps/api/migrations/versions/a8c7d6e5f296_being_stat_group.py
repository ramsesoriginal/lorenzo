"""The tenant's being stat group (ADR 0296).

Campaign parameters remain validated without overriding this tenant setting.
Existing RLS remains unchanged; the same-tenant key clears only the reference on deletion.

Revision ID: a8c7d6e5f296
Revises: c5b8d1f7a394
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c7d6e5f296"
down_revision: str | None = "c5b8d1f7a394"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("being_stat_group_id", sa.Uuid(), nullable=True))
    op.execute(
        "ALTER TABLE tenant ADD CONSTRAINT tenant_being_stat_group_id_fkey "
        "FOREIGN KEY (being_stat_group_id, id) REFERENCES stat_group (id, tenant_id) "
        "ON DELETE SET NULL (being_stat_group_id)"
    )


def downgrade() -> None:
    op.drop_constraint("tenant_being_stat_group_id_fkey", "tenant", type_="foreignkey")
    op.drop_column("tenant", "being_stat_group_id")
