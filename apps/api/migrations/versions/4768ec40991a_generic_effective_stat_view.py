"""generic v_effective_stat view, consumed by v_item/v_item_instance

Revision ID: 4768ec40991a
Revises: 186ed2cea603
Create Date: 2026-09-16 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "4768ec40991a"
down_revision: str | None = "186ed2cea603"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# entity_prototype's own BEFORE INSERT trigger (ADR 0015) already makes a
# cycle in this graph impossible, so this bound is a pure performance/
# pathological-depth safeguard, not a correctness necessity - unchanged
# from 6341fedbfc47 (ADR 0037), just relocated here.
_MAX_PROTOTYPE_DEPTH = 50

# name -> which value_* column - unchanged from 6c2f0a9d3e17 (ADR 0019).
# v_item/v_item_instance's own plain-column shape doesn't change in this
# migration at all; only where their per-name joins read resolved values
# from does (ADR 0039).
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_BOOL_STATS = ("is_magical", "is_cursed")

_V_EFFECTIVE_STAT_SQL = f"""
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
# ADR 0039: the sole difference from 6341fedbfc47's own stat_ancestor base
# case is `FROM entity e` here (every entity in the tenant) instead of
# `JOIN item st ON st.entity_id = e.id` / `JOIN item_instance st ...` -
# this is what makes the walk resolve stats for any entity (characters
# included, ADR 0031's VCharacter reuses EntityViewMixin too), not only
# item/item_instance-typed ones, and for every stat_definition, not only
# the 8 names v_item/v_item_instance happen to expose as columns. The
# three CTEs' own logic (hop-0 always wins, then hop distance, then the
# acquired-stat-group priority tie-break, then ancestor_id) is otherwise
# unchanged from ADR 0037 - relocated and generalized, not reconsidered.


def _resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT ves.entity_id, ves.{value_column}\n"
        f"    FROM v_effective_stat ves\n"
        f"    JOIN stat_definition sd ON sd.id = ves.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _create_view(
    name: str, source_table: str, *, extra_select: str = "", extra_join: str = ""
) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_resolved_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    # No WITH RECURSIVE here any more (ADR 0039) - v_effective_stat is now
    # the one place the prototype-stat walk exists. Each named join is
    # otherwise byte-for-byte the same shape 6341fedbfc47 already used,
    # just reading from v_effective_stat instead of an inline CTE.
    return f"""
        CREATE VIEW {name} WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id{extra_select},
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id
        FROM entity e
        JOIN {source_table} st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {extra_join}
        {joins}
        """


def upgrade() -> None:
    # Drop the two dependent views first (v_item_instance before v_item,
    # matching every prior migration's own order), then v_effective_stat
    # doesn't exist yet so there's nothing to drop for it - create it, then
    # recreate v_item/v_item_instance against it.
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute(_V_EFFECTIVE_STAT_SQL)
    op.execute(_create_view("v_item", "item"))
    # owner_entity_id: derived via a LEFT JOIN against `ownership`, not a
    # stored item_instance column - unchanged from 6341fedbfc47/91d78aeb6caf.
    op.execute(
        _create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )


# --- Pre-generalization view SQL, as 6341fedbfc47 (ADR 0037) left it -
# inlined here rather than imported from that migration, so this migration
# stays a self-contained snapshot downgrade can always replay even if a
# future change edits or removes that file's own helpers.
def _pre_generalization_resolved_stat_ctes(source_table: str) -> str:
    return f"""
        stat_ancestor(root_entity_id, ancestor_id, hops) AS (
            SELECT e.id, e.id, 0
            FROM entity e
            JOIN {source_table} st ON st.entity_id = e.id
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
        resolved_stat AS (
            SELECT DISTINCT ON (sa.root_entity_id, es.stat_definition_id)
                sa.root_entity_id AS entity_id,
                es.stat_definition_id,
                es.value_int,
                es.value_text,
                es.value_float,
                es.value_bool
            FROM stat_ancestor sa
            JOIN entity_stat es ON es.entity_id = sa.ancestor_id
            LEFT JOIN ancestor_priority ap ON ap.entity_id = sa.ancestor_id
            ORDER BY
                sa.root_entity_id,
                es.stat_definition_id,
                sa.hops ASC,
                COALESCE(ap.priority, 0) DESC,
                sa.ancestor_id
        )
    """


def _pre_generalization_resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT rs.entity_id, rs.{value_column}\n"
        f"    FROM resolved_stat rs\n"
        f"    JOIN stat_definition sd ON sd.id = rs.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _pre_generalization_create_view(
    name: str, source_table: str, *, extra_select: str = "", extra_join: str = ""
) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_pre_generalization_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_pre_generalization_resolved_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    return f"""
        CREATE VIEW {name} WITH (security_invoker = true) AS
        WITH RECURSIVE {_pre_generalization_resolved_stat_ctes(source_table)}
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id{extra_select},
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id
        FROM entity e
        JOIN {source_table} st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {extra_join}
        {joins}
        """


def downgrade() -> None:
    # Dependents (on v_effective_stat) go first, then v_effective_stat
    # itself, then the pre-generalization views are recreated exactly as
    # 6341fedbfc47 left them.
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute("DROP VIEW v_effective_stat")
    op.execute(_pre_generalization_create_view("v_item", "item"))
    op.execute(
        _pre_generalization_create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )
