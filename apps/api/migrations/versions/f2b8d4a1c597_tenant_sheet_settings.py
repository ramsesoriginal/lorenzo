"""tenant: the stat group that holds a weapon's stats and the information type of an ability

ADR 0281. Two settings of a library for the being sheet's datasheet. The group is a composite,
same-tenant key (the tenant's own id is the tenant_id of the group), and deleting the group clears
only the setting (PostgreSQL 15+): a plain ON DELETE SET NULL would try to null tenant_id too.

Revision ID: f2b8d4a1c597
Revises: e9a3c6d2b814
Create Date: 2026-10-12 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b8d4a1c597"
down_revision: str | None = "e9a3c6d2b814"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("weapon_stat_group_id", sa.Uuid(), nullable=True))
    op.add_column("tenant", sa.Column("ability_information_type", sa.String(), nullable=True))
    op.execute(
        "ALTER TABLE tenant ADD CONSTRAINT tenant_weapon_stat_group_id_fkey "
        "FOREIGN KEY (weapon_stat_group_id, id) REFERENCES stat_group (id, tenant_id) "
        "ON DELETE SET NULL (weapon_stat_group_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tenant DROP CONSTRAINT tenant_weapon_stat_group_id_fkey")
    op.drop_column("tenant", "ability_information_type")
    op.drop_column("tenant", "weapon_stat_group_id")
