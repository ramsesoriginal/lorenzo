"""ADR 0104: computed stats through the real API - resolution through the
prototype chain, every Python reader, the write-time checks, preview, the
dependents lookup, and RLS on the new tables.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.db import engine
from lorenzo_api.models import (
    AuditLog,
    Entity,
    EntityPrototype,
    EntityStat,
    Item,
    Membership,
    Player,
    StatDefinition,
    StatGroup,
    StatValueType,
)

MODIFIER_FORMULA = {
    "kind": "linear",
    "multiplier": 0.5,
    "offset": -5,
    "round_mode": "floor",
}


class Sheet:
    """A tenant with an `abilities` group and a few stat definitions."""

    def __init__(self, tenant_id: uuid.UUID, ids: dict[str, uuid.UUID]) -> None:
        self.tenant_id = tenant_id
        self.ids = ids

    def __getitem__(self, name: str) -> uuid.UUID:
        return self.ids[name]

    def formula_url(self, entity_id: uuid.UUID, stat: str) -> str:
        return f"/tenants/{self.tenant_id}/entities/{entity_id}/computed-stats/{self[stat]}"


async def _sheet(tenant_id: uuid.UUID, **stats: StatValueType) -> Sheet:
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="abilities")
        session.add(group)
        await session.flush()
        ids = {}
        for name, value_type in stats.items():
            definition = StatDefinition(
                tenant_id=tenant_id, stat_group_id=group.id, name=name, value_type=value_type
            )
            session.add(definition)
            await session.flush()
            ids[name] = definition.id
        await session.commit()
    return Sheet(tenant_id, ids)


async def _entity(
    tenant_id: uuid.UUID,
    name: str,
    *,
    prototype: uuid.UUID | None = None,
    item: bool = False,
    stats: dict[uuid.UUID, int] | None = None,
) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if item:
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        if prototype is not None:
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=prototype, tenant_id=tenant_id)
            )
        for definition_id, value in (stats or {}).items():
            session.add(
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant_id,
                    value_int=value,
                )
            )
        await session.commit()
        return entity.id


async def _stats(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> dict:
    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200, response.text
    return {s["name"]: s["value"] for s in response.json()["stats"]}


async def _put(client: AsyncClient, url: str, body: dict, **headers: str) -> dict:
    response = await client.put(url, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- resolution --------------------------------------------------------------


async def test_prototype_formula_evaluates_against_each_instance(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The fighter prototype holds the modifier formula; each instance's
    own strength feeds it (ADR 0104) - with floor, 9 gives -1, not 0."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, strength_modifier=StatValueType.INT)
    fighter = await _entity(tenant_id, "Fighter")
    await _put(
        client,
        sheet.formula_url(fighter, "strength_modifier"),
        {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )
    weak = await _entity(tenant_id, "Weak", prototype=fighter, stats={sheet["strength"]: 9})
    strong = await _entity(tenant_id, "Strong", prototype=fighter, stats={sheet["strength"]: 18})

    assert await _stats(client, tenant_id, weak) == {"strength": 9, "strength_modifier": -1}
    assert await _stats(client, tenant_id, strong) == {"strength": 18, "strength_modifier": 4}
    # The prototype itself has no strength, so no modifier either.
    assert await _stats(client, tenant_id, fighter) == {}
    await delete_tenant(tenant_id)


async def test_a_nearer_direct_value_beats_an_inherited_formula(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, strength_modifier=StatValueType.INT)
    fighter = await _entity(tenant_id, "Fighter")
    await _put(
        client,
        sheet.formula_url(fighter, "strength_modifier"),
        {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )
    cursed = await _entity(
        tenant_id,
        "Cursed",
        prototype=fighter,
        stats={sheet["strength"]: 18, sheet["strength_modifier"]: -3},
    )

    assert (await _stats(client, tenant_id, cursed))["strength_modifier"] == -3
    await delete_tenant(tenant_id)


async def test_named_item_column_picks_up_a_computed_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """`weight` is a named v_item column; SQL can't evaluate the formula,
    so ItemOut fills it from the Python pass (ADR 0104)."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, weight_oz=StatValueType.INT, weight=StatValueType.INT)
    item = await _entity(tenant_id, "Anvil", item=True, stats={sheet["weight_oz"]: 1600})
    await _put(
        client,
        sheet.formula_url(item, "weight"),
        {
            "kind": "linear",
            "source_stat_definition_id": str(sheet["weight_oz"]),
            "multiplier": 0.0625,
            "round_mode": "round",
        },
    )

    response = await client.get(f"/tenants/{tenant_id}/items/{item}")

    assert response.status_code == 200, response.text
    assert response.json()["weight"] == 100
    await delete_tenant(tenant_id)


async def test_comparison_into_an_enum_stat(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, weight=StatValueType.INT)
    created = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={
            "name": "weight_class",
            "stat_group_id": str(
                (
                    await client.get(f"/tenants/{tenant_id}/stat-definitions/{sheet['weight']}")
                ).json()["stat_group_id"]
            ),
            "value_type": "enum",
            "enum_values": ["light", "heavy"],
        },
    )
    sheet.ids["weight_class"] = uuid.UUID(created.json()["id"])
    crate = await _entity(tenant_id, "Crate", stats={sheet["weight"]: 80})
    url = sheet.formula_url(crate, "weight_class")
    body = {
        "kind": "comparison",
        "left_stat_definition_id": str(sheet["weight"]),
        "comparator": "gt",
        "right_constant": 50,
        "true_value": "heavy",
        "false_value": "light",
    }

    not_allowed = await client.put(url, json={**body, "true_value": "huge"})
    await _put(client, url, body)

    assert not_allowed.status_code == 422
    assert (await _stats(client, tenant_id, crate))["weight_class"] == "heavy"
    await delete_tenant(tenant_id)


# --- write-time checks -------------------------------------------------------


async def test_formula_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        modifier=StatValueType.INT,
        name=StatValueType.TEXT,
        heavy=StatValueType.BOOL,
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "modifier")
    linear = {"kind": "linear", "source_stat_definition_id": str(sheet["strength"])}

    cases = {
        "int target without rounding": (url, {**linear, "multiplier": 0.5}),
        "text source": (
            url,
            {**linear, "source_stat_definition_id": str(sheet["name"]), "multiplier": 1},
        ),
        "unknown source": (
            url,
            {**linear, "source_stat_definition_id": str(uuid.uuid4()), "multiplier": 1},
        ),
        "reads itself": (
            url,
            {
                **linear,
                "source_stat_definition_id": str(sheet["modifier"]),
                "multiplier": 1,
                "round_mode": "floor",
            },
        ),
        "bool target with result values": (
            sheet.formula_url(entity, "heavy"),
            {
                "kind": "comparison",
                "left_stat_definition_id": str(sheet["strength"]),
                "comparator": "gt",
                "right_constant": 10,
                "true_value": "yes",
                "false_value": "no",
            },
        ),
        "text target without result values": (
            sheet.formula_url(entity, "name"),
            {
                "kind": "comparison",
                "left_stat_definition_id": str(sheet["strength"]),
                "comparator": "gt",
                "right_constant": 10,
            },
        ),
    }
    statuses = {label: (await client.put(u, json=b)).status_code for label, (u, b) in cases.items()}
    neither_right_side = await client.put(
        sheet.formula_url(entity, "heavy"),
        json={
            "kind": "comparison",
            "left_stat_definition_id": str(sheet["strength"]),
            "comparator": "gt",
        },
    )

    assert statuses == dict.fromkeys(cases, 422)
    assert neither_right_side.status_code == 422
    await delete_tenant(tenant_id)


async def test_formula_and_direct_value_exclude_each_other(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        modifier=StatValueType.INT,
        strong=StatValueType.BOOL,
    )
    direct = await _entity(tenant_id, "Direct", stats={sheet["modifier"]: 1})
    computed = await _entity(tenant_id, "Computed")
    modifier = {
        **MODIFIER_FORMULA,
        "source_stat_definition_id": str(sheet["strength"]),
    }
    strong = {
        "kind": "comparison",
        "left_stat_definition_id": str(sheet["strength"]),
        "comparator": "ge",
        "right_constant": 15,
    }
    await _put(client, sheet.formula_url(computed, "modifier"), modifier)
    await _put(client, sheet.formula_url(computed, "strong"), strong)

    formula_over_value = await client.put(sheet.formula_url(direct, "modifier"), json=modifier)
    value_over_formula = await client.put(
        f"/tenants/{tenant_id}/entities/{computed}/stats/{sheet['modifier']}", json={"value": 2}
    )
    tag_over_formula = await client.put(
        f"/tenants/{tenant_id}/entities/{computed}/tags/{sheet['strong']}"
    )

    assert formula_over_value.status_code == 409
    assert value_over_formula.status_code == 409
    assert tag_over_formula.status_code == 409
    await delete_tenant(tenant_id)


async def test_cycles_are_rejected_across_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Tenant-wide, definition-level (ADR 0104): b-from-a on one entity and
    a-from-b on another would loop on any entity inheriting both."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, b=StatValueType.INT, c=StatValueType.INT)
    one = await _entity(tenant_id, "One")
    two = await _entity(tenant_id, "Two")

    def linear(source: str) -> dict:
        return {
            "kind": "linear",
            "source_stat_definition_id": str(sheet[source]),
            "multiplier": 1,
            "round_mode": "floor",
        }

    await _put(client, sheet.formula_url(one, "b"), linear("a"))
    await _put(client, sheet.formula_url(one, "c"), linear("b"))
    loop = await client.put(sheet.formula_url(two, "a"), json=linear("c"))
    preview = await client.post(
        f"{sheet.formula_url(two, 'a')}/preview", json={"formula": linear("c")}
    )
    # Replacing a formula doesn't count its own old edges.
    replaced = await client.put(sheet.formula_url(one, "b"), json=linear("c"))

    assert loop.status_code == 422
    assert loop.json()["detail"] == "Formula dependencies would loop: a -> c -> b -> a"
    assert preview.status_code == 422
    assert replaced.status_code == 422  # b from c, c from b: still a loop
    await delete_tenant(tenant_id)


async def test_replace_with_if_match_and_kind_change_then_delete(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, score=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 12})
    url = sheet.formula_url(entity, "score")
    first = await client.put(
        url, json={**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])}
    )
    etag = first.headers["etag"]

    stale = await client.put(
        url,
        json={**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
        headers={"If-Match": 'W/"2000-01-01T00:00:00+00:00"'},
    )
    doubled = await _put(
        client,
        url,
        {
            "kind": "linear",
            "source_stat_definition_id": str(sheet["strength"]),
            "multiplier": 2,
            "round_mode": "floor",
        },
        **{"If-Match": etag},
    )
    listed = await client.get(f"/tenants/{tenant_id}/entities/{entity}/computed-stats")
    value_before_delete = (await _stats(client, tenant_id, entity))["score"]
    old_etag_delete = await client.delete(url, headers={"If-Match": etag})
    deleted = await client.delete(url)
    deleted_again = await client.delete(url)

    assert stale.status_code == 412
    assert doubled["formula"]["multiplier"] == "2"
    assert [f["stat_definition_id"] for f in listed.json()] == [str(sheet["score"])]
    assert value_before_delete == 24
    assert old_etag_delete.status_code == 412
    assert deleted.status_code == 204
    assert deleted_again.status_code == 404
    assert "score" not in await _stats(client, tenant_id, entity)
    async with admin_session_factory() as session:
        actions = (
            (
                await session.execute(
                    select(AuditLog.action)
                    .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("computed_stat.%"))
                    .order_by(AuditLog.created_at)
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["computed_stat.set", "computed_stat.set", "computed_stat.deleted"]
    await delete_tenant(tenant_id)


async def test_replace_can_change_the_formula_kind(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, strong=StatValueType.BOOL)
    entity = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 16})
    url = sheet.formula_url(entity, "strong")
    comparison = {
        "kind": "comparison",
        "left_stat_definition_id": str(sheet["strength"]),
        "comparator": "ge",
        "right_constant": 15,
    }
    await _put(client, url, comparison)
    # A bool target can't hold a linear formula - the kind check still runs
    # on replace, and the old formula survives the failed write.
    rejected = await client.put(
        url,
        json={
            "kind": "linear",
            "source_stat_definition_id": str(sheet["strength"]),
            "multiplier": 1,
        },
    )
    flipped = await _put(client, url, {**comparison, "comparator": "lt"})

    assert rejected.status_code == 422
    assert flipped["formula"]["kind"] == "comparison"
    assert (await _stats(client, tenant_id, entity))["strong"] is False
    await delete_tenant(tenant_id)


async def test_deleting_a_formula_removes_its_concrete_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The two kinds never share a valid target type (linear produces a
    number, comparison a bool/text/enum), so a kind swap on one stat can't
    happen through the API; what can is a formula deleted and another kind
    added elsewhere. The deleted formula's linear row must go with it."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, strength=StatValueType.INT, label=StatValueType.TEXT, score=StatValueType.INT
    )
    entity = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 16})
    await _put(
        client,
        sheet.formula_url(entity, "score"),
        {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )
    await client.delete(sheet.formula_url(entity, "score"))
    await _put(
        client,
        sheet.formula_url(entity, "label"),
        {
            "kind": "comparison",
            "left_stat_definition_id": str(sheet["strength"]),
            "comparator": "gt",
            "right_constant": 10,
            "true_value": "strong",
            "false_value": "weak",
        },
    )
    async with admin_session_factory() as session:
        linear_rows = (
            await session.execute(
                text("SELECT count(*) FROM computed_stat_linear WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
        ).scalar_one()

    assert linear_rows == 0
    assert (await _stats(client, tenant_id, entity))["label"] == "strong"
    await delete_tenant(tenant_id)


# --- preview and dependents --------------------------------------------------


async def test_preview_evaluates_without_saving(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        modifier=StatValueType.INT,
        nothing=StatValueType.INT,
    )
    entity = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 9})
    url = sheet.formula_url(entity, "modifier")
    candidate = {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])}

    unsaved = await client.post(f"{url}/preview", json={"formula": candidate})
    listed = await client.get(f"/tenants/{tenant_id}/entities/{entity}/computed-stats")
    unset = await client.post(f"{url}/preview")
    direct = await client.post(f"{sheet.formula_url(entity, 'strength')}/preview")
    await _put(client, url, candidate)
    saved = await client.post(f"{url}/preview")

    assert unsaved.status_code == 200, unsaved.text
    assert unsaved.json() == {
        "stat_definition_id": str(sheet["modifier"]),
        "value": -1,
        "source": "computed",
        "inputs": [{"stat_definition_id": str(sheet["strength"]), "name": "strength", "value": 9}],
    }
    assert listed.json() == []
    assert unset.json()["source"] == "unset"
    assert direct.json()["source"] == "direct"
    assert direct.json()["value"] == 9
    assert saved.json()["value"] == -1
    assert saved.json()["source"] == "computed"
    await delete_tenant(tenant_id)


async def test_dependents_lists_every_formula_reading_a_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        modifier=StatValueType.INT,
        strong=StatValueType.BOOL,
    )
    one = await _entity(tenant_id, "One")
    two = await _entity(tenant_id, "Two")
    await _put(
        client,
        sheet.formula_url(one, "modifier"),
        {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )
    await _put(
        client,
        sheet.formula_url(two, "strong"),
        {
            "kind": "comparison",
            "left_stat_definition_id": str(sheet["modifier"]),
            "comparator": "lt",
            "right_stat_definition_id": str(sheet["strength"]),
        },
    )

    response = await client.get(
        f"/tenants/{tenant_id}/stat-definitions/{sheet['strength']}/dependents"
    )

    assert response.status_code == 200
    assert sorted((d["entity_id"], d["kind"]) for d in response.json()) == sorted(
        [(str(one), "linear"), (str(two), "comparison")]
    )
    await delete_tenant(tenant_id)


# --- authorization and isolation ---------------------------------------------


async def test_formulas_are_tenant_admin_only(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, modifier=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Membership, (tenant_id, test_user_id)))
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(
        sheet.formula_url(entity, "modifier"),
        json={**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )

    assert response.status_code == 404  # get_tenant_context: no Membership, no tenant
    await delete_tenant(tenant_id)


async def test_computed_stat_tables_are_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(tenant_id, strength=StatValueType.INT, modifier=StatValueType.INT)
        entity = await _entity(tenant_id, "Hero")
        await _put(
            client,
            sheet.formula_url(entity, "modifier"),
            {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
        )
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                for table in ("computed_stat", "computed_stat_linear"):
                    tenants = (
                        (await conn.execute(text(f"SELECT tenant_id FROM {table}"))).scalars().all()
                    )
                    assert tenants == [tenant_id]
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
