"""computed_stat_select and its steps: the select formula kind (ADR 0446)

A value from a table: a source stat of the same entity, a mode (`threshold` or `match`), steps each
with a key and a result, and the result when no step applies. A result is a constant or a stat of
the same entity. The kind row is keyed and cascades like computed_stat_linear; its steps cascade
from it. A source or result stat doesn't cascade (NO ACTION), like every other formula input
(ADR 0104). Every key between tenant tables is composite with tenant_id (ADR 0117), and both tables
are repository content (ADR 0118): tenant_isolation, repository_read, and FORCE ROW LEVEL SECURITY.

Revision ID: d0446a0b0c0d
Revises: d0445a0b0c0d
Create Date: 2026-11-11 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0446a0b0c0d"
down_revision: str | None = "d0445a0b0c0d"
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
        "computed_stat_select",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("otherwise_number", sa.Numeric(), nullable=True),
        sa.Column("otherwise_text", sa.Text(), nullable=True),
        sa.Column("otherwise_bool", sa.Boolean(), nullable=True),
        sa.Column("otherwise_stat_definition_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_select_entity_stat_tenant_key",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat.entity_id",
                "computed_stat.stat_definition_id",
                "computed_stat.tenant_id",
            ],
            name="computed_stat_select_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_select_source_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["otherwise_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_select_otherwise_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint("mode IN ('threshold', 'match')", name="computed_stat_select_mode"),
        sa.CheckConstraint(
            "num_nonnulls(otherwise_number, otherwise_text, otherwise_bool,"
            " otherwise_stat_definition_id) <= 1",
            name="computed_stat_select_one_otherwise",
        ),
    )
    op.create_table(
        "computed_stat_select_step",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("threshold", sa.Numeric(), nullable=True),
        sa.Column("match_value", sa.Text(), nullable=True),
        sa.Column("result_number", sa.Numeric(), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("result_bool", sa.Boolean(), nullable=True),
        sa.Column("result_stat_definition_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id", "position"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat_select.entity_id",
                "computed_stat_select.stat_definition_id",
                "computed_stat_select.tenant_id",
            ],
            name="computed_stat_select_step_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["result_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_select_step_result_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(threshold, match_value) = 1", name="computed_stat_select_step_one_key"
        ),
        sa.CheckConstraint(
            "num_nonnulls(result_number, result_text, result_bool, result_stat_definition_id) = 1",
            name="computed_stat_select_step_one_result",
        ),
    )
    # The reverse-dependency lookup (ADR 0104) reads by source and by result stat.
    op.create_index(
        "ix_computed_stat_select_source_stat_definition_id",
        "computed_stat_select",
        ["source_stat_definition_id"],
    )
    op.create_index(
        "ix_computed_stat_select_otherwise_stat_definition_id",
        "computed_stat_select",
        ["otherwise_stat_definition_id"],
    )
    op.create_index(
        "ix_computed_stat_select_step_result_stat_definition_id",
        "computed_stat_select_step",
        ["result_stat_definition_id"],
    )
    _protect("computed_stat_select")
    _protect("computed_stat_select_step")


def downgrade() -> None:
    op.drop_table("computed_stat_select_step")
    op.drop_table("computed_stat_select")
