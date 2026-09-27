"""computed_stat_sum and its terms: the sum formula kind (ADR 0126)

`round(Σ coefficient × stat + offset)` over stats of the same entity. The
kind row is keyed and cascades like computed_stat_linear; its terms cascade
from it. A term's source stat doesn't cascade (NO ACTION), like every other
formula input (ADR 0104). Every key between tenant tables is composite with
tenant_id (ADR 0117), and both tables are repository content (ADR 0118):
tenant_isolation, repository_read, and FORCE ROW LEVEL SECURITY.

Revision ID: 1e0ae40cab18
Revises: bad0e5f486eb
Create Date: 2026-09-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1e0ae40cab18"
down_revision: str | None = "bad0e5f486eb"
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
        "computed_stat_sum",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("offset", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("round_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_sum_entity_id_stat_definition_id_tenant_id_key",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat.entity_id",
                "computed_stat.stat_definition_id",
                "computed_stat.tenant_id",
            ],
            name="computed_stat_sum_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_sum_round_mode",
        ),
    )
    op.create_table(
        "computed_stat_sum_term",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("coefficient", sa.Numeric(), server_default=sa.text("1"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id", "source_stat_definition_id"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat_sum.entity_id",
                "computed_stat_sum.stat_definition_id",
                "computed_stat_sum.tenant_id",
            ],
            name="computed_stat_sum_term_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name="computed_stat_sum_term_source_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(
        "ix_computed_stat_sum_term_source_stat_definition_id",
        "computed_stat_sum_term",
        ["source_stat_definition_id"],
    )
    _protect("computed_stat_sum")
    _protect("computed_stat_sum_term")


def downgrade() -> None:
    op.drop_table("computed_stat_sum_term")
    op.drop_table("computed_stat_sum")
