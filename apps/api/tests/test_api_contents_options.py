"""ADR 0447: the options of a contents formula (`aggregate`, `only_active`, `only_kind`, `where`,
`if_none`) and the `active` switch of an item instance, through the real API - armour class from
what is worn, a dexterity cap, a count of what needs attunement, the stack count, the write-time
checks, preview, explanation, dependents, a stat that is deleted while one reads it, and how an
instance starts and keeps its switch.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from test_api_computed_stats import _put, _sheet, _stats

from lorenzo_api.models import (
    ComputedStatContents,
    Containment,
    Entity,
    EntityStat,
    Item,
    ItemInstance,
    StatValueType,
)


def _contents(
    source: uuid.UUID | None = None,
    *,
    aggregate: str = "sum",
    only_active: bool = False,
    only_kind: str | None = None,
    where: uuid.UUID | None = None,
    if_none: float | None = None,
) -> dict:
    return {
        "kind": "contents",
        "source_stat_definition_id": None if source is None else str(source),
        "aggregate": aggregate,
        "only_active": only_active,
        "only_kind": only_kind,
        "where_stat_definition_id": None if where is None else str(where),
        "if_none": if_none,
    }


async def _held(
    tenant_id: uuid.UUID,
    holder: uuid.UUID,
    name: str,
    *,
    stats: dict[uuid.UUID, int | bool] | None = None,
    active: bool = True,
    quantity: int = 1,
    instance: bool = True,
) -> uuid.UUID:
    """A thing inside `holder`: an item instance with its switch as given, or a plain item."""
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if instance:
            session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id, active=active))
        else:
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        for stat, value in (stats or {}).items():
            session.add(
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=stat,
                    tenant_id=tenant_id,
                    value_int=None if isinstance(value, bool) else value,
                    value_bool=value if isinstance(value, bool) else None,
                )
            )
        session.add(
            Containment(
                child_entity_id=entity.id,
                parent_entity_id=holder,
                tenant_id=tenant_id,
                quantity=quantity,
            )
        )
        await session.commit()
        return entity.id


async def _worn(client: AsyncClient, test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """Hero wearing chain mail (armour 16, cap 2), leather (11, cap 5, switched off), a shield
    (2, no cap) and a stack of 3 arrows (1 each); a ring that needs attunement and is on, and a
    cloak that does too and is off; and a plain item with an armour of 100 that is not an
    instance."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        armor_value=StatValueType.INT,
        dex_cap=StatValueType.INT,
        attunes=StatValueType.BOOL,
        total=StatValueType.INT,
        best=StatValueType.INT,
        cap=StatValueType.INT,
        attuned=StatValueType.INT,
        weight_float=StatValueType.FLOAT,
    )
    async with admin_session_factory() as session:
        hero = (await make_being(session, tenant_id=tenant_id, name="Hero")).entity_id
        await session.commit()
    armor, cap, attunes = sheet["armor_value"], sheet["dex_cap"], sheet["attunes"]
    await _held(tenant_id, hero, "Chain mail", stats={armor: 16, cap: 2})
    await _held(tenant_id, hero, "Leather", stats={armor: 11, cap: 5}, active=False)
    await _held(tenant_id, hero, "Shield", stats={armor: 2})
    await _held(tenant_id, hero, "Arrows", stats={armor: 1}, quantity=3)
    await _held(tenant_id, hero, "Ring", stats={attunes: True})
    await _held(tenant_id, hero, "Cloak", stats={attunes: True}, active=False)
    await _held(tenant_id, hero, "Crate", stats={armor: 100}, instance=False)
    return tenant_id, sheet, hero


async def _formula(
    client: AsyncClient, tenant_id: uuid.UUID, sheet, hero: uuid.UUID, stat: str, body: dict
) -> None:  # type: ignore[no-untyped-def]
    await _put(client, sheet.formula_url(hero, stat), body)


# --- the options ----------------------------------------------------------------------------


async def test_the_default_still_sums_every_thing_times_its_stack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(client, tenant_id, sheet, hero, "total", _contents(sheet["armor_value"]))

    stats = await _stats(client, tenant_id, hero)

    # 16 + 11 + 2 + 1 x 3 + the crate's 100: the formula of ADR 0127, as it was.
    assert stats["total"] == 132
    await delete_tenant(tenant_id)


async def test_only_active_skips_what_is_switched_off(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "total",
        _contents(sheet["armor_value"], only_active=True),
    )

    stats = await _stats(client, tenant_id, hero)

    # Leather is off; the crate is not an instance, has no switch and counts.
    assert stats["total"] == 121
    await delete_tenant(tenant_id)


async def test_only_kind_keeps_item_instances_alone(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "total",
        _contents(sheet["armor_value"], only_kind="item_instance", only_active=True),
    )

    assert (await _stats(client, tenant_id, hero))["total"] == 21
    await delete_tenant(tenant_id)


async def test_max_over_what_is_worn_with_a_value_for_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Armour class is the best of what is worn, and 10 for an unarmoured being."""
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "best",
        _contents(
            sheet["armor_value"],
            aggregate="max",
            only_active=True,
            only_kind="item_instance",
            if_none=10,
        ),
    )
    naked = await make_tenant(test_user_id)
    naked_sheet = await _sheet(naked, armor_value=StatValueType.INT, best=StatValueType.INT)
    async with admin_session_factory() as session:
        bare = (await make_being(session, tenant_id=naked, name="Bare")).entity_id
        await session.commit()
    await _formula(
        client,
        naked,
        naked_sheet,
        bare,
        "best",
        _contents(naked_sheet["armor_value"], aggregate="max", if_none=10),
    )

    assert (await _stats(client, tenant_id, hero))["best"] == 16
    assert (await _stats(client, naked, bare))["best"] == 10
    await delete_tenant(tenant_id)
    await delete_tenant(naked)


async def test_min_and_max_of_nothing_have_no_value_without_if_none(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "best",
        _contents(sheet["armor_value"], aggregate="max", only_kind="item_instance", where=None)
        | {"only_active": True},
    )
    # Nothing is both off and on: where a stat nobody has is true, nothing is taken.
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "cap",
        _contents(sheet["dex_cap"], aggregate="min", where=sheet["attunes"]),
    )

    stats = await _stats(client, tenant_id, hero)

    assert stats["best"] == 16
    # The ring and the cloak, which need attunement, carry no dex cap: nothing to take a min of.
    assert "cap" not in stats
    await delete_tenant(tenant_id)


async def test_min_takes_the_smallest_value_and_ignores_things_without_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "cap",
        _contents(sheet["dex_cap"], aggregate="min", only_active=True),
    )

    # Chain mail (2) and leather (5, switched off): the shield has no cap and is ignored.
    assert (await _stats(client, tenant_id, hero))["cap"] == 2
    await delete_tenant(tenant_id)


async def test_count_ignores_the_stat_and_the_stack_and_takes_a_where(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Attunement used: the things that are on and need attunement."""
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "attuned",
        _contents(aggregate="count", only_active=True, where=sheet["attunes"]),
    )

    stats = await _stats(client, tenant_id, hero)

    assert stats["attuned"] == 1
    await delete_tenant(tenant_id)


async def test_a_stack_multiplies_a_sum_and_not_a_min_a_max_or_a_count(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        weight=StatValueType.INT,
        summed=StatValueType.INT,
        biggest=StatValueType.INT,
        counted=StatValueType.INT,
    )
    async with admin_session_factory() as session:
        pack = (await make_being(session, tenant_id=tenant_id, name="Pack")).entity_id
        await session.commit()
    await _held(tenant_id, pack, "Rope", stats={sheet["weight"]: 2}, quantity=5)
    await _held(tenant_id, pack, "Torch", stats={sheet["weight"]: 1}, quantity=4)
    for stat, body in (
        ("summed", _contents(sheet["weight"])),
        ("biggest", _contents(sheet["weight"], aggregate="max")),
        ("counted", _contents(aggregate="count")),
    ):
        await _formula(client, tenant_id, sheet, pack, stat, body)

    stats = await _stats(client, tenant_id, pack)

    assert (stats["summed"], stats["biggest"], stats["counted"]) == (14, 2, 2)
    await delete_tenant(tenant_id)


# --- write-time checks ------------------------------------------------------------------------


async def test_contents_shape_and_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        armor_value=StatValueType.INT,
        speed=StatValueType.FLOAT,
        flag=StatValueType.BOOL,
        label=StatValueType.TEXT,
        total=StatValueType.INT,
        reach=StatValueType.FLOAT,
    )
    async with admin_session_factory() as session:
        pack = (await make_being(session, tenant_id=tenant_id, name="Pack")).entity_id
        await session.commit()
    url = sheet.formula_url(pack, "total")
    armor = sheet["armor_value"]

    cases = {
        "no stat for a sum": (url, _contents()),
        "no stat for a max": (url, _contents(aggregate="max")),
        "a text stat": (url, _contents(sheet["label"])),
        "an if_none for a sum": (url, _contents(armor, if_none=1)),
        "a fractional if_none for an int": (url, _contents(armor, aggregate="min", if_none=0.5)),
        "a float stat for an int": (url, _contents(sheet["speed"], aggregate="max")),
        "a where that is not a bool": (url, _contents(armor, where=armor)),
        "a text target": (
            sheet.formula_url(pack, "label"),
            _contents(armor, aggregate="max"),
        ),
        "an unknown kind": (url, _contents(armor, only_kind="character")),
        "an unknown aggregate": (url, _contents(armor, aggregate="median")),
    }
    statuses = {
        label: (await client.put(u, json=body)).status_code for label, (u, body) in cases.items()
    }
    counted = await client.put(url, json=_contents(aggregate="count"))
    float_target = await client.put(
        sheet.formula_url(pack, "reach"), json=_contents(sheet["speed"], aggregate="max")
    )

    assert statuses == dict.fromkeys(cases, 422)
    assert counted.status_code == 200, counted.text
    assert float_target.status_code == 200, float_target.text
    await delete_tenant(tenant_id)


async def test_a_stored_formula_keeps_its_default_options(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    saved = await client.put(
        sheet.formula_url(hero, "total"),
        json={"kind": "contents", "source_stat_definition_id": str(sheet["armor_value"])},
    )
    async with admin_session_factory() as session:
        row = (
            await session.execute(
                select(ComputedStatContents).where(ComputedStatContents.tenant_id == tenant_id)
            )
        ).scalar_one()

    assert saved.status_code == 200, saved.text
    assert saved.json()["formula"]["aggregate"] == "sum"
    assert saved.json()["formula"]["only_active"] is False
    assert (row.aggregate, row.only_active, row.only_kind, row.where_stat_definition_id) == (
        "sum",
        False,
        None,
        None,
    )
    await delete_tenant(tenant_id)


# --- preview, explanation, dependents, deleting a stat -------------------------------------------


async def test_preview_explanation_and_dependents_know_the_options(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    url = sheet.formula_url(hero, "attuned")
    formula = _contents(aggregate="count", only_active=True, where=sheet["attunes"])

    preview = await client.post(f"{url}/preview", json={"formula": formula})
    await _put(client, url, formula)
    explained = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['attuned']}/explanation"
    )
    dependents = await client.get(
        f"/tenants/{tenant_id}/stat-definitions/{sheet['attunes']}/dependents"
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 1
    assert explained.json()["value"] == 1
    # Of the seven things inside, one is on and needs attunement; the explanation says so.
    assert explained.json()["contents"] == {
        "source_stat_definition_id": None,
        "source_name": None,
        "things": 1,
    }
    assert dependents.json() == [
        {"entity_id": str(hero), "stat_definition_id": str(sheet["attuned"]), "kind": "contents"}
    ]
    await delete_tenant(tenant_id)


async def test_a_stat_a_contents_formula_filters_by_is_not_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "attuned",
        _contents(aggregate="count", where=sheet["attunes"]),
    )

    refused = await client.delete(f"/tenants/{tenant_id}/stat-definitions/{sheet['attunes']}")

    assert refused.status_code == 409
    await delete_tenant(tenant_id)


# --- the active switch ----------------------------------------------------------------------------


async def test_an_instance_is_active_by_default_and_its_holder_flips_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, hero = await _worn(client, test_user_id)
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=tenant_id)
        prototype = Entity(tenant_id=tenant_id, name="Plate")
        session.add(prototype)
        await session.flush()
        session.add(Item(entity_id=prototype.id, tenant_id=tenant_id))
        await session.commit()
        prototype_id = prototype.id
    created = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": str(prototype_id)}
    )
    instance = created.json()["entity_id"]
    await _formula(
        client,
        tenant_id,
        sheet,
        hero,
        "attuned",
        _contents(aggregate="count", only_active=True),
    )
    async with admin_session_factory() as session:
        session.add(
            Containment(
                child_entity_id=uuid.UUID(instance),
                parent_entity_id=hero,
                tenant_id=tenant_id,
                quantity=1,
            )
        )
        await session.commit()
    before = (await _stats(client, tenant_id, hero))["attuned"]

    off = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{instance}", json={"active": False}
    )
    after = (await _stats(client, tenant_id, hero))["attuned"]
    null = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{instance}", json={"active": None}
    )
    fetched = await client.get(f"/tenants/{tenant_id}/item-instances/{instance}")

    assert created.json()["active"] is True
    assert off.status_code == 200, off.text
    assert off.json()["active"] is False
    # The seven things already inside, minus Leather and Cloak; Plate went in on.
    assert (before, after) == (6, 5)
    assert null.status_code == 422
    assert fetched.json()["active"] is False
    await delete_tenant(tenant_id)


async def test_an_instance_starts_as_its_prototype_says_unless_told(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
    ring = await client.post(
        f"/tenants/{tenant_id}/items", json={"name": "Ring", "starts_inactive": True}
    )
    plain = await client.post(f"/tenants/{tenant_id}/items", json={"name": "Torch"})
    ring_id, plain_id = ring.json()["entity_id"], plain.json()["entity_id"]

    inactive = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": ring_id}
    )
    told = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": ring_id, "active": True}
    )
    active = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": plain_id}
    )
    switched = await client.patch(
        f"/tenants/{tenant_id}/items/{plain_id}", json={"starts_inactive": True}
    )
    after = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": plain_id}
    )

    assert ring.json()["starts_inactive"] is True and plain.json()["starts_inactive"] is False
    assert inactive.json()["active"] is False
    assert told.json()["active"] is True
    assert active.json()["active"] is True
    assert switched.status_code == 200, switched.text
    assert after.json()["active"] is False
    # An instance that already exists keeps its switch when the prototype's rule changes.
    kept = await client.get(f"/tenants/{tenant_id}/item-instances/{active.json()['entity_id']}")
    assert kept.json()["active"] is True
    await delete_tenant(tenant_id)
