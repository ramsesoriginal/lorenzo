"""Builds the R2 spike's repositories for one size and records their ids in a state file.

    python -m spike_r2.seed 5000

What it builds (RFC 0037 R2: "repositories of 1,000, 5,000 and 20,000 entries with realistic
stats, prototypes and attachments"), all in the spike database:

- `Core` (A): N entries (about 6 in 7 items, the rest beings), 6 stat groups, 42 stat definitions
  (int, float, bool, enum with 5 values, text; two of them derived), about five stored stat values
  on each entry, a linear formula on one entry in ten, a stat group on 3 in 10, a link name on 2
  in 3, a description (300 to 1,200 characters) on 4 in 5, a picture on 1 in 100 (the same 30 kB
  picture each time, so the blob table holds it once), and prototype edges in four tiers (depth up to 4, 15% with a second parent,
  3% with a third).
- `Bridge` (B): built on Core by an actual copy (`POST .../copy`), then N/10 entries of its own with
  parents among the copies, and N/20 attachments (a parent added to a copied entry).
- libraries: `Shelf` copied Core, `Stack` copied Bridge (and so Core), `Fresh` copied nothing.
- both repositories published once as release 1.0 while private, granted to the libraries.

Authored straight in the database with `generate_series`, as tests/test_stat_views_per_entity.py
does for its libraries; publishing, copying and everything measured go through the HTTP API.
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from typing import Any

from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from spike_r2.common import (
    app,
    Actor,
    admin_engine,
    admin_session_factory,
    new_client,
    save_state,
)

INTS = [
    "weight", "price", "rarity", "hp", "armor", "damage", "range", "speed", "level", "reach",
    "hit_bonus", "save_dc", "charges", "duration", "capacity", "bulk", "hardness", "value",
    "tier", "initiative",
]  # fmt: skip
FLOATS = ["weight_kg", "length_m", "volume_l", "damage_mult", "crit_mult", "drop_rate"]
BOOLS = ["magical", "cursed", "consumable", "two_handed", "stackable", "attuned"]
ENUMS = ["material", "rarity_class", "school", "damage_type"]
TEXTS = ["origin", "maker", "inscription", "note_short"]
DERIVED = ["derived_a", "derived_b"]
GROUPS = [("Core", 0), ("Combat", 5), ("Magic", 5), ("Economy", 9), ("Lore", 0), ("Misc", 2)]
KIND_NAMES = [
    "Longsword", "Shortbow", "Dagger", "Plate", "Shield", "Potion", "Scroll", "Amulet", "Staff",
    "Crossbow", "Lantern", "Rope",
]  # fmt: skip


def pseudo(salt: str, *parts: str) -> str:
    """SQL for a number in [0, 1) that depends only on the salt and the parts (SQL expressions)."""
    key = ", ".join((f"'{salt}'", *parts))
    return f"(abs(hashtextextended(concat_ws(':', {key}), 7) % 1000000) / 1000000.0)"


async def stat_vocabulary(session: AsyncSession, tenant: uuid.UUID) -> None:
    await session.execute(
        text(
            "INSERT INTO stat_group (tenant_id, name, priority, mandatory) "
            "SELECT :t, g, p, false FROM unnest(CAST(:names AS text[]), CAST(:prios AS int[])) "
            "AS v(g, p)"
        ),
        {"t": tenant, "names": [g for g, _ in GROUPS], "prios": [p for _, p in GROUPS]},
    )
    names = [*INTS, *FLOATS, *BOOLS, *ENUMS, *TEXTS, *DERIVED]
    types = (
        ["int"] * len(INTS)
        + ["float"] * len(FLOATS)
        + ["bool"] * len(BOOLS)
        + ["enum"] * len(ENUMS)
        + ["text"] * len(TEXTS)
        + ["int"] * len(DERIVED)
    )
    await session.execute(
        text(
            "INSERT INTO stat_definition (tenant_id, stat_group_id, name, value_type) "
            "SELECT :t, (SELECT id FROM stat_group WHERE tenant_id = :t ORDER BY name "
            "OFFSET (i % 6) LIMIT 1), nm, CAST(tp AS stat_value_type) "
            "FROM unnest(CAST(:names AS text[]), CAST(:types AS text[])) "
            "WITH ORDINALITY AS u(nm, tp, i)"
        ),
        {"t": tenant, "names": names, "types": types},
    )
    await session.execute(
        text(
            "INSERT INTO stat_definition_enum_value (tenant_id, stat_definition_id, value, "
            "sort_order) SELECT :t, d.id, 'v' || v, v FROM stat_definition d "
            "CROSS JOIN generate_series(1, 5) v WHERE d.tenant_id = :t AND d.value_type = 'enum'"
        ),
        {"t": tenant},
    )


async def description_and_pictures(session: AsyncSession, tenant: uuid.UUID, table: str) -> None:
    """A description on 4 in 5 entries of `table` (a temp table of (id, n)) and a picture on 1 in
    100 (an information of type main_picture)."""
    await session.execute(
        text(
            "CREATE TEMP TABLE infos ON COMMIT DROP AS "
            "SELECT gen_random_uuid() AS id, gen_random_uuid() AS payload_id, e.id AS entity_id, "
            f"e.n FROM {table} e WHERE {pseudo('described', 'e.n::text')} < 0.8"
        )
    )
    await session.execute(
        text(
            "INSERT INTO information (id, tenant_id, entity_id, title, type, is_public, \"order\") "
            "SELECT id, :t, entity_id, 'Description', 'description', true, 0 FROM infos"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO payload (id, tenant_id, information_id, \"order\") "
            "SELECT payload_id, :t, id, 0 FROM infos"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO payload_description (payload_id, tenant_id, locale, content) "
            "SELECT i.payload_id, :t, 'en', left((SELECT string_agg(md5(i.n::text || ':' || k), "
            f"' ') FROM generate_series(1, 40) k), 300 + floor({pseudo('len', 'i.n::text')} * 900)"
            "::int) FROM infos i"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "CREATE TEMP TABLE pics ON COMMIT DROP AS "
            "SELECT gen_random_uuid() AS id, gen_random_uuid() AS payload_id, e.id AS entity_id, "
            f"e.n FROM {table} e WHERE e.n % 100 = 3"
        )
    )
    await session.execute(
        text(
            "INSERT INTO information (id, tenant_id, entity_id, title, type, is_public, \"order\") "
            "SELECT id, :t, entity_id, 'Picture', 'main_picture', true, 1 FROM pics"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO payload (id, tenant_id, information_id, \"order\") "
            "SELECT payload_id, :t, id, 0 FROM pics"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO payload_picture (payload_id, tenant_id, data, file_type) "
            "SELECT payload_id, :t, convert_to(repeat(md5((p.n % 100)::text || :seed), 960), "
            "'UTF8'), 'png' FROM pics p"
        ),
        {"t": tenant, "seed": str(tenant)},
    )


async def stats_for(
    session: AsyncSession, tenant: uuid.UUID, table: str, *, int_defs_like: str = "%"
) -> None:
    """Stored stat values on the entities of `table`: three ints, and a float, a bool, an enum
    value and a text on about half of them (a third for the text)."""
    p = {"t": tenant, "like": int_defs_like}
    await session.execute(
        text(
            "INSERT INTO entity_stat (entity_id, stat_definition_id, tenant_id, value_int) "
            f"SELECT e.id, d.id, :t, (({pseudo('iv', 'e.n::text', 'd.name')}) * 200)::int "
            f"FROM {table} e JOIN LATERAL (SELECT id, name FROM stat_definition "
            "WHERE tenant_id = :t AND value_type = 'int' AND name NOT LIKE 'derived%' "
            "AND name LIKE :like "
            f"ORDER BY {pseudo('id', 'e.n::text', 'name')} LIMIT 3) d ON true"
        ),
        p,
    )
    for vtype, column, value, odds in (
        ("float", "value_float", f"({pseudo('fv', 'e.n::text', 'd.name')}) * 100", 0.5),
        ("bool", "value_bool", f"{pseudo('bv', 'e.n::text', 'd.name')} < 0.5", 0.5),
        (
            "enum",
            "value_text",
            f"'v' || (1 + floor({pseudo('ev', 'e.n::text', 'd.name')} * 5))::int",
            0.5,
        ),
        ("text", "value_text", "'text ' || e.n::text", 0.3),
    ):
        await session.execute(
            text(
                f"INSERT INTO entity_stat (entity_id, stat_definition_id, tenant_id, {column}) "
                f"SELECT e.id, d.id, :t, {value} FROM {table} e "
                "JOIN LATERAL (SELECT id, name FROM stat_definition "
                f"WHERE tenant_id = :t AND value_type = '{vtype}' "
                f"ORDER BY {pseudo('dd', 'e.n::text', 'name')} LIMIT 1) d ON true "
                f"WHERE {pseudo('has' + vtype, 'e.n::text')} < {odds}"
            ),
            p,
        )


async def formulas_and_groups(session: AsyncSession, tenant: uuid.UUID, table: str) -> None:
    await session.execute(
        text(
            "CREATE TEMP TABLE derived ON COMMIT DROP AS "
            "SELECT e.id AS entity_id, d.id AS definition_id, s.id AS source_id "
            f"FROM {table} e "
            "JOIN LATERAL (SELECT id FROM stat_definition WHERE tenant_id = :t AND "
            f"name LIKE 'derived%' ORDER BY {pseudo('der', 'e.n::text', 'name')} LIMIT 1) d "
            "ON true JOIN LATERAL (SELECT id FROM stat_definition WHERE tenant_id = :t AND "
            "value_type = 'int' AND name NOT LIKE 'derived%' "
            f"ORDER BY {pseudo('src', 'e.n::text', 'name')} LIMIT 1) s ON true "
            f"WHERE {pseudo('computed', 'e.n::text')} < 0.1"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO computed_stat (entity_id, stat_definition_id, tenant_id) "
            "SELECT entity_id, definition_id, :t FROM derived"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO computed_stat_linear (entity_id, stat_definition_id, tenant_id, "
            "source_stat_definition_id, multiplier, \"offset\", round_mode) "
            "SELECT entity_id, definition_id, :t, source_id, 0.5, 1, 'floor' FROM derived"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO entity_stat_group (entity_id, stat_group_id, tenant_id) "
            f"SELECT e.id, g.id, :t FROM {table} e JOIN LATERAL (SELECT id FROM stat_group "
            f"WHERE tenant_id = :t ORDER BY {pseudo('grp', 'e.n::text', 'name')} LIMIT 1) g "
            f"ON true WHERE {pseudo('grouped', 'e.n::text')} < 0.3"
        ),
        {"t": tenant},
    )


async def seed_core(session: AsyncSession, tenant: uuid.UUID, n: int) -> None:
    await stat_vocabulary(session, tenant)
    await session.execute(
        text(
            "CREATE TEMP TABLE ents ON COMMIT DROP AS "
            "SELECT gen_random_uuid() AS id, g AS n FROM generate_series(1, :n) g"
        ),
        {"n": n},
    )
    await session.execute(
        text(
            "INSERT INTO entity (id, tenant_id, name) SELECT id, :t, "
            "(CAST(:kinds AS text[]))[1 + (n % 12)] || ' ' || n FROM ents"
        ),
        {"t": tenant, "kinds": KIND_NAMES},
    )
    await session.execute(
        text(
            "INSERT INTO item (entity_id, tenant_id, in_public_catalog) "
            "SELECT id, :t, n % 2 = 0 FROM ents WHERE n % 7 <> 0"
        ),
        {"t": tenant},
    )
    await session.execute(
        text("INSERT INTO being (entity_id, tenant_id) SELECT id, :t FROM ents WHERE n % 7 = 0"),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO entity_slug (entity_id, tenant_id, slug) "
            "SELECT id, :t, lower((CAST(:kinds AS text[]))[1 + (n % 12)]) || '-' || n FROM ents "
            "WHERE n % 3 <> 0"
        ),
        {"t": tenant, "kinds": KIND_NAMES},
    )
    # Prototype edges in tiers: the first 1% have none, the next 4% take parents among those,
    # the next 15% among the first 5%, the rest among the first 20%: depth up to four.
    t0, t1, t2 = max(1, n // 100), max(2, n // 20), max(3, n // 5)
    await session.execute(
        text(
            "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
            "SELECT DISTINCT ON (c.id, p.id) c.id, p.id, :t, k - 1 FROM ents c "
            "CROSS JOIN generate_series(1, 3) k "
            "JOIN ents p ON p.n = 1 + floor(" + pseudo("parent", "c.n::text", "k::text") + " * "
            "CASE WHEN c.n <= :t1 THEN :t0 WHEN c.n <= :t2 THEN :t1 ELSE :t2 END)::int "
            "WHERE c.n > :t0 AND (k = 1 OR " + pseudo("more", "c.n::text", "k::text") + " < "
            "CASE k WHEN 2 THEN 0.15 ELSE 0.03 END) AND p.n < c.n "
            "ORDER BY c.id, p.id, k"
        ),
        {"t": tenant, "t0": t0, "t1": t1, "t2": t2},
    )
    await stats_for(session, tenant, "ents")
    await formulas_and_groups(session, tenant, "ents")
    await description_and_pictures(session, tenant, "ents")


async def seed_bridge_own(session: AsyncSession, tenant: uuid.UUID, n: int) -> None:
    """The bridge's own rows once Core is copied into it: n/10 entries with parents among the
    copies, a stat group and three definitions, and n/20 attachments."""
    own = max(10, n // 10)
    await session.execute(
        text(
            "INSERT INTO stat_group (tenant_id, name, priority, mandatory) "
            "VALUES (:t, 'Bridge', 3, false)"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "INSERT INTO stat_definition (tenant_id, stat_group_id, name, value_type) "
            "SELECT :t, (SELECT id FROM stat_group WHERE tenant_id = :t AND name = 'Bridge'), "
            "nm, 'int' FROM unnest(CAST(:names AS text[])) nm"
        ),
        {"t": tenant, "names": ["bridge_a", "bridge_b", "bridge_c"]},
    )
    # The copies, numbered as Core numbered them (the copy keeps the name, "Longsword 12").
    await session.execute(
        text(
            "CREATE TEMP TABLE copies ON COMMIT DROP AS "
            "SELECT l.entity_id AS id, split_part(e.name, ' ', 2)::int AS n "
            "FROM repository_copy_link_entity l JOIN entity e ON e.id = l.entity_id "
            "AND e.tenant_id = l.tenant_id WHERE l.tenant_id = :t AND l.entity_id IS NOT NULL"
        ),
        {"t": tenant},
    )
    await session.execute(
        text(
            "CREATE TEMP TABLE ents ON COMMIT DROP AS SELECT gen_random_uuid() AS id, g AS n "
            "FROM generate_series(1, :own) g"
        ),
        {"own": own},
    )
    await session.execute(
        text("INSERT INTO entity (id, tenant_id, name) SELECT id, :t, 'Bridge piece ' || n "
             "FROM ents"),
        {"t": tenant},
    )
    await session.execute(
        text("INSERT INTO item (entity_id, tenant_id) SELECT id, :t FROM ents"),
        {"t": tenant},
    )
    await session.execute(
        text("INSERT INTO entity_slug (entity_id, tenant_id, slug) "
             "SELECT id, :t, 'bridge-piece-' || n FROM ents"),
        {"t": tenant},
    )
    count = await session.scalar(text("SELECT count(*) FROM copies"))
    await session.execute(
        text(
            "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
            "SELECT DISTINCT ON (c.id, p.id) c.id, p.id, :t, k - 1 FROM ents c "
            "CROSS JOIN generate_series(1, 2) k JOIN copies p ON p.n = 1 + floor("
            + pseudo("bp", "c.n::text", "k::text") + " * :count)::int "
            "WHERE k = 1 OR " + pseudo("bp2", "c.n::text") + " < 0.3 ORDER BY c.id, p.id, k"
        ),
        {"t": tenant, "count": count},
    )
    await stats_for(session, tenant, "ents", int_defs_like="%")
    await description_and_pictures(session, tenant, "ents")
    # Attachments: one copy in twenty gets one more parent, a copy with a lower number.
    await session.execute(
        text(
            "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
            "SELECT c.id, p.id, :t, 50 FROM copies c JOIN copies p ON p.n = 1 + floor("
            + pseudo("att", "c.n::text") + " * (c.n - 1))::int WHERE c.n % 20 = 7 AND c.n > 1 "
            "ON CONFLICT DO NOTHING"
        ),
        {"t": tenant},
    )


async def vacuum() -> None:
    async with admin_engine.connect() as raw:
        conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("VACUUM (ANALYZE)"))


async def create_users() -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_session_factory() as session:
        ids: list[uuid.UUID] = []
        for name in ("author", "gm"):
            ids.append(
                (
                    await session.execute(
                        text(
                            "INSERT INTO app_user (authgear_subject_id) VALUES (:s) RETURNING id"
                        ),
                        {"s": f"spike|{name}|{uuid.uuid4()}"},
                    )
                ).scalar_one()
            )
        await session.commit()
    return ids[0], ids[1]


async def api(response: Any, expected: int | tuple[int, ...] = (200, 201, 204)) -> Any:
    allowed = (expected,) if isinstance(expected, int) else expected
    assert response.status_code in allowed, (response.status_code, response.text[:500])
    return response


async def build(size: int) -> dict[str, Any]:
    started = time.perf_counter()
    author_id, gm_id = await create_users()
    state: dict[str, Any] = {"size": size, "author": str(author_id), "gm": str(gm_id)}
    async with LifespanManager(app):
        async with new_client() as client:
            author, gm = Actor(client, author_id), Actor(client, gm_id)

            async def make(actor: Actor, name: str, kind: str) -> uuid.UUID:
                response = await api(await actor.post("/tenants", json={"name": name, "kind": kind}))
                return uuid.UUID(response.json()["id"])

            core = await make(author, f"Core {size}", "repository")
            bridge = await make(author, f"Bridge {size}", "repository")
            shelf = await make(gm, f"Shelf {size}", "play")
            stack = await make(gm, f"Stack {size}", "play")
            fresh = await make(gm, f"Fresh {size}", "play")
            state |= {
                "core": str(core),
                "bridge": str(bridge),
                "shelf": str(shelf),
                "stack": str(stack),
                "fresh": str(fresh),
            }

            t = time.perf_counter()
            async with admin_session_factory() as session, session.begin():
                await seed_core(session, core, size)
            state["seed_core_s"] = round(time.perf_counter() - t, 1)
            await vacuum()

            for repository, library in (
                (core, bridge), (core, shelf), (core, stack), (core, fresh),
                (bridge, stack), (bridge, fresh),
            ):  # fmt: skip
                await api(await author.put(f"/tenants/{repository}/subscribers/{library}"))

            t = time.perf_counter()
            await api(await author.put(f"/tenants/{core}/published", json={"label": "1.0"}))
            state["publish_core_first_s"] = round(time.perf_counter() - t, 2)

            # Bridge: copy Core in (an actual copy), then its own rows and attachments.
            t = time.perf_counter()
            response = await api(await author.post(f"/tenants/{bridge}/repositories/{core}/copy", json={}))
            state["copy_core_into_bridge_s"] = round(time.perf_counter() - t, 2)
            state["copy_core_into_bridge_steps"] = response.json()["steps"]
            t = time.perf_counter()
            async with admin_session_factory() as session, session.begin():
                await seed_bridge_own(session, bridge, size)
            state["seed_bridge_s"] = round(time.perf_counter() - t, 1)
            await vacuum()
            t = time.perf_counter()
            await api(await author.put(f"/tenants/{bridge}/published", json={"label": "1.0"}))
            state["publish_bridge_first_s"] = round(time.perf_counter() - t, 2)

            t = time.perf_counter()
            response = await api(await gm.post(f"/tenants/{shelf}/repositories/{core}/copy", json={}))
            state["copy_core_into_library_s"] = round(time.perf_counter() - t, 2)
            t = time.perf_counter()
            response = await api(await gm.post(f"/tenants/{stack}/repositories/{bridge}/copy", json={}))
            state["copy_bridge_into_library_s"] = round(time.perf_counter() - t, 2)
            state["copy_bridge_into_library_steps"] = response.json()["steps"]
    await vacuum()
    state["seed_total_s"] = round(time.perf_counter() - started, 1)
    save_state(size, state)
    return state


if __name__ == "__main__":
    import json

    print(json.dumps(asyncio.run(build(int(sys.argv[1]))), indent=2))
