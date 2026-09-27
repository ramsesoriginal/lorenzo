"""ADR 0129: binding, derived from where an item is and who owns it; what
it refuses; a GM's override and lifting a binding.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete, select
from test_api_held_by import _character

from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    ComputedStat,
    ComputedStatComparison,
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    GroupMember,
    Item,
    ItemInstance,
    Ownership,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
    User,
)


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    pia_user_id: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _scene(test_user_id: uuid.UUID, *, binding: bool = True) -> _Scene:
    """The caller plays Alice, a plain player; another player plays Pia, in
    the same campaign; the Company is both of them. Three catalog items bind:
    the Cursed one on equip, the Soulbound one on pickup, the Heirloom when
    owned. Alice has:

    - equipped: a Ring (Cursed), a stack of 5 Arrows (Soulbound), the
      Company's Banner (Heirloom), and a Backpack;
    - in the Backpack: a Blade (Soulbound) and Gloves (Cursed, not worn);
    - in no container: a Chest, holding an Amulet (Soulbound, not carried)
      and a Locket (Heirloom).

    Without `binding`, the tenant defines no such stat at all.
    """
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Table")
        await session.flush()
        pia_user = User(authgear_subject_id=f"pia-{uuid.uuid4()}")
        session.add(pia_user)
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        pia = await _character(session, tenant_id, campaign.id, pia_user.id, "Pia")
        company = Entity(tenant_id=tenant_id, name="The Company")
        session.add(company)
        await session.flush()
        session.add_all(
            GroupMember(group_entity_id=company.id, character_entity_id=m, tenant_id=tenant_id)
            for m in (alice, pia)
        )
        ids = {"alice": alice, "pia": pia, "company": company.id}

        group = StatGroup(tenant_id=tenant_id, name="rules")
        session.add(group)
        await session.flush()
        if binding:
            definition = StatDefinition(
                tenant_id=tenant_id,
                stat_group_id=group.id,
                name="binding",
                value_type=StatValueType.ENUM,
            )
            session.add(definition)
            await session.flush()
            ids["stat:binding"] = definition.id
            session.add_all(
                StatDefinitionEnumValue(
                    tenant_id=tenant_id, stat_definition_id=definition.id, value=value
                )
                for value in ("on_own", "on_pickup", "on_equip", "none")
            )

        async def prototype(name: str, value: str | None) -> uuid.UUID:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
            if value is not None and binding:
                session.add(
                    EntityStat(
                        entity_id=entity.id,
                        stat_definition_id=ids["stat:binding"],
                        tenant_id=tenant_id,
                        value_text=value,
                    )
                )
            await session.flush()
            return entity.id

        kinds = {
            "cursed": await prototype("Cursed", "on_equip"),
            "soulbound": await prototype("Soulbound", "on_pickup"),
            "heirloom": await prototype("Heirloom", "on_own"),
            "plain": await prototype("Plain", None),
        }

        async def thing(
            name: str,
            kind: str,
            inside: uuid.UUID | None,
            *,
            owner: uuid.UUID = alice,
            quantity: int = 1,
        ) -> uuid.UUID:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=kinds[kind], tenant_id=tenant_id)
            )
            session.add(
                Ownership(owned_entity_id=entity.id, owner_character_id=owner, tenant_id=tenant_id)
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

        ids["ring"] = await thing("Ring", "cursed", alice)
        ids["arrows"] = await thing("Arrows", "soulbound", alice, quantity=5)
        ids["banner"] = await thing("Banner", "heirloom", alice, owner=company.id)
        ids["backpack"] = await thing("Backpack", "plain", alice)
        ids["blade"] = await thing("Blade", "soulbound", ids["backpack"])
        ids["gloves"] = await thing("Gloves", "cursed", ids["backpack"])
        ids["chest"] = await thing("Chest", "plain", None)
        ids["amulet"] = await thing("Amulet", "soulbound", ids["chest"])
        ids["locket"] = await thing("Locket", "heirloom", ids["chest"])
        await session.commit()
    return _Scene(tenant_id, campaign.id, pia_user.id, ids)


async def _tear_down(scene: _Scene) -> None:
    await delete_tenant(scene.tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, scene.pia_user_id))
        await session.commit()


async def _gm(scene: _Scene, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(
                user_id=test_user_id, campaign_id=scene.campaign_id, tenant_id=scene.tenant_id
            )
        )
        await session.commit()


def _url(scene: _Scene, item: str, action: str = "") -> str:
    return f"/tenants/{scene.tenant_id}/item-instances/{scene.ids[item]}{action}"


def _into(client: AsyncClient, scene: _Scene, item: str, container: str, **extra: object):
    return client.put(
        _url(scene, item, "/container"),
        json={"container_entity_id": str(scene.ids[container]), **extra},
    )


def _give(client: AsyncClient, scene: _Scene, item: str, to: str, **extra: object):
    return client.put(
        _url(scene, item, "/owner"), json={"owner_character_id": str(scene.ids[to]), **extra}
    )


async def _bound(client: AsyncClient, scene: _Scene, item: str) -> bool:
    response = await client.get(_url(scene, item))
    assert response.status_code == 200, response.text
    bound = response.json()["bound"]
    assert isinstance(bound, bool)
    return bound


async def _parent(scene: _Scene, item: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        row = await session.get(Containment, scene.ids[item])
        return row.parent_entity_id if row else None


async def _owner(scene: _Scene, item: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        row = await session.get(Ownership, scene.ids[item])
        return row.owner_character_id if row else None


async def test_bound_follows_where_it_is_and_who_owns_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        # Equipped, carried, owned by a being; not worn, not carried, a group's.
        expected = {
            "ring": True,
            "arrows": True,
            "blade": True,
            "locket": True,
            "gloves": False,
            "amulet": False,
            "banner": False,
            "backpack": False,
        }
        assert {item: await _bound(client, scene, item) for item in expected} == expected

        # Every listing carries it too.
        board = await client.get(
            f"/tenants/{scene.tenant_id}/item-instances/held-by/{scene.ids['alice']}"
        )
        assert board.status_code == 200, board.text
        listed = {
            item["title"]: item["bound"]
            for group in board.json()["groups"]
            for item in group["item_instances"]
        }
        assert listed["Blade"] is True
        assert listed["Gloves"] is False

        # Putting the Gloves on binds them; picking up the Amulet binds it.
        worn = await _into(client, scene, "gloves", "alice")
        assert worn.status_code == 200, worn.text
        assert worn.json()["bound"] is True
        picked = await _into(client, scene, "amulet", "backpack")
        assert picked.json()["bound"] is True
    finally:
        await _tear_down(scene)


async def test_a_bound_items_owner_cant_change(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        refused = await _give(client, scene, "ring", "pia")
        assert refused.status_code == 409, refused.text
        body = refused.json()
        assert body["type"] == "item-bound"
        assert (
            body["detail"] == "Ring is bound to Alice (binds on equip), so it can't change hands."
        )
        assert body["item"] == {"id": str(scene.ids["ring"]), "name": "Ring"}
        assert body["binding"] == "on_equip"
        assert body["owner"] == {"id": str(scene.ids["alice"]), "name": "Alice"}

        cleared = await client.delete(_url(scene, "locket", "/owner"))
        assert cleared.status_code == 409, cleared.text
        assert "binds when owned" in cleared.json()["detail"]

        split = await client.post(
            _url(scene, "arrows", "/split"),
            json={"quantity": 2, "owner_character_id": str(scene.ids["pia"])},
        )
        assert split.status_code == 409, split.text

        results = await client.post(
            f"/tenants/{scene.tenant_id}/item-instances/bulk-assign",
            json=[
                {"entity_id": str(scene.ids["blade"]), "owner_character_id": str(scene.ids["pia"])},
                {
                    "entity_id": str(scene.ids["amulet"]),
                    "owner_character_id": str(scene.ids["pia"]),
                },
            ],
        )
        assert results.status_code == 200, results.text
        blade, amulet = results.json()
        assert blade["status"] == "error"
        assert blade["problem"]["type"] == "item-bound"
        assert amulet["status"] == "ok"

        # Nothing bound changed hands; a group's heirloom never binds.
        assert await _owner(scene, "ring") == scene.ids["alice"]
        assert await _owner(scene, "locket") == scene.ids["alice"]
        assert (await _give(client, scene, "banner", "pia")).status_code == 200
    finally:
        await _tear_down(scene)


async def test_a_bound_thing_cant_leave_what_binds_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        worn = await _into(client, scene, "ring", "backpack")
        assert worn.status_code == 409, worn.text
        assert (
            worn.json()["detail"]
            == "Ring is bound to Alice (binds on equip), so it can't be taken off Alice."
        )
        off = await client.delete(_url(scene, "ring", "/container"))
        assert off.status_code == 409, off.text

        # Within what Alice carries, the Blade moves freely; out of it, not.
        assert (await _into(client, scene, "blade", "alice")).status_code == 200
        assert (await _into(client, scene, "blade", "backpack")).status_code == 200
        away = await _into(client, scene, "blade", "chest")
        assert away.status_code == 409, away.text
        assert away.json()["detail"] == (
            "Blade is bound to Alice (binds on pickup), so it can't leave what Alice carries."
        )

        # A container checks what's inside it, and names it.
        packed = await _into(client, scene, "backpack", "chest")
        assert packed.status_code == 409, packed.text
        assert packed.json()["item"]["name"] == "Blade"
        handed = await _give(client, scene, "backpack", "pia", move_to_owner=True)
        assert handed.status_code == 409, handed.text
        assert handed.json()["item"]["name"] == "Blade"
        assert await _owner(scene, "backpack") == scene.ids["alice"]

        # The Locket moves until it's carried, then stays.
        assert (await _into(client, scene, "locket", "pia")).status_code == 200
        assert (await _into(client, scene, "locket", "alice")).status_code == 200
        assert (await _into(client, scene, "locket", "chest")).status_code == 409

        results = await client.post(
            f"/tenants/{scene.tenant_id}/item-instances/bulk-move",
            json={
                "to_container_entity_id": str(scene.ids["chest"]),
                "items": [{"entity_id": str(scene.ids[i])} for i in ("blade", "gloves")],
            },
        )
        assert [r["status"] for r in results.json()] == ["error", "ok"]
        assert results.json()[0]["problem"]["type"] == "item-bound"
        assert await _parent(scene, "blade") == scene.ids["backpack"]
    finally:
        await _tear_down(scene)


async def test_what_binding_never_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    scene = await _scene(test_user_id)
    try:
        # Splitting in place keeps both halves where binding holds them.
        split = await client.post(_url(scene, "arrows", "/split"), json={"quantity": 2})
        assert split.status_code == 201, split.text
        assert split.json()["bound"] is True
        assert await _bound(client, scene, "arrows")

        renamed = await client.patch(_url(scene, "ring"), json={"name": "Ring of Embers"})
        assert renamed.status_code == 200, renamed.text

        # Deleting the Backpack keeps the Blade where Alice carries it.
        assert (await client.delete(_url(scene, "backpack"))).status_code == 204
        assert await _parent(scene, "blade") == scene.ids["alice"]
        assert await _bound(client, scene, "blade")

        # A potion can be drunk.
        assert (await client.delete(_url(scene, "ring"))).status_code == 204
    finally:
        await _tear_down(scene)


async def test_giving_whats_inside_keeps_what_is_bound(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        response = await client.post(
            _url(scene, "backpack", "/give-contents"),
            json={"owner_character_id": str(scene.ids["pia"])},
        )
        assert response.status_code == 200, response.text
        outcome = {
            r["title"]: (r["status"], (r.get("problem") or {}).get("type")) for r in response.json()
        }
        assert outcome == {"Blade": ("kept", "item-bound"), "Gloves": ("ok", None)}
    finally:
        await _tear_down(scene)


async def test_a_gm_moves_anyway_and_lifts_a_binding(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        as_player = await _give(client, scene, "ring", "pia", override=True)
        assert as_player.status_code == 403, as_player.text
        assert as_player.json()["type"] == "override-forbidden"
        lifting = await _into(client, scene, "blade", "chest", lift_binding=True)
        assert lifting.status_code == 403, lifting.text
        assert "lift its binding" in lifting.json()["detail"]
        off = await client.delete(_url(scene, "locket", "/owner"), params={"override": "true"})
        assert off.status_code == 403, off.text

        await _gm(scene, test_user_id)
        given = await _give(client, scene, "ring", "pia", override=True)
        assert given.status_code == 200, given.text
        # Pia's now, and in Alice's hands, so it binds no one - for now.
        assert given.json()["bound"] is False

        lifted = await _into(client, scene, "blade", "chest", lift_binding=True)
        assert lifted.status_code == 200, lifted.text
        back = await _into(client, scene, "blade", "alice")
        assert back.json()["bound"] is False

        taken = await client.delete(
            _url(scene, "arrows", "/owner"), params={"lift_binding": "true"}
        )
        assert taken.status_code == 200, taken.text

        # A lifted stack's halves both stay lifted.
        split = await client.post(_url(scene, "arrows", "/split"), json={"quantity": 2})
        assert split.status_code == 201, split.text

        moved = await client.post(
            f"/tenants/{scene.tenant_id}/item-instances/bulk-move",
            json={
                "to_container_entity_id": str(scene.ids["chest"]),
                "items": [{"entity_id": str(scene.ids["gloves"])}],
                "override": True,
            },
        )
        assert moved.json()[0]["status"] == "ok"

        async with admin_session_factory() as session:
            own = {
                row.entity_id: row.value_text
                for row in await session.scalars(
                    select(EntityStat).where(
                        EntityStat.stat_definition_id == scene.ids["stat:binding"]
                    )
                )
            }
            details = list(
                await session.scalars(
                    select(AuditLog.detail)
                    .where(AuditLog.tenant_id == scene.tenant_id)
                    .order_by(AuditLog.created_at)
                )
            )
        assert own[scene.ids["blade"]] == "none"
        assert own[scene.ids["arrows"]] == "none"
        assert own[uuid.UUID(split.json()["entity_id"])] == "none"
        assert f"owner={scene.ids['alice']}; overridden" not in details
        assert f"owner={scene.ids['pia']}; overridden" in details
        assert f"container={scene.ids['chest']}; binding lifted" in details
        assert f"owner={scene.ids['alice']}; binding lifted" in details
    finally:
        await _tear_down(scene)


async def test_what_a_binding_can_be_lifted_to(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    try:
        await _gm(scene, test_user_id)
        async with admin_session_factory() as session:
            await session.execute(
                delete(StatDefinitionEnumValue).where(StatDefinitionEnumValue.value == "none")
            )
            await session.commit()
        refused = await _into(client, scene, "blade", "chest", lift_binding=True)
        assert refused.status_code == 422, refused.text
        assert refused.json()["type"] == "binding-not-liftable"
        assert await _parent(scene, "blade") == scene.ids["backpack"]
    finally:
        await _tear_down(scene)

    # Without a binding stat, nothing binds and there's nothing to lift.
    scene = await _scene(test_user_id, binding=False)
    try:
        await _gm(scene, test_user_id)
        assert not await _bound(client, scene, "ring")
        assert (await _give(client, scene, "ring", "pia")).status_code == 200
        lifted = await _into(client, scene, "blade", "chest", lift_binding=True)
        assert lifted.status_code == 200, lifted.text
    finally:
        await _tear_down(scene)


async def test_a_formula_can_decide_the_binding(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A comparison formula on the Gloves' own entity: bound on equip while
    their curse is over 2."""
    scene = await _scene(test_user_id)
    try:
        async with admin_session_factory() as session:
            group_id = await session.scalar(
                select(StatDefinition.stat_group_id).where(
                    StatDefinition.id == scene.ids["stat:binding"]
                )
            )
            curse = StatDefinition(
                tenant_id=scene.tenant_id,
                stat_group_id=group_id,
                name="curse",
                value_type=StatValueType.INT,
            )
            session.add(curse)
            await session.flush()
            key = {"entity_id": scene.ids["gloves"], "tenant_id": scene.tenant_id}
            # The prototype's on_equip is overruled by the Gloves' own formula.
            session.add(ComputedStat(**key, stat_definition_id=scene.ids["stat:binding"]))
            await session.flush()
            session.add(
                ComputedStatComparison(
                    **key,
                    stat_definition_id=scene.ids["stat:binding"],
                    left_stat_definition_id=curse.id,
                    comparator="gt",
                    right_constant=Decimal(2),
                    true_value="on_equip",
                    false_value="none",
                )
            )
            session.add(EntityStat(**key, stat_definition_id=curse.id, value_int=1))
            await session.commit()
            curse_id = curse.id

        assert (await _into(client, scene, "gloves", "alice")).json()["bound"] is False
        assert (await _into(client, scene, "gloves", "backpack")).status_code == 200

        async with admin_session_factory() as session:
            stat = await session.get_one(EntityStat, (scene.ids["gloves"], curse_id))
            stat.value_int = 3
            await session.commit()
        assert (await _into(client, scene, "gloves", "alice")).json()["bound"] is True
        stuck = await _into(client, scene, "gloves", "backpack")
        assert stuck.status_code == 409, stuck.text

        await _gm(scene, test_user_id)
        formula = await _into(client, scene, "gloves", "backpack", lift_binding=True)
        assert formula.status_code == 422, formula.text
        assert "formula" in formula.json()["detail"]
    finally:
        await _tear_down(scene)
