"""computed_stat_product (with its factors) and computed_stat_ratio: the product and ratio kinds (ADR 0445)

`product` is two to five stats multiplied, then times a constant plus an offset; `ratio` is a stat
divided by a stat or a constant, times a constant plus an offset. The kind row is keyed and cascades
like computed_stat_linear; a product's factors cascade from it. A formula input's stat doesn't
cascade (NO ACTION), like every other formula input (ADR 0104). Every key between tenant tables is
composite with tenant_id (ADR 0117), and all three tables are repository content (ADR 0118):
tenant_isolation, repository_read, and FORCE ROW LEVEL SECURITY.

Revision ID: d0445a0b0c0d
Revises: d0444a0b0c0d
Create Date: 2026-11-11 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0445a0b0c0d"
down_revision: str | None = "d0444a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
_ROUND_MODES = "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')"


def _protect(table: str) -> None:
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {table} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def _kind_key(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["entity_id", "stat_definition_id", "tenant_id"],
        [
            "computed_stat.entity_id",
            "computed_stat.stat_definition_id",
            "computed_stat.tenant_id",
        ],
        name=f"{table}_entity_id_stat_definition_id_fkey",
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "computed_stat_product",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("multiplier", sa.Numeric(), server_default=sa.text("1"), nullable=False),
        sa.Column("offset", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("round_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_product_entity_stat_tenant_key",
        ),
        _kind_key("computed_stat_product"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(_ROUND_MODES, name="computed_stat_product_round_mode"),
    )
    op.create_table(
        "computed_stat_product_factor",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id", "position"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat_product.entity_id",
                "computed_stat_product.stat_definition_id",
                "computed_stat_product.tenant_id",
            ],
            name="computed_stat_product_factor_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_product_factor_source_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(
        "ix_computed_stat_product_factor_source_stat_definition_id",
        "computed_stat_product_factor",
        ["source_stat_definition_id"],
    )
    op.create_table(
        "computed_stat_ratio",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("numerator_stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("denominator_stat_definition_id", sa.UUID(), nullable=True),
        sa.Column("denominator_constant", sa.Numeric(), nullable=True),
        sa.Column("multiplier", sa.Numeric(), server_default=sa.text("1"), nullable=False),
        sa.Column("offset", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("round_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        _kind_key("computed_stat_ratio"),
        sa.ForeignKeyConstraint(
            ["numerator_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_ratio_numerator_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["denominator_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_ratio_denominator_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(denominator_stat_definition_id, denominator_constant) = 1",
            name="computed_stat_ratio_one_denominator",
        ),
        sa.CheckConstraint(_ROUND_MODES, name="computed_stat_ratio_round_mode"),
    )
    op.create_index(
        "ix_computed_stat_ratio_numerator_stat_definition_id",
        "computed_stat_ratio",
        ["numerator_stat_definition_id"],
    )
    op.create_index(
        "ix_computed_stat_ratio_denominator_stat_definition_id",
        "computed_stat_ratio",
        ["denominator_stat_definition_id"],
    )
    _protect("computed_stat_product")
    _protect("computed_stat_product_factor")
    _protect("computed_stat_ratio")


def downgrade() -> None:
    op.drop_table("computed_stat_ratio")
    op.drop_table("computed_stat_product_factor")
    op.drop_table("computed_stat_product")
