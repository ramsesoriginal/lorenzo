"""computed_stat_extremum and its inputs: the min and max formula kinds (ADR 0444)

`min` or `max` of two to five inputs, each a stat of the same entity or a constant. One row
per formula (`pick` says which kind), its inputs cascade from it. An input's stat doesn't
cascade (NO ACTION), like every other formula input (ADR 0104). Every key between tenant
tables is composite with tenant_id (ADR 0117), and both tables are repository content
(ADR 0118): tenant_isolation, repository_read, and FORCE ROW LEVEL SECURITY.

Revision ID: d0444a0b0c0d
Revises: d0439a0b0c0d
Create Date: 2026-11-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0444a0b0c0d"
down_revision: str | None = "d0439a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"


def _protect(table: str) -> None:
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {table} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def upgrade() -> None:
    op.create_table(
        "computed_stat_extremum",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("pick", sa.Text(), nullable=False),
        sa.Column("round_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_extremum_entity_stat_tenant_key",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat.entity_id",
                "computed_stat.stat_definition_id",
                "computed_stat.tenant_id",
            ],
            name="computed_stat_extremum_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint("pick IN ('min', 'max')", name="computed_stat_extremum_pick"),
        sa.CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_extremum_round_mode",
        ),
    )
    op.create_table(
        "computed_stat_extremum_input",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=True),
        sa.Column("constant", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id", "position"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat_extremum.entity_id",
                "computed_stat_extremum.stat_definition_id",
                "computed_stat_extremum.tenant_id",
            ],
            name="computed_stat_extremum_input_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_extremum_input_source_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(source_stat_definition_id, constant) = 1",
            name="computed_stat_extremum_input_one_operand",
        ),
    )
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(
        "ix_computed_stat_extremum_input_source_stat_definition_id",
        "computed_stat_extremum_input",
        ["source_stat_definition_id"],
    )
    _protect("computed_stat_extremum")
    _protect("computed_stat_extremum_input")


def downgrade() -> None:
    op.drop_table("computed_stat_extremum_input")
    op.drop_table("computed_stat_extremum")
