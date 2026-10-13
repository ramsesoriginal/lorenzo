"""v_effective_stat.source_entity_id: the entity holding the winning value or formula

ADR 0276. The view named the holder only when a formula won (computed_entity_id); a stored value
inherited from a prototype did not say where it came from. The column is appended last, so
CREATE OR REPLACE VIEW accepts it and the views built on this one are untouched. The rule that
picks the winner is not changed.

Revision ID: c8e2a5d19f47
Revises: b9d1e47a3c62
Create Date: 2026-10-12 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8e2a5d19f47"
down_revision: str | None = "b9d1e47a3c62"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 5fade6f98352 (ADR 0037, 0039).
_MAX_PROTOTYPE_DEPTH = 50

# d7a3f1b9c2e4's definition (ADR 0266), plus `source_entity_id` as the last column.
_V_EFFECTIVE_STAT_SQL = f"""
    CREATE OR REPLACE VIEW v_effective_stat WITH (security_invoker = true) AS
    WITH RECURSIVE
        stat_ancestor(root_entity_id, ancestor_id, hops, path) AS (
            SELECT e.id, e.id, 0, ARRAY[]::integer[]
            FROM entity e
            UNION ALL
            SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1, sa.path || ep.position
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
        CASE WHEN c.is_computed THEN c.holder_id END AS computed_entity_id,
        c.holder_id AS source_entity_id
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
        sa.path ASC,
        sa.ancestor_id
    """


def upgrade() -> None:
    op.execute(_V_EFFECTIVE_STAT_SQL)


def downgrade() -> None:
    # A view cannot lose a column while other views are built on it, and dropping them to put the
    # old definition back is more than an unused column is worth. The column stays; nothing reads
    # it once the code that did is gone.
    pass
