"""ADR 0450: `?system=<slug>` on the entity read and the bulk read narrows the stats to those of
no game system and that system's, resolves every value as without it, and 404s on a slug that is
not the library's.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_computed_stats import _entity

from lorenzo_api.models import EntitySlug


async def _post(client: AsyncClient, url: str, body: dict) -> dict:
    response = await client.post(url, json=body)
    assert response.status_code == 201, response.text
    return response.json()


class World:
    """Two game systems and a neutral group, each with one stat, and an entry holding all three
    and a formula of the second system that reads the first's."""

    def __init__(self, tenant_id: uuid.UUID, ids: dict[str, str], entry: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.ids = ids
        self.entry = entry


async def _world(client: AsyncClient, tenant_id: uuid.UUID) -> World:
    base = f"/tenants/{tenant_id}"
    ds = await _post(client, f"{base}/systems", {"slug": "ds", "name": "Draw Steel"})
    pf = await _post(client, f"{base}/systems", {"slug": "pf", "name": "Pathfinder"})
    groups = {
        "ds": await _post(client, f"{base}/stat-groups", {"name": "DS", "system_id": ds["id"]}),
        "pf": await _post(client, f"{base}/stat-groups", {"name": "PF", "system_id": pf["id"]}),
        "neutral": await _post(client, f"{base}/stat-groups", {"name": "Notes"}),
    }
    ids: dict[str, str] = {}
    for name, group in (
        ("ds_stamina", "ds"),
        ("ds_bonus", "ds"),
        ("pf_strength", "pf"),
        ("reach", "neutral"),
    ):
        made = await _post(
            client,
            f"{base}/stat-definitions",
            {"stat_group_id": groups[group]["id"], "name": name, "value_type": "int"},
        )
        ids[name] = made["id"]
    entry = await _entity(
        tenant_id,
        "Hero",
        stats={
            uuid.UUID(ids["ds_stamina"]): 20,
            uuid.UUID(ids["pf_strength"]): 18,
            uuid.UUID(ids["reach"]): 2,
        },
    )
    formula = await client.put(
        f"{base}/entities/{entry}/computed-stats/{ids['ds_bonus']}",
        json={
            "kind": "linear",
            "multiplier": 0.5,
            "offset": -5,
            "round_mode": "floor",
            "source_stat_definition_id": ids["pf_strength"],
        },
    )
    assert formula.status_code == 200, formula.text
    return World(tenant_id, ids, entry)


def _names(body: dict) -> list[str]:
    return sorted(s["name"] for s in body["stats"])


async def test_the_entity_read_keeps_the_stats_of_no_system_and_of_the_one_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    world = await _world(client, tenant_id)
    url = f"/tenants/{tenant_id}/entities/{world.entry}"

    whole = (await client.get(url)).json()
    ds = (await client.get(url, params={"system": "ds"})).json()
    pf = (await client.get(url, params={"system": "pf"})).json()

    assert _names(whole) == ["ds_bonus", "ds_stamina", "pf_strength", "reach"]
    assert _names(ds) == ["ds_bonus", "ds_stamina", "reach"]
    assert _names(pf) == ["pf_strength", "reach"]
    # The formula of a system that reads another's still reads it: the filter shows, not resolves.
    assert {s["name"]: s["value"] for s in ds["stats"]}["ds_bonus"] == 4
    assert {s["name"]: s["value"] for s in whole["stats"]}["ds_bonus"] == 4
    await delete_tenant(tenant_id)


async def test_a_slug_that_is_not_a_system_of_the_library_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other_tenant = await make_tenant(test_user_id)
    await _post(
        client, f"/tenants/{other_tenant}/systems", {"slug": "elsewhere", "name": "Elsewhere"}
    )
    world = await _world(client, tenant_id)
    url = f"/tenants/{tenant_id}/entities/{world.entry}"

    unknown = await client.get(url, params={"system": "nope"})
    theirs = await client.get(url, params={"system": "elsewhere"})
    bulk = await client.get(
        f"/tenants/{tenant_id}/entities/effective-stats",
        params={"stat_definition_id": world.ids["reach"], "system": "nope"},
    )

    assert (unknown.status_code, theirs.status_code, bulk.status_code) == (404, 404, 404)
    assert unknown.json()["type"].endswith("system-not-found")
    await delete_tenant(tenant_id)
    await delete_tenant(other_tenant)


async def test_the_entity_read_by_slug_takes_the_filter_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    world = await _world(client, tenant_id)
    async with admin_session_factory() as session:
        session.add(EntitySlug(entity_id=world.entry, tenant_id=tenant_id, slug="hero"))
        await session.commit()

    read = await client.get(f"/tenants/{tenant_id}/entities/by-slug/hero", params={"system": "pf"})

    assert read.status_code == 200, read.text
    assert _names(read.json()) == ["pf_strength", "reach"]
    await delete_tenant(tenant_id)


async def test_the_bulk_read_leaves_out_the_stats_of_other_systems(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    world = await _world(client, tenant_id)
    params: list[tuple[str, str]] = [
        ("stat_definition_id", world.ids[name])
        for name in ("ds_stamina", "ds_bonus", "pf_strength", "reach")
    ]
    url = f"/tenants/{tenant_id}/entities/effective-stats"

    def row(body: dict) -> dict[str, int]:
        (hero,) = [item for item in body["items"] if item["id"] == str(world.entry)]
        by_id = {v: k for k, v in world.ids.items()}
        return {by_id[s["stat_definition_id"]]: s["value"] for s in hero["stats"]}

    whole = (await client.get(url, params=params)).json()
    ds = (await client.get(url, params=[*params, ("system", "ds")])).json()
    pf = (await client.get(url, params=[*params, ("system", "pf")])).json()

    assert row(whole) == {"ds_stamina": 20, "ds_bonus": 4, "pf_strength": 18, "reach": 2}
    assert row(ds) == {"ds_stamina": 20, "ds_bonus": 4, "reach": 2}
    assert row(pf) == {"pf_strength": 18, "reach": 2}
    await delete_tenant(tenant_id)


async def test_a_library_with_no_system_reads_as_it_did(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _post(client, f"/tenants/{tenant_id}/stat-groups", {"name": "Plain"})
    stat = await _post(
        client,
        f"/tenants/{tenant_id}/stat-definitions",
        {"stat_group_id": group["id"], "name": "speed", "value_type": "int"},
    )
    entry = await _entity(tenant_id, "Cart", stats={uuid.UUID(stat["id"]): 3})

    read = await client.get(f"/tenants/{tenant_id}/entities/{entry}")

    assert _names(read.json()) == ["speed"]
    await delete_tenant(tenant_id)
