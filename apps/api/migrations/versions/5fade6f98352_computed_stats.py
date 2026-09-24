"""computed stats: computed_stat + linear/comparison kinds, v_effective_stat

Revision ID: 5fade6f98352
Revises: 80c7d253d53e
Create Date: 2026-09-24 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5fade6f98352"
down_revision: str | None = "80c7d253d53e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 4768ec40991a (ADR 0039).
_MAX_PROTOTYPE_DEPTH = 50

_TABLES = ("computed_stat_linear", "computed_stat_comparison", "computed_stat")

# ADR 0104: a computed_stat row competes for the win at its hop exactly like
# an entity_stat row. Same-hop ties go to the direct value (is_computed
# sorts before priority), then ADR 0037's priority/ancestor_id rule. A
# winning formula comes out with every value_* column null and
# computed_entity_id naming the ancestor that holds it; the API evaluates it
# in Python (stat_evaluation.py). Existing columns keep their names, types
# and meaning for stored winners, and the new one is appended last, so
# CREATE OR REPLACE works without touching v_item/v_item_instance.
_V_EFFECTIVE_STAT_SQL = f"""
    CREATE OR REPLACE VIEW v_effective_stat WITH (security_invoker = true) AS
    WITH RECURSIVE
        stat_ancestor(root_entity_id, ancestor_id, hops) AS (
            SELECT e.id, e.id, 0
            FROM entity e
            UNION ALL
            SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1
            FROM stat_ancestor sa
            JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
            WHERE sa.hops < {_MAX_PROTOTYPE_DEPTH}
        ),
        ancestor_priority AS (
            SELECT esg.entity_id, MAX(sg.priority) AS priority
            FROM entity_stat_group esg
            JOIN stat_group sg ON sg.id = esg.stat_group_id
            GROUP BY esg.entity_id
        ),
        candidate AS (
            SELECT es.entity_id AS holder_id, es.stat_definition_id,
                es.value_int, es.value_text, es.value_float, es.value_bool,
                false AS is_computed
            FROM entity_stat es
            UNION ALL
            SELECT cs.entity_id, cs.stat_definition_id,
                NULL::integer, NULL::text, NULL::double precision, NULL::boolean,
                true
            FROM computed_stat cs
        )
    SELECT DISTINCT ON (sa.root_entity_id, c.stat_definition_id)
        sa.root_entity_id AS entity_id,
        e.tenant_id AS tenant_id,
        c.stat_definition_id AS stat_definition_id,
        c.value_int AS value_int,
        c.value_text AS value_text,
        c.value_float AS value_float,
        c.value_bool AS value_bool,
        CASE WHEN c.is_computed THEN c.holder_id END AS computed_entity_id
    FROM stat_ancestor sa
    JOIN entity e ON e.id = sa.root_entity_id
    JOIN candidate c ON c.holder_id = sa.ancestor_id
    LEFT JOIN ancestor_priority ap ON ap.entity_id = sa.ancestor_id
    ORDER BY
        sa.root_entity_id,
        c.stat_definition_id,
        sa.hops ASC,
        c.is_computed ASC,
        COALESCE(ap.priority, 0) DESC,
        sa.ancestor_id
    """

# As 4768ec40991a left it - for downgrade.
_PREVIOUS_V_EFFECTIVE_STAT_SQL = f"""
    CREATE VIEW v_effective_stat WITH (security_invoker = true) AS
    WITH RECURSIVE
        stat_ancestor(root_entity_id, ancestor_id, hops) AS (
            SELECT e.id, e.id, 0
            FROM entity e
            UNION ALL
            SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1
            FROM stat_ancestor sa
            JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
            WHERE sa.hops < {_MAX_PROTOTYPE_DEPTH}
        ),
        ancestor_priority AS (
            SELECT esg.entity_id, MAX(sg.priority) AS priority
            FROM entity_stat_group esg
            JOIN stat_group sg ON sg.id = esg.stat_group_id
            GROUP BY esg.entity_id
        )
    SELECT DISTINCT ON (sa.root_entity_id, es.stat_definition_id)
        sa.root_entity_id AS entity_id,
        e.tenant_id AS tenant_id,
        es.stat_definition_id AS stat_definition_id,
        es.value_int AS value_int,
        es.value_text AS value_text,
        es.value_float AS value_float,
        es.value_bool AS value_bool
    FROM stat_ancestor sa
    JOIN entity e ON e.id = sa.root_entity_id
    JOIN entity_stat es ON es.entity_id = sa.ancestor_id
    LEFT JOIN ancestor_priority ap ON ap.entity_id = sa.ancestor_id
    ORDER BY
        sa.root_entity_id,
        es.stat_definition_id,
        sa.hops ASC,
        COALESCE(ap.priority, 0) DESC,
        sa.ancestor_id
    """


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _kind_key() -> list[sa.Column | sa.Constraint]:
    """The (entity_id, stat_definition_id) key a concrete kind shares with
    its computed_stat row, cascading from it - payload's own shape (ADR
    0017)."""
    return [
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id"],
            ["computed_stat.entity_id", "computed_stat.stat_definition_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    ]


def upgrade() -> None:
    op.create_table(
        "computed_stat",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stat_definition_id"], ["stat_definition.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    # Source-stat FKs don't cascade (NO ACTION): a stat a formula reads
    # can't disappear from under it. NO ACTION rather than RESTRICT, so a
    # tenant delete that removes both in one statement still works.
    op.create_table(
        "computed_stat_linear",
        *_kind_key(),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("multiplier", sa.Numeric(), nullable=False),
        sa.Column("offset", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("round_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.ForeignKeyConstraint(["source_stat_definition_id"], ["stat_definition.id"]),
        sa.CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_linear_round_mode",
        ),
    )
    op.create_table(
        "computed_stat_comparison",
        *_kind_key(),
        sa.Column("left_stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("comparator", sa.Text(), nullable=False),
        sa.Column("right_stat_definition_id", sa.UUID(), nullable=True),
        sa.Column("right_constant", sa.Numeric(), nullable=True),
        sa.Column("true_value", sa.Text(), nullable=True),
        sa.Column("false_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["left_stat_definition_id"], ["stat_definition.id"]),
        sa.ForeignKeyConstraint(["right_stat_definition_id"], ["stat_definition.id"]),
        sa.CheckConstraint(
            "comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')",
            name="computed_stat_comparison_comparator",
        ),
        sa.CheckConstraint(
            "num_nonnulls(right_stat_definition_id, right_constant) = 1",
            name="computed_stat_comparison_one_right_side",
        ),
    )
    for table in _TABLES:
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(
        "ix_computed_stat_linear_source", "computed_stat_linear", ["source_stat_definition_id"]
    )
    op.create_index(
        "ix_computed_stat_comparison_left", "computed_stat_comparison", ["left_stat_definition_id"]
    )
    op.create_index(
        "ix_computed_stat_comparison_right",
        "computed_stat_comparison",
        ["right_stat_definition_id"],
    )

    op.execute(_V_EFFECTIVE_STAT_SQL)


def downgrade() -> None:
    # CREATE OR REPLACE can't drop a column, so the view is rebuilt - and
    # v_item/v_item_instance with it, recreated from their own current
    # definitions so this doesn't need a copy of their SQL.
    bind = op.get_bind()
    dependents = {
        name: bind.execute(sa.text(f"SELECT pg_get_viewdef('{name}'::regclass)")).scalar_one()
        for name in ("v_item", "v_item_instance")
    }
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute("DROP VIEW v_effective_stat")
    op.execute(_PREVIOUS_V_EFFECTIVE_STAT_SQL)
    for name in ("v_item", "v_item_instance"):
        op.execute(f"CREATE VIEW {name} WITH (security_invoker = true) AS {dependents[name]}")
    for table in _TABLES:
        op.drop_table(table)
