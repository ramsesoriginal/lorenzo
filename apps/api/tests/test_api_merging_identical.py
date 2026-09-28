"""Merging what's identical on a move - ADR 0133, RFC 0031 slice 4."""

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
    Information,
    Item,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    other_user_ids: list[uuid.UUID]
    ids: dict[str, uuid.UUID]

    @property
    def base(self) -> str:
        return f"/tenants/{self.tenant_id}/item-instances"


async def _scene(test_user_id: uuid.UUID) -> _Scene:
    """The caller plays Alice; another player plays Brisk. Alice carries a
    Quiver holding a stack of 3 Arrows, and an empty Pouch. In her hands are
    single Arrows of hers: a plain one, one with a note, one with a slug, a
    blessed one (an `enchantment` of its own), and one renamed "Grandpa's
    arrow" - and Brisk's plain Arrow. Three more plain ones of hers lie in no
    container. Every Arrow is an instance of the Arrow item."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        brisk_user = User(authgear_subject_id=f"brisk-{uuid.uuid4()}")
        session.add(brisk_user)
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        brisk = await _character(session, tenant_id, campaign.id, brisk_user.id, "Brisk")
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

        ids = {"alice": alice, "brisk": brisk}
        ids["quiver"] = await _instance(session, tenant_id, "Quiver", owner=alice, container=alice)
        ids["pouch"] = await _instance(session, tenant_id, "Pouch", owner=alice, container=alice)

        async def an_arrow(key: str, owner: uuid.UUID, container: uuid.UUID | None, name="Arrow"):
            ids[key] = await _instance(session, tenant_id, name, owner=owner, container=container)
            session.add(
                EntityPrototype(entity_id=ids[key], prototype_id=arrow.id, tenant_id=tenant_id)
            )

        await an_arrow("stack", alice, ids["quiver"])
        await an_arrow("plain", alice, alice)
        await an_arrow("noted", alice, alice)
        await an_arrow("slugged", alice, alice)
        await an_arrow("blessed", alice, alice)
        await an_arrow("grandpas", alice, alice, name="Grandpa's arrow")
        await an_arrow("brisks", brisk, alice)
        for n in (1, 2, 3):
            await an_arrow(f"loose{n}", alice, None)
        await session.flush()
        (await session.get_one(Containment, ids["stack"])).quantity = 3
        session.add_all(
            [
                Information(
                    tenant_id=tenant_id,
                    entity_id=ids["noted"],
                    title="Note",
                    type="note",
                    created_by=test_user_id,
                ),
                EntitySlug(entity_id=ids["slugged"], tenant_id=tenant_id, slug="lucky-arrow"),
                EntityStat(
                    entity_id=ids["blessed"],
                    stat_definition_id=enchantment.id,
                    tenant_id=tenant_id,
                    value_int=1,
                ),
            ]
        )
        await session.commit()
    return _Scene(tenant_id, [brisk_user.id], ids)


async def _tear_down(scene: _Scene) -> None:
    await delete_tenant(scene.tenant_id)
    async with admin_session_factory() as session:
        for user_id in scene.other_user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


def _into(client: AsyncClient, scene: _Scene, key: str, container: str, **body: object):
    return client.put(
        f"{scene.base}/{scene.ids[key]}/container",
        json={"container_entity_id": str(scene.ids[container]), **body},
    )


async def _quantity(entity_id: uuid.UUID) -> int | None:
    async with admin_session_factory() as session:
        row = await session.get(Containment, entity_id)
        return row.quantity if row is not None else None


async def _exists(entity_id: uuid.UUID) -> bool:
    async with admin_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Entity).where(Entity.id == entity_id)
        )
        return count == 1


async def test_a_move_merges_into_an_identical_stack_only_when_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    ids = scene.ids

    merged = await _into(client, scene, "plain", "quiver", merge_identical=True)
    kept_apart = await _into(client, scene, "loose1", "quiver")

    # The answer is where it ended up: the stack, one more in it.
    assert merged.status_code == 200, merged.text
    assert merged.json()["entity_id"] == str(ids["stack"])
    assert merged.json()["quantity"] == 4
    assert kept_apart.status_code == 200, kept_apart.text
    assert kept_apart.json()["entity_id"] == str(ids["loose1"])
    assert await _quantity(ids["stack"]) == 4
    assert not await _exists(ids["plain"])
    async with admin_session_factory() as session:
        detail = await session.scalar(
            select(AuditLog.detail).where(
                AuditLog.tenant_id == scene.tenant_id,
                AuditLog.action == "item_instance.merged",
                AuditLog.target_id == ids["stack"],
            )
        )
    assert detail == f"source={ids['plain']}, quantity=1; identical, on a move"

    await _tear_down(scene)


async def test_what_is_a_thing_of_its_own_never_merges(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A note, a slug, a stat value of its own, a name of its own, or another
    owner: each stays itself in the Quiver."""
    scene = await _scene(test_user_id)

    for key in ("noted", "slugged", "blessed", "grandpas", "brisks"):
        moved = await _into(client, scene, key, "quiver", merge_identical=True)
        assert moved.status_code == 200, moved.text
        assert moved.json()["entity_id"] == str(scene.ids[key]), key

    assert await _quantity(scene.ids["stack"]) == 3

    await _tear_down(scene)


async def test_things_moved_together_that_are_identical_end_up_one_stack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Three plain Arrows from nowhere into the empty Pouch: the first goes in,
    the other two merge into it."""
    scene = await _scene(test_user_id)
    loose = [scene.ids[f"loose{n}"] for n in (1, 2, 3)]

    response = await client.post(
        f"{scene.base}/bulk-move",
        json={
            "to_container_entity_id": str(scene.ids["pouch"]),
            "items": [{"entity_id": str(i)} for i in loose],
            "merge_identical": True,
        },
    )

    assert response.status_code == 200, response.text
    results = response.json()
    assert [r["entity_id"] for r in results] == [str(i) for i in loose]
    # Each entry names where it ended up: all in the first one's stack.
    assert {r["item_instance"]["entity_id"] for r in results} == {str(loose[0])}
    assert await _quantity(loose[0]) == 3
    assert not await _exists(loose[1])
    assert not await _exists(loose[2])

    await _tear_down(scene)
