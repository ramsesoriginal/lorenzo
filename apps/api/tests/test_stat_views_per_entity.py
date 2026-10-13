"""ADR 0285: v_effective_stat, v_item and v_item_instance resolve per entity.

The views used to start their recursive walk from every entity in the tenant, so reading one
entity cost as much as reading the library. These tests hold the two halves of the change: the
rows are what they were (the old definitions, kept here as the reference they are compared with),
and a read of one entity walks only that entity's prototypes.
"""

import json
import uuid
from typing import Any

from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import Tenant

_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")

# v_effective_stat as c8e2a5d19f47 left it (ADR 0266, 0276): one recursive walk from every entity.
_REFERENCE_V_EFFECTIVE_STAT = """
CREATE TEMP VIEW ref_effective_stat AS
WITH RECURSIVE
    stat_ancestor(root_entity_id, ancestor_id, hops, path) AS (
        SELECT e.id, e.id, 0, ARRAY[]::integer[]
        FROM entity e
        UNION ALL
        SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1, sa.path || ep.position
        FROM stat_ancestor sa
        JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
        WHERE sa.hops < 50
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
ORDER BY sa.root_entity_id, c.stat_definition_id, sa.hops ASC, c.is_computed ASC,
    COALESCE(ap.priority, 0) DESC, sa.path ASC, sa.ancestor_id
"""


def _reference_stat_joins() -> str:
    return "\n".join(
        f"""
LEFT JOIN (
    SELECT ves.entity_id, ves.value_int
    FROM ref_effective_stat ves
    JOIN stat_definition sd ON sd.id = ves.stat_definition_id
    WHERE sd.name = '{name}'
) {name} ON {name}.entity_id = e.id"""
        for name in _INT_STATS
    )


_REFERENCE_STAT_COLUMNS = ", ".join(f"{name}.value_int AS {name}" for name in _INT_STATS)

# v_item and v_item_instance as they joined the view once per stat.
_REFERENCE_V_ITEM = f"""
CREATE TEMP VIEW ref_item AS
SELECT e.id AS entity_id, e.tenant_id AS tenant_id,
    description_info.id AS description_id, description_info.title AS title,
    {_REFERENCE_STAT_COLUMNS},
    containment.parent_entity_id AS container_entity_id, containment.quantity AS quantity
FROM entity e
JOIN item st ON st.entity_id = e.id
LEFT JOIN information description_info
    ON description_info.entity_id = e.id AND description_info.type = 'description'
LEFT JOIN containment ON containment.child_entity_id = e.id{_reference_stat_joins()}
"""

_REFERENCE_V_ITEM_INSTANCE = f"""
CREATE TEMP VIEW ref_item_instance AS
SELECT e.id AS entity_id, e.tenant_id AS tenant_id,
    ownership.owner_character_id AS owner_entity_id, entity_slug.slug AS slug,
    description_info.id AS description_id, description_info.title AS title,
    {_REFERENCE_STAT_COLUMNS},
    containment.parent_entity_id AS container_entity_id, containment.quantity AS quantity
FROM entity e
JOIN item_instance st ON st.entity_id = e.id
LEFT JOIN information description_info
    ON description_info.entity_id = e.id AND description_info.type = 'description'
LEFT JOIN containment ON containment.child_entity_id = e.id
LEFT JOIN ownership ON ownership.owned_entity_id = e.id
LEFT JOIN entity_slug ON entity_slug.entity_id = e.id{_reference_stat_joins()}
"""


async def _library(session: AsyncSession, entities: int, *, linked: bool) -> uuid.UUID:
    """A tenant with `entities` entries; with `linked`, a random acyclic graph of parents (each
    entry has up to a few, among the dozen before it, in an order of their own), stats of its
    own, formulas, and stat groups with priorities, so that every way a stat is chosen is used."""
    tenant = Tenant(name="stat-views")
    session.add(tenant)
    await session.flush()
    parameters = {"tenant": tenant.id, "entities": entities}
    await session.execute(text("SELECT setseed(0.285)"))
    await session.execute(
        text(
            "INSERT INTO stat_group (tenant_id, name, priority) "
            "SELECT :tenant, g, p FROM (VALUES ('A', 0), ('B', 5), ('C', 5), ('D', 9)) v(g, p)"
        ),
        parameters,
    )
    await session.execute(
        text(
            "INSERT INTO stat_definition (tenant_id, stat_group_id, name, value_type) "
            "SELECT :tenant, (SELECT id FROM stat_group WHERE tenant_id = :tenant AND name = 'A'), "
            "n, 'int' FROM unnest(CAST(:names AS text[])) n"
        ),
        {**parameters, "names": [*_INT_STATS, "dmg", "ac", "speed", "luck"]},
    )
    await session.execute(
        text(
            "CREATE TEMP TABLE ents ON COMMIT DROP AS "
            "SELECT gen_random_uuid() AS id, g AS n FROM generate_series(1, :entities) g"
        ),
        parameters,
    )
    await session.execute(
        text("INSERT INTO entity (id, tenant_id, name) SELECT id, :tenant, 'e' || n FROM ents"),
        parameters,
    )
    if not linked:
        return tenant.id
    for statement in (
        # up to a few parents among the twelve entries before, each with a position of its own
        "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
        "SELECT DISTINCT ON (c.id, p.id) c.id, p.id, :tenant, (random() * 5)::int FROM ents c "
        "JOIN LATERAL (SELECT id FROM ents p WHERE p.n < c.n AND p.n >= greatest(1, c.n - 12) "
        "AND random() < 0.10) p ON true WHERE c.n > 1",
        # stats of their own, some on a definition an ancestor has too
        "INSERT INTO entity_stat (entity_id, stat_definition_id, tenant_id, value_int) "
        "SELECT DISTINCT ON (e.id, d.id) e.id, d.id, :tenant, (random() * 100)::int FROM ents e "
        "JOIN LATERAL (SELECT id FROM stat_definition WHERE tenant_id = :tenant AND e.n > 0 "
        "ORDER BY random() LIMIT 2) d ON true "
        "WHERE random() < 0.7",
        # formulas, some on a definition the same entry also holds a stored value for
        "INSERT INTO computed_stat (entity_id, stat_definition_id, tenant_id) "
        "SELECT DISTINCT ON (e.id, d.id) e.id, d.id, :tenant FROM ents e "
        "JOIN LATERAL (SELECT id FROM stat_definition WHERE tenant_id = :tenant AND e.n > 0 "
        "ORDER BY random() LIMIT 1) d ON true "
        "WHERE random() < 0.25",
        # groups, so that their priority breaks a tie
        "INSERT INTO entity_stat_group (entity_id, stat_group_id, tenant_id) "
        "SELECT DISTINCT ON (e.id, g.id) e.id, g.id, :tenant FROM ents e "
        "JOIN LATERAL (SELECT id FROM stat_group WHERE tenant_id = :tenant AND e.n > 0 "
        "ORDER BY random() LIMIT 1) g ON true "
        "WHERE random() < 0.4",
        # the even ones are items, the odd ones instances of them
        "INSERT INTO item (entity_id, tenant_id) SELECT id, :tenant FROM ents WHERE n % 2 = 0",
        "INSERT INTO item_instance (entity_id, tenant_id) SELECT id, :tenant FROM ents "
        "WHERE n % 2 = 1",
    ):
        await session.execute(text(statement), parameters)
    return tenant.id


async def _only_in_first(session: AsyncSession, first: str, second: str, tenant: uuid.UUID) -> int:
    result = await session.execute(
        text(
            f"SELECT count(*) FROM (SELECT * FROM {first} WHERE tenant_id = :tenant "
            f"EXCEPT SELECT * FROM {second} WHERE tenant_id = :tenant) differing"
        ),
        {"tenant": tenant},
    )
    return int(result.scalar_one())


async def _count(
    session: AsyncSession, relation: str, tenant: uuid.UUID, where: str = "true"
) -> int:
    result = await session.execute(
        text(f"SELECT count(*) FROM {relation} WHERE tenant_id = :tenant AND {where}"),
        {"tenant": tenant},
    )
    return int(result.scalar_one())


async def test_the_views_return_the_rows_they_returned_before() -> None:
    """The reference definitions are the ones this change replaced: every row of the new views is
    a row of theirs and the other way round, over a library that uses every way a stat is chosen."""
    async with admin_session_factory() as session:
        tenant_id = await _library(session, 140, linked=True)
        for reference in (
            _REFERENCE_V_EFFECTIVE_STAT,
            _REFERENCE_V_ITEM,
            _REFERENCE_V_ITEM_INSTANCE,
        ):
            await session.execute(text(reference))
        await session.flush()
        try:
            # What the comparison is made of: not an empty library, and every way a stat is
            # chosen is in it (inherited, a formula, a formula beating or losing to a stored value).
            assert await _count(session, "v_effective_stat", tenant_id) > 140
            assert (
                await _count(
                    session, "v_effective_stat", tenant_id, "computed_entity_id IS NOT NULL"
                )
                > 5
            )
            assert (
                await _count(
                    session, "v_effective_stat", tenant_id, "source_entity_id <> entity_id"
                )
                > 5
            )
            assert await _count(session, "v_item", tenant_id) == 70
            assert await _count(session, "v_item_instance", tenant_id) == 70
            assert await _count(session, "v_item", tenant_id, "weight IS NOT NULL") > 10

            for new, old in (
                ("v_effective_stat", "ref_effective_stat"),
                ("v_item", "ref_item"),
                ("v_item_instance", "ref_item_instance"),
            ):
                assert await _only_in_first(session, new, old, tenant_id) == 0, new
                assert await _only_in_first(session, old, new, tenant_id) == 0, old
        finally:
            await session.rollback()


def _recursive_rows(plan: Any) -> int:
    """The rows every recursive walk in a plan produced, over all its loops."""
    total = 0
    if isinstance(plan, dict):
        if plan.get("Node Type") == "Recursive Union":
            total += int(plan.get("Actual Rows", 0)) * int(plan.get("Actual Loops", 1))
        for value in plan.values():
            total += _recursive_rows(value)
    elif isinstance(plan, list):
        for value in plan:
            total += _recursive_rows(value)
    return total


async def test_a_read_of_one_entity_walks_that_entity_and_not_the_library() -> None:
    """Three hundred entries that have nothing to do with the one read: the walks of a read of it
    produce a handful of rows (its own chain), where the old views' walks produced a row for every
    entry of the library, six times over for an item."""
    async with admin_session_factory() as session:
        tenant_id = await _library(session, 300, linked=False)
        # one chain of four, the last an item: base <- mid <- leaf, and the leaf's own item row
        await session.execute(
            text(
                "WITH chain AS (SELECT id, row_number() OVER (ORDER BY name) AS k FROM entity "
                "WHERE tenant_id = :tenant AND name IN ('e1', 'e2', 'e3', 'e4')) "
                "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
                "SELECT a.id, b.id, :tenant, 0 FROM chain a JOIN chain b ON b.k = a.k + 1"
            ),
            {"tenant": tenant_id},
        )
        await session.execute(
            text(
                "INSERT INTO item (entity_id, tenant_id) "
                "SELECT id, :tenant FROM entity WHERE tenant_id = :tenant AND name = 'e1'"
            ),
            {"tenant": tenant_id},
        )
        await session.execute(text("ANALYZE entity, entity_prototype, item"))
        entity_id = (
            await session.execute(
                text("SELECT id FROM entity WHERE tenant_id = :tenant AND name = 'e1'"),
                {"tenant": tenant_id},
            )
        ).scalar_one()
        walked: dict[str, int] = {}
        try:
            for view in ("v_effective_stat", "v_item"):
                plan = (
                    await session.execute(
                        text(
                            f"EXPLAIN (ANALYZE, FORMAT JSON) SELECT * FROM {view} "
                            "WHERE entity_id = :entity_id"
                        ),
                        {"entity_id": entity_id},
                    )
                ).scalar_one()
                walked[view] = _recursive_rows(json.loads(plan) if isinstance(plan, str) else plan)
        finally:
            await session.rollback()
    # The chain is four entries: the walk is four rows, and an item's one walk is the same four.
    # Reading the library would be 300 or more (1,800 for v_item before this change).
    assert 0 < walked["v_effective_stat"] <= 10, walked
    assert 0 < walked["v_item"] <= 10, walked
