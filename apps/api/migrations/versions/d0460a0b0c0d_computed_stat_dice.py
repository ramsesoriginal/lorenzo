"""computed_stat_dice: the `dice` kind (RFC 0056 D3, ADR 0464)

A dice value built from a count and a number of sides, each a stat of the same entry or a constant.
The kind row is keyed and cascades like computed_stat_linear; a formula input's stat does not
cascade (NO ACTION), like every other (ADR 0104). Every key between tenant tables is composite with
tenant_id (ADR 0117), and the table is repository content (ADR 0118): tenant_isolation,
repository_read and FORCE ROW LEVEL SECURITY.

Revision ID: d0460a0b0c0d
Revises: d0459a0b0c0d
Create Date: 2026-11-13 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0460a0b0c0d"
down_revision: str | None = "d0459a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
_TABLE = "computed_stat_dice"


def _stat_key(column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column, "tenant_id"],
        ["stat_definition.id", "stat_definition.tenant_id"],
        name=f"{_TABLE}_{column}_fkey",
    )


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("count_stat_definition_id", sa.UUID(), nullable=True),
        sa.Column("count_constant", sa.Integer(), nullable=True),
        sa.Column("sides_stat_definition_id", sa.UUID(), nullable=True),
        sa.Column("sides_constant", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat.entity_id",
                "computed_stat.stat_definition_id",
                "computed_stat.tenant_id",
            ],
            name=f"{_TABLE}_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        _stat_key("count_stat_definition_id"),
        _stat_key("sides_stat_definition_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(count_stat_definition_id, count_constant) = 1",
            name=f"{_TABLE}_one_count",
        ),
        sa.CheckConstraint(
            "num_nonnulls(sides_stat_definition_id, sides_constant) = 1",
            name=f"{_TABLE}_one_sides",
        ),
        sa.CheckConstraint(
            "(count_constant IS NULL OR count_constant BETWEEN 1 AND 100) "
            "AND (sides_constant IS NULL OR sides_constant BETWEEN 2 AND 1000)",
            name=f"{_TABLE}_constants",
        ),
    )
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(f"ix_{_TABLE}_count_stat_definition_id", _TABLE, ["count_stat_definition_id"])
    op.create_index(f"ix_{_TABLE}_sides_stat_definition_id", _TABLE, ["sides_stat_definition_id"])
    op.create_index(f"ix_{_TABLE}_tenant_id", _TABLE, ["tenant_id"])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {_TABLE} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {_TABLE} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
