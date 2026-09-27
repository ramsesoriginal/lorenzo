"""ADR 0127: contents formulas through the real API - the weight recipe on
every read path that serializes stats, containment cycles, the write-time
checks, preview, dependents, and RLS on the new table.
"""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_computed_stats import _put, _sheet, _stats

from lorenzo_api.db import engine
from lorenzo_api.models import (
    ComputedStatContents,
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    Item,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    StatValueType,
)


def _contents(source: uuid.UUID) -> dict:
    return {"kind": "contents", "source_stat_definition_id": str(source)}


async def _thing(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    *,
    prototype: uuid.UUID,
    own_weight: uuid.UUID,
    weight: int | None,
    inside: uuid.UUID | None = None,
    quantity: int = 1,
    catalog: bool = False,
) -> uuid.UUID:
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    kind = Item if catalog else ItemInstance
    session.add(kind(entity_id=entity.id, tenant_id=tenant_id))
    session.add(EntityPrototype(entity_id=entity.id, prototype_id=prototype, tenant_id=tenant_id))
    if weight is not None:
        session.add(
            EntityStat(
                entity_id=entity.id,
                stat_definition_id=own_weight,
                tenant_id=tenant_id,
                value_int=weight,
            )
        )
    if inside is not None:
        session.add(
            Containment(
                child_entity_id=entity.id,
                parent_entity_id=inside,
                tenant_id=tenant_id,
                quantity=quantity,
            )
        )
    await session.flush()
    return entity.id


@dataclass
class _Packed:
    tenant_id: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _packed(client: AsyncClient, test_user_id: uuid.UUID) -> _Packed:
    """The weight recipe on a Gear prototype, and Hero carrying a Backpack
    (2) holding a Rope (1), 20 Arrows (1 each), an unweighed Torch, and a
    Pouch (1) with 3 Coins (1 each): the Backpack weighs 27, the Pouch 4.
    A catalog Crate (10) holds a Lantern (3)."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        own_weight=StatValueType.INT,
        contents_weight=StatValueType.INT,
        weight=StatValueType.INT,
        carried_weight=StatValueType.INT,
    )
    async with admin_session_factory() as session:
        gear = Entity(tenant_id=tenant_id, name="Gear")
        session.add(gear)
        await session.flush()
        session.add(Item(entity_id=gear.id, tenant_id=tenant_id))
        hero = (await make_being(session, tenant_id=tenant_id, name="Hero")).entity_id
        await session.commit()

    for stat, formula in (
        ("contents_weight", _contents(sheet["weight"])),
        (
            "weight",
            {
                "kind": "sum",
                "terms": [
                    {"stat_definition_id": str(sheet["own_weight"])},
                    {"stat_definition_id": str(sheet["contents_weight"])},
                ],
            },
        ),
    ):
        await _put(client, sheet.formula_url(gear.id, stat), formula)
    await _put(client, sheet.formula_url(hero, "carried_weight"), _contents(sheet["weight"]))

    async with admin_session_factory() as session:
        thing = {"prototype": gear.id, "own_weight": sheet["own_weight"]}
        ids = {"hero": hero, "gear": gear.id}
        ids["backpack"] = await _thing(
            session, tenant_id, "Backpack", **thing, weight=2, inside=hero
        )
        session.add(
            Ownership(owned_entity_id=ids["backpack"], owner_character_id=hero, tenant_id=tenant_id)
        )
        session.add(EntitySlug(entity_id=ids["backpack"], tenant_id=tenant_id, slug="pack"))
        for name, weight, quantity in (("Rope", 1, 1), ("Arrows", 1, 20), ("Torch", None, 1)):
            ids[name.lower()] = await _thing(
                session,
                tenant_id,
                name,
                **thing,
                weight=weight,
                inside=ids["backpack"],
                quantity=quantity,
            )
        ids["pouch"] = await _thing(
            session, tenant_id, "Pouch", **thing, weight=1, inside=ids["backpack"]
        )
        ids["coins"] = await _thing(
            session, tenant_id, "Coins", **thing, weight=1, inside=ids["pouch"], quantity=3
        )
        ids["crate"] = await _thing(session, tenant_id, "Crate", **thing, weight=10, catalog=True)
        ids["lantern"] = await _thing(
            session, tenant_id, "Lantern", **thing, weight=3, inside=ids["crate"]
        )
        # ORGA reaches every holder (ADR 0040), for held-by below.
        (await session.get_one(Membership, (tenant_id, test_user_id))).role = MembershipRole.ORGA
        await session.commit()
    return _Packed(tenant_id, ids | {f"stat:{k}": v for k, v in sheet.ids.items()})


async def test_the_weight_recipe_adds_up_on_every_read_path(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    packed = await _packed(client, test_user_id)
    t, ids = packed.tenant_id, packed.ids
    base = f"/tenants/{t}/item-instances"

    backpack = await _stats(client, t, ids["backpack"])
    assert (backpack["contents_weight"], backpack["weight"]) == (25, 27)
    assert (await _stats(client, t, ids["pouch"]))["weight"] == 4
    # An unweighed torch has no weight of its own, and counts as 0 above.
    assert "weight" not in await _stats(client, t, ids["torch"])
    # What Hero carries in hand: the Backpack, contents and all.
    assert (await _stats(client, t, ids["hero"]))["carried_weight"] == 27

    detail = await client.get(f"{base}/{ids['backpack']}")
    by_slug = await client.get(f"{base}/by-slug/pack")
    listed = await client.get(base, params={"size": 100})
    owned = await client.get(f"{base}/owned-by/{ids['hero']}")
    held = await client.get(f"{base}/held-by/{ids['hero']}")
    crate = await client.get(f"/tenants/{t}/items/{ids['crate']}")
    catalog = await client.get(f"/tenants/{t}/items", params={"size": 100})
    renamed = await client.patch(f"{base}/{ids['pouch']}", json={"name": "Belt pouch"})

    assert detail.json()["weight"] == 27
    assert by_slug.json()["weight"] == 27
    assert {i["title"]: i["weight"] for i in listed.json()["items"]}["Backpack"] == 27
    owned_items = [i for g in owned.json()["groups"] for i in g["item_instances"]]
    assert {i["title"]: i["weight"] for i in owned_items}["Backpack"] == 27
    held_items = {
        i["title"]: i["weight"] for g in held.json()["groups"] for i in g["item_instances"]
    }
    assert (held_items["Backpack"], held_items["Arrows"], held_items["Torch"]) == (27, 1, None)
    assert crate.json()["weight"] == 13
    assert {i["title"]: i["weight"] for i in catalog.json()["items"]}["Crate"] == 13
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["weight"] == 4
    await delete_tenant(t)


async def test_a_containment_cycle_leaves_its_weights_without_a_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The Backpack slipped inside its own Pouch: neither has a weight. Hero
    now carries only the Rope, which still weighs 1."""
    packed = await _packed(client, test_user_id)
    t, ids = packed.tenant_id, packed.ids
    async with admin_session_factory() as session:
        (await session.get_one(Containment, ids["backpack"])).parent_entity_id = ids["pouch"]
        (await session.get_one(Containment, ids["rope"])).parent_entity_id = ids["hero"]
        await session.commit()

    for name in ("backpack", "pouch"):
        stats = await _stats(client, t, ids[name])
        assert "weight" not in stats and "contents_weight" not in stats, name
    assert (await _stats(client, t, ids["rope"]))["weight"] == 1
    assert (await _stats(client, t, ids["hero"]))["carried_weight"] == 1
    await delete_tenant(t)


async def test_contents_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        weight=StatValueType.FLOAT,
        count=StatValueType.INT,
        total=StatValueType.INT,
        label=StatValueType.TEXT,
    )
    async with admin_session_factory() as session:
        box = Entity(tenant_id=tenant_id, name="Box")
        session.add(box)
        await session.commit()
    url = sheet.formula_url(box.id, "total")

    cases = {
        "a text source": (url, _contents(sheet["label"])),
        "a text target": (sheet.formula_url(box.id, "label"), _contents(sheet["count"])),
        "an int target over a float": (url, _contents(sheet["weight"])),
    }
    statuses = {label: (await client.put(u, json=b)).status_code for label, (u, b) in cases.items()}
    # Reading its own stat is reading what's inside, not itself.
    own = await client.put(sheet.formula_url(box.id, "weight"), json=_contents(sheet["weight"]))
    ints = await client.put(url, json=_contents(sheet["count"]))

    assert statuses == dict.fromkeys(cases, 422)
    assert own.status_code == 200, own.text
    assert ints.status_code == 200, ints.text
    await delete_tenant(tenant_id)


async def test_preview_dependents_and_kind_changes_know_contents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    packed = await _packed(client, test_user_id)
    t, ids = packed.tenant_id, packed.ids
    own_weight, weight = ids["stat:own_weight"], ids["stat:weight"]
    url = f"/tenants/{t}/entities/{ids['backpack']}/computed-stats/{ids['stat:carried_weight']}"

    # What the Backpack's own weights inside add up to, unsaved: 1 + 20 + 1.
    preview = await client.post(f"{url}/preview", json={"formula": _contents(own_weight)})
    dependents = await client.get(f"/tenants/{t}/stat-definitions/{weight}/dependents")
    saved = await client.put(url, json=_contents(own_weight))
    replaced = await client.put(
        url,
        json={"kind": "linear", "source_stat_definition_id": str(own_weight), "multiplier": 2},
        headers={"If-Match": saved.headers["ETag"]},
    )

    assert preview.status_code == 200, preview.text
    assert (preview.json()["value"], preview.json()["inputs"]) == (22, [])
    assert sorted(
        (d["entity_id"], d["kind"]) for d in dependents.json() if d["kind"] == "contents"
    ) == sorted([(str(ids["gear"]), "contents"), (str(ids["hero"]), "contents")])
    assert replaced.status_code == 200, replaced.text
    async with admin_session_factory() as session:
        left = await session.scalar(
            select(ComputedStatContents.entity_id).where(
                ComputedStatContents.entity_id == ids["backpack"]
            )
        )
    assert left is None
    await delete_tenant(t)


async def test_computed_stat_contents_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(tenant_id, weight=StatValueType.INT, total=StatValueType.INT)
        async with admin_session_factory() as session:
            box = Entity(tenant_id=tenant_id, name="Box")
            session.add(box)
            await session.commit()
        await _put(client, sheet.formula_url(box.id, "total"), _contents(sheet["weight"]))
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                tenants = (
                    (await conn.execute(text("SELECT tenant_id FROM computed_stat_contents")))
                    .scalars()
                    .all()
                )
                assert tenants == [tenant_id]
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
