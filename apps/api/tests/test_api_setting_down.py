"""Setting things down - ADR 0132, RFC 0031 slice 3: a stack out of every
container as single items, and a deleted container's contents set down."""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import func, select
from test_api_held_by import _character, _instance

from lorenzo_api.models import (
    AuditLog,
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Item,
    Ownership,
    StatDefinition,
    StatGroup,
    StatValueType,
)


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    ids: dict[str, uuid.UUID]

    @property
    def base(self) -> str:
        return f"/tenants/{self.tenant_id}/item-instances"


async def _scene(test_user_id: uuid.UUID) -> _Scene:
    """The caller plays Alice. She has a Backpack in hand, holding a stack
    of 3 Arrows made from the Arrow item, with a +1 of their own
    (`enchantment`) and a slug. Her Chest stands in no container, holding
    her Rope and a stack of 5 Bolts; her Crate is in her hands, with a Coin
    in it."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        arrow = Entity(tenant_id=tenant_id, name="Arrow")
        session.add(arrow)
        await session.flush()
        session.add(Item(entity_id=arrow.id, tenant_id=tenant_id))
        group = StatGroup(tenant_id=tenant_id, name="magic")
        session.add(group)
        await session.flush()
        enchantment = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=group.id,
            name="enchantment",
            value_type=StatValueType.INT,
        )
        session.add(enchantment)
        await session.flush()

        ids = {"alice": alice, "arrow": arrow.id, "enchantment": enchantment.id, "magic": group.id}
        ids["backpack"] = await _instance(
            session, tenant_id, "Backpack", owner=alice, container=alice
        )
        ids["arrows"] = await _instance(
            session, tenant_id, "Arrows", owner=alice, container=ids["backpack"]
        )
        stack = await session.get_one(Containment, ids["arrows"])
        stack.quantity = 3
        session.add_all(
            [
                EntityPrototype(
                    entity_id=ids["arrows"], prototype_id=arrow.id, tenant_id=tenant_id
                ),
                EntityStat(
                    entity_id=ids["arrows"],
                    stat_definition_id=enchantment.id,
                    tenant_id=tenant_id,
                    value_int=1,
                ),
                EntityStatGroup(
                    entity_id=ids["arrows"], stat_group_id=group.id, tenant_id=tenant_id
                ),
                EntitySlug(entity_id=ids["arrows"], tenant_id=tenant_id, slug="the-arrows"),
            ]
        )
        ids["chest"] = await _instance(session, tenant_id, "Chest", owner=alice)
        ids["rope"] = await _instance(
            session, tenant_id, "Rope", owner=alice, container=ids["chest"]
        )
        ids["bolts"] = await _instance(
            session, tenant_id, "Bolts", owner=alice, container=ids["chest"]
        )
        (await session.get_one(Containment, ids["bolts"])).quantity = 5
        ids["crate"] = await _instance(session, tenant_id, "Crate", owner=alice, container=alice)
        ids["coin"] = await _instance(
            session, tenant_id, "Coin", owner=alice, container=ids["crate"]
        )
        await session.commit()
    return _Scene(tenant_id, ids)


async def _named(tenant_id: uuid.UUID, name: str) -> list[uuid.UUID]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(Entity.id).where(Entity.tenant_id == tenant_id, Entity.name == name)
                )
            ).all()
        )


async def test_setting_down_a_stack_makes_it_single_items_only_when_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    arrows = scene.ids["arrows"]

    refused = await client.delete(f"{scene.base}/{arrows}/container")
    set_down = await client.delete(f"{scene.base}/{arrows}/container", params={"split": True})

    assert refused.status_code == 409
    assert refused.json()["type"] == "stack-needs-container"
    assert "split=true" in refused.json()["detail"]
    assert set_down.status_code == 200, set_down.text
    # The stack itself is one of them, in no container now.
    assert set_down.json()["entity_id"] == str(arrows)
    assert set_down.json()["container_entity_id"] is None

    pieces = await _named(scene.tenant_id, "Arrows")
    assert len(pieces) == 3
    async with admin_session_factory() as session:
        for piece in pieces:
            assert await session.get(Containment, piece) is None
            owner = await session.get_one(Ownership, piece)
            assert owner.owner_character_id == scene.ids["alice"]
            prototype = await session.get_one(EntityPrototype, (piece, scene.ids["arrow"]))
            assert prototype is not None
            # Every piece keeps the stack's own +1.
            stat = await session.get_one(EntityStat, (piece, scene.ids["enchantment"]))
            assert stat.value_int == 1
            assert await session.get(EntityStatGroup, (piece, scene.ids["magic"])) is not None
        # Its slug stays with the one that kept its id.
        slugged = await session.scalars(
            select(EntitySlug.entity_id).where(EntitySlug.tenant_id == scene.tenant_id)
        )
        assert list(slugged) == [arrows]
        detail = await session.scalar(
            select(AuditLog.detail).where(
                AuditLog.tenant_id == scene.tenant_id,
                AuditLog.action == "item_instance.container_cleared",
                AuditLog.target_id == arrows,
            )
        )
    assert detail == f"container={scene.ids['backpack']}; split into 3"

    await delete_tenant(scene.tenant_id)


async def test_deleting_a_container_in_no_container_sets_its_contents_down(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The Chest is Alice's, in no container. What's in it no longer goes to
    her hands: it's set down, and its stack of Bolts only when asked."""
    scene = await _scene(test_user_id)
    chest = scene.ids["chest"]

    refused = await client.delete(f"{scene.base}/{chest}")
    assert refused.status_code == 409
    assert refused.json()["type"] == "stack-needs-container"
    assert "Chest holds Bolts, a stack of 5" in refused.json()["detail"]

    deleted = await client.delete(f"{scene.base}/{chest}", params={"split": True})

    assert deleted.status_code == 204, deleted.text
    bolts = await _named(scene.tenant_id, "Bolts")
    assert len(bolts) == 5
    async with admin_session_factory() as session:
        assert await session.get(Containment, scene.ids["rope"]) is None
        for bolt in bolts:
            assert await session.get(Containment, bolt) is None
        assert (
            await session.scalar(select(func.count()).select_from(Entity).where(Entity.id == chest))
            == 0
        )

    await delete_tenant(scene.tenant_id)


async def test_deleting_a_container_in_hand_still_passes_its_contents_out(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0128, unchanged: the Crate is in Alice's hands, so its Coin is."""
    scene = await _scene(test_user_id)

    deleted = await client.delete(f"{scene.base}/{scene.ids['crate']}")

    assert deleted.status_code == 204, deleted.text
    async with admin_session_factory() as session:
        coin = await session.get_one(Containment, scene.ids["coin"])
        assert coin.parent_entity_id == scene.ids["alice"]

    await delete_tenant(scene.tenant_id)
