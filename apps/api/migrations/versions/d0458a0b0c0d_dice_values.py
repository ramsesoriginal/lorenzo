"""dice: a value type held as parts (RFC 0056 D1, ADR 0462)

`stat_value_type` gains `dice`; `entity_stat` gains `dice_count`, `dice_sides`, `dice_drop_mode` and
`dice_drop_count`, a fifth alternative of "exactly one value is set", with a check on the parts;
`v_effective_stat` carries the four columns, appended last so CREATE OR REPLACE VIEW accepts them
and the views built on it are untouched. The rule that picks the winner is not changed.

Revision ID: d0458a0b0c0d
Revises: d0457a0b0c0d
Create Date: 2026-11-13 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0458a0b0c0d"
down_revision: str | None = "d0457a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 5fade6f98352 (ADR 0037, 0039).
_MAX_PROTOTYPE_DEPTH = 50

_DICE_PARTS = (
    "(dice_count IS NULL) = (dice_sides IS NULL) "
    "AND (dice_drop_mode IS NULL) = (dice_drop_count IS NULL) "
    "AND (dice_count IS NOT NULL OR dice_drop_mode IS NULL) "
    "AND (dice_count IS NULL OR (dice_count BETWEEN 1 AND 100 "
    "AND dice_sides BETWEEN 2 AND 1000)) "
    "AND (dice_drop_mode IS NULL OR (dice_drop_mode IN ('lowest', 'highest') "
    "AND dice_drop_count BETWEEN 1 AND dice_count - 1))"
)


def _view_sql(*, dice: bool) -> str:
    """7e9e042cfdbb's definition (ADR 0285), with the dice columns last, or - for downgrade - the
    same columns as nulls, since a view cannot lose a column while other views are built on it."""
    if dice:
        stored = "es.dice_count, es.dice_sides, es.dice_drop_mode, es.dice_drop_count,"
        computed = "NULL::integer, NULL::integer, NULL::text, NULL::integer,"
        names = "c.dice_count, c.dice_sides, c.dice_drop_mode, c.dice_drop_count,"
        outer = (
            "s.dice_count AS dice_count, s.dice_sides AS dice_sides,"
            " s.dice_drop_mode AS dice_drop_mode, s.dice_drop_count AS dice_drop_count"
        )
    else:
        stored = computed = names = ""
        outer = (
            "NULL::integer AS dice_count, NULL::integer AS dice_sides,"
            " NULL::text AS dice_drop_mode, NULL::integer AS dice_drop_count"
        )
    return f"""
    CREATE OR REPLACE VIEW v_effective_stat WITH (security_invoker = true) AS
    SELECT
        e.id AS entity_id,
        e.tenant_id AS tenant_id,
        s.stat_definition_id AS stat_definition_id,
        s.value_int AS value_int,
        s.value_text AS value_text,
        s.value_float AS value_float,
        s.value_bool AS value_bool,
        s.computed_entity_id AS computed_entity_id,
        s.source_entity_id AS source_entity_id,
        {outer}
    FROM entity e
    CROSS JOIN LATERAL (
        WITH RECURSIVE stat_ancestor(ancestor_id, hops, path) AS (
            SELECT e.id, 0, ARRAY[]::integer[]
            UNION ALL
            SELECT ep.prototype_id, sa.hops + 1, sa.path || ep.position
            FROM stat_ancestor sa
            JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
            WHERE sa.hops < {_MAX_PROTOTYPE_DEPTH}
        )
        SELECT DISTINCT ON (c.stat_definition_id)
            c.stat_definition_id,
            c.value_int,
            c.value_text,
            c.value_float,
            c.value_bool,
            CASE WHEN c.is_computed THEN c.holder_id END AS computed_entity_id,
            c.holder_id AS source_entity_id
            {"," + names.rstrip(",") if dice else ""}
        FROM stat_ancestor sa
        CROSS JOIN LATERAL (
            SELECT es.entity_id AS holder_id, es.stat_definition_id,
                es.value_int, es.value_text, es.value_float, es.value_bool,
                {stored}
                false AS is_computed
            FROM entity_stat es
            WHERE es.entity_id = sa.ancestor_id
            UNION ALL
            SELECT cs.entity_id, cs.stat_definition_id,
                NULL::integer, NULL::text, NULL::double precision, NULL::boolean,
                {computed}
                true
            FROM computed_stat cs
            WHERE cs.entity_id = sa.ancestor_id
        ) c
        LEFT JOIN LATERAL (
            SELECT MAX(sg.priority) AS priority
            FROM entity_stat_group esg
            JOIN stat_group sg ON sg.id = esg.stat_group_id
            WHERE esg.entity_id = sa.ancestor_id
        ) ap ON true
        ORDER BY
            c.stat_definition_id,
            sa.hops ASC,
            c.is_computed ASC,
            COALESCE(ap.priority, 0) DESC,
            sa.path ASC,
            sa.ancestor_id
    ) s
    """


def upgrade() -> None:
    op.execute("ALTER TYPE stat_value_type ADD VALUE IF NOT EXISTS 'dice'")
    op.add_column("entity_stat", sa.Column("dice_count", sa.Integer(), nullable=True))
    op.add_column("entity_stat", sa.Column("dice_sides", sa.Integer(), nullable=True))
    op.add_column("entity_stat", sa.Column("dice_drop_mode", sa.Text(), nullable=True))
    op.add_column("entity_stat", sa.Column("dice_drop_count", sa.Integer(), nullable=True))
    op.drop_constraint("entity_stat_exactly_one_value", "entity_stat")
    op.create_check_constraint(
        "entity_stat_exactly_one_value",
        "entity_stat",
        "num_nonnulls(value_int, value_text, value_float, value_bool, dice_count) = 1",
    )
    op.create_check_constraint("entity_stat_dice_parts", "entity_stat", _DICE_PARTS)
    op.execute(_view_sql(dice=True))


def downgrade() -> None:
    op.execute(_view_sql(dice=False))
    op.drop_constraint("entity_stat_dice_parts", "entity_stat")
    op.drop_constraint("entity_stat_exactly_one_value", "entity_stat")
    # A dice value has no other column to go to, and Postgres cannot drop one enum member: the
    # rows go, and the type stays with a value nothing uses.
    op.execute("DELETE FROM entity_stat WHERE dice_count IS NOT NULL")
    op.create_check_constraint(
        "entity_stat_exactly_one_value",
        "entity_stat",
        "num_nonnulls(value_int, value_text, value_float, value_bool) = 1",
    )
    for column in ("dice_drop_count", "dice_drop_mode", "dice_sides", "dice_count"):
        op.drop_column("entity_stat", column)
