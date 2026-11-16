"""ADR 0448: a game system as a row - its routes, the groups that carry one, the prefix rule on
the names of their stats, what a stat row says of where it comes from, and RLS on the table.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from test_api_computed_stats import _entity

from lorenzo_api.db import engine
from lorenzo_api.models import EntityStat, StatDefinition


async def _system(client: AsyncClient, tenant_id: uuid.UUID, slug: str, **extra: object) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/systems", json={"slug": slug, "name": slug.upper(), **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str, **extra: object) -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def _stat(
    client: AsyncClient, tenant_id: uuid.UUID, group_id: str, name: str
) -> tuple[int, dict]:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": name, "value_type": "int"},
    )
    return response.status_code, response.json()


# --- the routes -----------------------------------------------------------------------------


async def test_a_system_is_made_read_edited_and_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entry = await _entity(tenant_id, "Rules of Draw")

    made = await _system(client, tenant_id, "ds", root_entry_id=str(entry))
    other = await _system(client, tenant_id, "bitd")
    fetched = await client.get(f"/tenants/{tenant_id}/systems/{made['id']}")
    listed = await client.get(f"/tenants/{tenant_id}/systems")
    renamed = await client.patch(
        f"/tenants/{tenant_id}/systems/{made['id']}",
        json={"name": "Draw Steel", "root_entry_id": None},
    )
    reslugged = await client.patch(
        f"/tenants/{tenant_id}/systems/{other['id']}", json={"slug": "blades"}
    )
    deleted = await client.delete(f"/tenants/{tenant_id}/systems/{other['id']}")
    gone = await client.get(f"/tenants/{tenant_id}/systems/{other['id']}")

    assert (made["slug"], made["root_entry_id"]) == ("ds", str(entry))
    assert fetched.json()["name"] == "DS"
    assert [s["slug"] for s in listed.json()["items"]] == ["bitd", "ds"]
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["name"], renamed.json()["root_entry_id"]) == ("Draw Steel", None)
    assert reslugged.json()["slug"] == "blades"
    assert (deleted.status_code, gone.status_code) == (204, 404)
    await delete_tenant(tenant_id)


async def test_a_slug_is_a_short_lowercase_word_and_unique(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _system(client, tenant_id, "dnd")

    bad = {
        slug: (
            await client.post(f"/tenants/{tenant_id}/systems", json={"slug": slug, "name": "x"})
        ).status_code
        for slug in ("DnD", "d_d", "5e", "", "a" * 33, "with space")
    }
    duplicate = await client.post(
        f"/tenants/{tenant_id}/systems", json={"slug": "dnd", "name": "again"}
    )
    clash = await _system(client, tenant_id, "pf")
    taken = await client.patch(f"/tenants/{tenant_id}/systems/{clash['id']}", json={"slug": "dnd"})
    no_root = await client.post(
        f"/tenants/{tenant_id}/systems",
        json={"slug": "ten", "name": "10 Candles", "root_entry_id": str(uuid.uuid4())},
    )

    assert set(bad.values()) == {422}
    assert duplicate.status_code == 409
    assert taken.status_code == 409
    assert no_root.status_code == 422
    await delete_tenant(tenant_id)


# --- groups, and the prefix rule ---------------------------------------------------------------


async def test_a_definition_of_a_system_starts_with_its_slug_and_an_underscore(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    group = await _group(client, tenant_id, "Draw Steel", system_id=ds["id"])
    neutral = await _group(client, tenant_id, "Core")

    ok, made = await _stat(client, tenant_id, group["id"], "ds_stamina")
    bad, _ = await _stat(client, tenant_id, group["id"], "stamina")
    bare, _ = await _stat(client, tenant_id, group["id"], "ds_")
    other_system, _ = await _stat(client, tenant_id, group["id"], "dsx_stamina")
    free, _ = await _stat(client, tenant_id, neutral["id"], "stamina")
    renamed_wrong = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{made['id']}", json={"name": "stamina"}
    )
    renamed_right = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{made['id']}", json={"name": "ds_recoveries"}
    )

    assert group["system_id"] == ds["id"] and neutral["system_id"] is None
    assert (ok, bad, bare, other_system, free) == (201, 422, 422, 422, 201)
    assert renamed_wrong.status_code == 422
    assert renamed_wrong.json()["type"].endswith("stat-name-prefix")
    assert renamed_right.status_code == 200, renamed_right.text
    await delete_tenant(tenant_id)


async def test_a_group_takes_a_system_only_when_its_stats_carry_the_prefix(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    bitd = await _system(client, tenant_id, "bitd")
    group = await _group(client, tenant_id, "Mixed")
    _, plain = await _stat(client, tenant_id, group["id"], "stamina")
    await _stat(client, tenant_id, group["id"], "ds_might")
    url = f"/tenants/{tenant_id}/stat-groups/{group['id']}"

    refused = await client.patch(url, json={"system_id": ds["id"]})
    await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{plain['id']}", json={"name": "ds_stamina"}
    )
    taken = await client.patch(url, json={"system_id": ds["id"]})
    moved = await client.patch(url, json={"system_id": bitd["id"]})
    unknown = await client.patch(url, json={"system_id": str(uuid.uuid4())})
    cleared = await client.patch(url, json={"system_id": None})
    renamed = await client.patch(url, json={"priority": 3})

    assert refused.status_code == 422
    assert refused.json()["type"].endswith("stat-name-prefix")
    assert "stamina" in refused.json()["detail"]
    assert taken.status_code == 200 and taken.json()["system_id"] == ds["id"]
    # The names carry ds_, not bitd_.
    assert moved.status_code == 422
    assert unknown.status_code == 422
    assert cleared.status_code == 200 and cleared.json()["system_id"] is None
    assert renamed.status_code == 200, renamed.text
    await delete_tenant(tenant_id)


async def test_a_slug_stays_while_a_group_uses_it_and_a_system_is_not_deleted_then(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    group = await _group(client, tenant_id, "Draw Steel", system_id=ds["id"])
    base = f"/tenants/{tenant_id}/systems/{ds['id']}"

    reslug = await client.patch(base, json={"slug": "dsx"})
    delete = await client.delete(base)
    renamed = await client.patch(base, json={"name": "Draw Steel"})
    await client.patch(f"/tenants/{tenant_id}/stat-groups/{group['id']}", json={"system_id": None})
    freed = await client.patch(base, json={"slug": "dsx"})
    deleted = await client.delete(base)

    assert reslug.status_code == 409 and reslug.json()["type"].endswith("system-slug-in-use")
    assert delete.status_code == 409 and delete.json()["type"].endswith("system-in-use")
    assert renamed.status_code == 200
    assert freed.status_code == 200 and freed.json()["slug"] == "dsx"
    assert deleted.status_code == 204
    await delete_tenant(tenant_id)


# --- what a stat row says -----------------------------------------------------------------------


async def test_a_stat_row_says_its_definition_group_and_system(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    group = await _group(client, tenant_id, "Draw Steel", system_id=ds["id"])
    neutral = await _group(client, tenant_id, "Core")
    _, stamina = await _stat(client, tenant_id, group["id"], "ds_stamina")
    _, speed = await _stat(client, tenant_id, neutral["id"], "speed")
    hero = await _entity(tenant_id, "Hero")
    async with admin_session_factory() as session:
        for definition, value in ((stamina, 30), (speed, 6)):
            session.add(
                EntityStat(
                    entity_id=hero,
                    stat_definition_id=uuid.UUID(definition["id"]),
                    tenant_id=tenant_id,
                    value_int=value,
                )
            )
        await session.commit()

    detail = (await client.get(f"/tenants/{tenant_id}/entities/{hero}")).json()
    rows = {s["name"]: s for s in detail["stats"]}
    bulk = (
        await client.get(
            f"/tenants/{tenant_id}/entities/effective-stats",
            params=[("stat_definition_id", stamina["id"]), ("stat_definition_id", speed["id"])],
        )
    ).json()
    explained = (
        await client.get(f"/tenants/{tenant_id}/entities/{hero}/stats/{stamina['id']}/explanation")
    ).json()

    assert rows["ds_stamina"]["system"] == "ds"
    assert rows["ds_stamina"]["group_id"] == group["id"]
    assert rows["ds_stamina"]["stat_definition_id"] == stamina["id"]
    assert rows["speed"]["system"] is None and rows["speed"]["group_id"] == neutral["id"]
    hero_row = next(e for e in bulk["items"] if e["id"] == str(hero))
    by_stat = {s["stat_definition_id"]: s for s in hero_row["stats"]}
    assert by_stat[stamina["id"]]["system"] == "ds"
    assert by_stat[speed["id"]]["system"] is None
    assert explained["system"] == "ds" and explained["group_id"] == group["id"]
    await delete_tenant(tenant_id)


async def test_a_definition_keeps_its_group_so_its_system_is_permanent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    group = await _group(client, tenant_id, "Draw Steel", system_id=ds["id"])
    other = await _group(client, tenant_id, "Core")
    _, stat = await _stat(client, tenant_id, group["id"], "ds_stamina")

    moved = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{stat['id']}", json={"stat_group_id": other["id"]}
    )

    assert moved.status_code == 422
    async with admin_session_factory() as session:
        kept = await session.scalar(
            select(StatDefinition.stat_group_id).where(StatDefinition.id == uuid.UUID(stat["id"]))
        )
    assert str(kept) == group["id"]
    await delete_tenant(tenant_id)


# --- RLS ----------------------------------------------------------------------------------------


async def test_the_system_table_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for slug in ("one", "two"):
        tenant_id = await make_tenant(test_user_id)
        await _system(client, tenant_id, slug)
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                tenants = (await conn.execute(text("SELECT tenant_id FROM system"))).scalars().all()
                assert set(tenants) == {tenant_id}
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
