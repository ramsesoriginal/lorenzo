"""resolve effective stats through the prototype graph in v_item/v_item_instance

Revision ID: 6341fedbfc47
Revises: fae51f1f72bc
Create Date: 2026-09-15 10:45:32.424263

"""

from collections.abc import Sequence

from alembic import op

revision: str = "6341fedbfc47"
down_revision: str | None = "fae51f1f72bc"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# name -> which value_* column - unchanged from the original 6c2f0a9d3e17
# migration (ADR 0019). Only what *populates* these columns changes here
# (ADR 0037/RFC 0008), not the view's own plain-column shape.
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_BOOL_STATS = ("is_magical", "is_cursed")

# entity_prototype's own BEFORE INSERT trigger (ADR 0015) already makes a
# cycle in this graph impossible, so this bound is a pure performance/
# pathological-depth safeguard, not a correctness necessity - mirrors
# entity_access.py's identical _MAX_CONTAINMENT_DEPTH bound for the
# unrelated (and genuinely cycle-tolerant) containment walk.
_MAX_PROTOTYPE_DEPTH = 50


def _resolved_stat_ctes(source_table: str) -> str:
    """RFC 0001's resolution rule, as the CTEs shared by every named-stat
    join below: walk entity_prototype outward from every source_table-typed
    entity (hop 0 is the entity itself - its own direct entity_stat row
    always wins outright, per RFC 0001), and for each stat_definition pick
    the value from the closest ancestor that sets it.

    Tie-break, precisely (ADR 0037 resolves what RFC 0001 left open - "the
    value acquired through the higher-priority stat group wins"): a given
    stat_definition has exactly one stat_group (UNIQUE(tenant_id, name)
    means there's only ever one canonical "weight" per tenant), so two
    ancestors both setting the *same* stat_definition always agree on that
    stat's own group - it can never discriminate between them. The
    priority that actually varies per ancestor is the highest-priority
    stat_group *that ancestor itself has acquired* (entity_stat_group) -
    that's what "value acquired through the higher-priority stat group"
    is read as here: which prototype's own contribution carries more
    authority, not which (fixed, shared) group the stat itself happens to
    live in. An ancestor with no acquired stat_group at all defaults to
    priority 0 (stat_group's own column default, ADR 0014). Still tied
    after that (equal hops, equal priority): sa.ancestor_id, an arbitrary
    but deterministic last resort - not spec'd further.
    """
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


def _resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT rs.entity_id, rs.{value_column}\n"
        f"    FROM resolved_stat rs\n"
        f"    JOIN stat_definition sd ON sd.id = rs.stat_definition_id\n"
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
    # security_invoker: unchanged from the original migration (ADR 0019) -
    # still required for RLS to actually apply through this view, and still
    # correct here - every table the CTEs above touch (entity,
    # entity_prototype, entity_stat, entity_stat_group, stat_group,
    # stat_definition) already carries its own tenant_id RLS policy, so the
    # walk is automatically tenant-scoped without an explicit filter of its
    # own, exactly like the original per-stat LEFT JOINs it replaces.
    return f"""
        CREATE VIEW {name} WITH (security_invoker = true) AS
        WITH RECURSIVE {_resolved_stat_ctes(source_table)}
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
    # Drop first (v_item_instance before v_item, matching the original
    # migration's own downgrade order) - both are plain SELECTs with no
    # dependents, so this is a clean replace, not a real dependency concern.
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute(_create_view("v_item", "item"))
    # owner_entity_id: derived via a LEFT JOIN against `ownership`, not a
    # stored item_instance column - that moved in migration 91d78aeb6caf
    # (ADR 0025), well before this one; item_instance itself has never had
    # an owner_entity_id column since.
    op.execute(
        _create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )


# --- Pre-resolution view SQL, as it stood immediately before this migration
# (ADR 0019's original v_item, and v_item_instance as migration 91d78aeb6caf
# / ADR 0025 left it) - inlined here rather than imported from either of
# those files, so this migration stays a self-contained snapshot downgrade
# can always replay even if a future change edits or removes their own
# helpers.
_PRE_RESOLUTION_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_PRE_RESOLUTION_BOOL_STATS = ("is_magical", "is_cursed")


def _pre_resolution_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT es.entity_id, es.{value_column}\n"
        f"    FROM entity_stat es\n"
        f"    JOIN stat_definition sd ON sd.id = es.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _pre_resolution_create_view(
    name: str, source_table: str, *, extra_select: str = "", extra_join: str = ""
) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _PRE_RESOLUTION_INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _PRE_RESOLUTION_BOOL_STATS]
    )
    joins = "\n".join(
        [_pre_resolution_stat_join(stat, "value_int") for stat in _PRE_RESOLUTION_INT_STATS]
        + [_pre_resolution_stat_join(stat, "value_bool") for stat in _PRE_RESOLUTION_BOOL_STATS]
    )
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


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute(_pre_resolution_create_view("v_item", "item"))
    op.execute(
        _pre_resolution_create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )
