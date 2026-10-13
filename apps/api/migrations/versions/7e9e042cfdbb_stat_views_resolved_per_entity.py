"""v_effective_stat, v_item and v_item_instance resolve per entity, not per tenant

ADR 0285. v_effective_stat started its recursive walk from every entity in the tenant (`FROM
entity` as the anchor) and filtered afterwards: Postgres cannot push `entity_id = X` into a
recursive CTE, so reading one entity's stats cost as much as reading the whole library's. v_item
and v_item_instance joined it six times, once per stat they carry, so a read of one item cost six
walks of everything: 6-8 ms in a library of 13 entities, 190 ms in one of 3,000 and 1.8 s in one of
20,000.

The walk is now a lateral subquery anchored on the entity it belongs to, so a filter on the entity
is a filter on where the walk starts, and what a read costs follows the length of the entity's
prototype chain. v_item and v_item_instance take their six stats from one such walk per row.

The rule is not changed: the same rows, in the same columns, picked by the same order (ADR 0037,
0039, 0266, 0276); the new view, the old one and v_item/v_item_instance over each were compared on
generated libraries of up to 3,000 entities, multiple parents, groups and formulas included.
The columns, their types and their order are the same, so CREATE OR REPLACE VIEW accepts it and
nothing built on the views is touched.

Revision ID: 7e9e042cfdbb
Revises: a41c9d7e5b23
Create Date: 2026-10-13 21:40:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7e9e042cfdbb"
down_revision: str | None = "a41c9d7e5b23"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 5fade6f98352 (ADR 0037, 0039).
_MAX_PROTOTYPE_DEPTH = 50

# What v_item and v_item_instance carry of the effective stats (ADR 0019, 0129).
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")

# c8e2a5d19f47's definition (ADR 0266, 0276), for downgrade.
_OLD_V_EFFECTIVE_STAT_SQL = f"""
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

# The same winner per (entity, definition), picked by the same order, from a walk that starts at the
# entity it is for: `e.id` in the anchor is what lets a filter on `entity_id` reach it. Each
# ancestor's candidates and group priority are looked up by the ancestor, not aggregated over the
# tenant first.
_V_EFFECTIVE_STAT_SQL = f"""
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
        s.source_entity_id AS source_entity_id
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
        FROM stat_ancestor sa
        CROSS JOIN LATERAL (
            SELECT es.entity_id AS holder_id, es.stat_definition_id,
                es.value_int, es.value_text, es.value_float, es.value_bool,
                false AS is_computed
            FROM entity_stat es
            WHERE es.entity_id = sa.ancestor_id
            UNION ALL
            SELECT cs.entity_id, cs.stat_definition_id,
                NULL::integer, NULL::text, NULL::double precision, NULL::boolean,
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


def _old_stat_joins() -> str:
    """One join of v_effective_stat per stat, as the views had them."""
    return "\n".join(
        f"""
    LEFT JOIN (
        SELECT ves.entity_id, ves.value_int
        FROM v_effective_stat ves
        JOIN stat_definition sd ON sd.id = ves.stat_definition_id
        WHERE sd.name = '{name}'
    ) {name} ON {name}.entity_id = e.id"""
        for name in _INT_STATS
    )


# One walk per row for all of them: the stat each name resolves to, pivoted.
_NEW_STAT_JOIN = (
    """
    LEFT JOIN LATERAL (
        SELECT
"""
    + ",\n".join(
        f"            MAX(ves.value_int) FILTER (WHERE sd.name = '{name}') AS {name}"
        for name in _INT_STATS
    )
    + """
        FROM v_effective_stat ves
        JOIN stat_definition sd ON sd.id = ves.stat_definition_id
        WHERE ves.entity_id = e.id
          AND sd.name IN ("""
    + ", ".join(f"'{name}'" for name in _INT_STATS)
    + """)
    ) stats ON true"""
)

_STAT_COLUMNS_OLD = ",\n    ".join(f"{name}.value_int AS {name}" for name in _INT_STATS)
_STAT_COLUMNS_NEW = ",\n    ".join(f"stats.{name} AS {name}" for name in _INT_STATS)


def _v_item_sql(stat_columns: str, stat_joins: str) -> str:
    return f"""
    CREATE OR REPLACE VIEW v_item WITH (security_invoker = true) AS
    SELECT
        e.id AS entity_id,
        e.tenant_id AS tenant_id,
        description_info.id AS description_id,
        description_info.title AS title,
        {stat_columns},
        containment.parent_entity_id AS container_entity_id,
        containment.quantity AS quantity
    FROM entity e
    JOIN item st ON st.entity_id = e.id
    LEFT JOIN information description_info
        ON description_info.entity_id = e.id AND description_info.type = 'description'
    LEFT JOIN containment ON containment.child_entity_id = e.id{stat_joins}
    """


def _v_item_instance_sql(stat_columns: str, stat_joins: str) -> str:
    return f"""
    CREATE OR REPLACE VIEW v_item_instance WITH (security_invoker = true) AS
    SELECT
        e.id AS entity_id,
        e.tenant_id AS tenant_id,
        ownership.owner_character_id AS owner_entity_id,
        entity_slug.slug AS slug,
        description_info.id AS description_id,
        description_info.title AS title,
        {stat_columns},
        containment.parent_entity_id AS container_entity_id,
        containment.quantity AS quantity
    FROM entity e
    JOIN item_instance st ON st.entity_id = e.id
    LEFT JOIN information description_info
        ON description_info.entity_id = e.id AND description_info.type = 'description'
    LEFT JOIN containment ON containment.child_entity_id = e.id
    LEFT JOIN ownership ON ownership.owned_entity_id = e.id
    LEFT JOIN entity_slug ON entity_slug.entity_id = e.id{stat_joins}
    """


def upgrade() -> None:
    op.execute(_V_EFFECTIVE_STAT_SQL)
    op.execute(_v_item_sql(_STAT_COLUMNS_NEW, _NEW_STAT_JOIN))
    op.execute(_v_item_instance_sql(_STAT_COLUMNS_NEW, _NEW_STAT_JOIN))


def downgrade() -> None:
    op.execute(_OLD_V_EFFECTIVE_STAT_SQL)
    op.execute(_v_item_sql(_STAT_COLUMNS_OLD, _old_stat_joins()))
    op.execute(_v_item_instance_sql(_STAT_COLUMNS_OLD, _old_stat_joins()))
