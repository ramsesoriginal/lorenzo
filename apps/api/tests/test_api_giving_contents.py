"""Giving a container with what's inside it, and giving everything inside -
ADR 0125."""

import uuid
from dataclasses import dataclass
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from test_api_held_by import _character, _instance

from lorenzo_api.models import AuditLog, CampaignGm, Containment, EntityChange, Ownership, User


@dataclass
class _Pack:
    tenant_id: uuid.UUID
    pia_user_id: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _make_pack(test_user_id: uuid.UUID) -> _Pack:
    """The caller plays Alice, a plain participant (no Membership, so no
    OWNER bypass). Another player plays Pia and Brisk, in campaigns the
    caller isn't in.

    Alice carries her Backpack, holding:
    - her Rope;
    - Pia's Potion;
    - Brisk's Letter;
    - her Belt pouch, with her Coin and an ownerless Gem in it;
    - her Familiar (a being), holding an ownerless Cheese.

    She also carries an ownerless Sack, with an ownerless Pebble in it.
    """
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        alices = await make_campaign(session, tenant_id=tenant_id, name="Alice's")
        pias = await make_campaign(session, tenant_id=tenant_id, name="Pia's")
        brisks = await make_campaign(session, tenant_id=tenant_id, name="Brisk's")
        await session.flush()
        pia_user = User(authgear_subject_id=f"pia-{uuid.uuid4()}")
        session.add(pia_user)
        await session.flush()
        alice = await _character(session, tenant_id, alices.id, test_user_id, "Alice")
        pia = await _character(session, tenant_id, pias.id, pia_user.id, "Pia")
        brisk = await _character(session, tenant_id, brisks.id, pia_user.id, "Brisk")
        familiar = (await make_being(session, tenant_id=tenant_id, name="Familiar")).entity_id

        ids = {"alice": alice, "pia": pia, "brisk": brisk, "pias_campaign": pias.id}
        backpack = await _instance(session, tenant_id, "Backpack", owner=alice, container=alice)
        pouch = await _instance(session, tenant_id, "Belt pouch", owner=alice, container=backpack)
        sack = await _instance(session, tenant_id, "Sack", container=alice)
        session.add(
            Containment(child_entity_id=familiar, parent_entity_id=backpack, tenant_id=tenant_id)
        )
        ids |= {"backpack": backpack, "pouch": pouch, "sack": sack, "familiar": familiar}
        ids["rope"] = await _instance(session, tenant_id, "Rope", owner=alice, container=backpack)
        ids["potion"] = await _instance(session, tenant_id, "Potion", owner=pia, container=backpack)
        ids["letter"] = await _instance(
            session, tenant_id, "Letter", owner=brisk, container=backpack
        )
        ids["coin"] = await _instance(session, tenant_id, "Coin", owner=alice, container=pouch)
        ids["gem"] = await _instance(session, tenant_id, "Gem", container=pouch)
        ids["cheese"] = await _instance(session, tenant_id, "Cheese", container=familiar)
        ids["pebble"] = await _instance(session, tenant_id, "Pebble", container=sack)
        await session.commit()
    return _Pack(tenant_id=tenant_id, pia_user_id=pia_user.id, ids=ids)


async def _tear_down(pack: _Pack) -> None:
    await delete_tenant(pack.tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, pack.pia_user_id))
        await session.commit()


async def _owner_of(pack: _Pack, name: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        return await session.scalar(
            select(Ownership.owner_character_id).where(Ownership.owned_entity_id == pack.ids[name])
        )


async def _container_of(pack: _Pack, name: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        return await session.scalar(
            select(Containment.parent_entity_id).where(
                Containment.child_entity_id == pack.ids[name]
            )
        )


def _by_title(contents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {content["title"]: content for content in contents}


async def test_gives_a_container_with_what_inside_is_the_callers_to_give(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids

    assigned = await client.post(
        f"/tenants/{t}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(ids["backpack"]),
                "owner_character_id": str(ids["brisk"]),
                "with_contents": True,
            }
        ],
    )

    assert assigned.status_code == 200
    [result] = assigned.json()
    assert result["status"] == "ok"
    assert result["item_instance"]["owner_entity_id"] == str(ids["brisk"])
    contents = _by_title(result["contents"])
    # Brisk's Letter is already his, and what the Familiar holds is its own.
    assert sorted(contents) == ["Belt pouch", "Coin", "Gem", "Potion", "Rope"]
    for given in ["Belt pouch", "Coin", "Gem", "Rope"]:
        assert contents[given]["status"] == "ok"
        assert contents[given]["owner"]["name"] == "Brisk"
        assert contents[given]["problem"] is None
    kept = contents["Potion"]
    assert kept["status"] == "kept"
    assert kept["owner"]["name"] == "Pia"
    assert kept["problem"]["type"] == "item-not-yours-to-give"

    for name in ["backpack", "pouch", "coin", "gem", "rope", "letter"]:
        assert await _owner_of(pack, name) == ids["brisk"]
    assert await _owner_of(pack, "potion") == ids["pia"]
    assert await _owner_of(pack, "cheese") is None
    # Nothing moves.
    assert await _container_of(pack, "backpack") == ids["alice"]
    assert await _container_of(pack, "coin") == ids["pouch"]

    await _tear_down(pack)


async def test_what_inside_is_given_before_the_container_is_handed_over(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Alice reaches the ownerless Pebble only through the ownerless Sack in
    her hands. Handing the Sack over first would put the Pebble out of her
    reach."""
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids

    assigned = await client.post(
        f"/tenants/{t}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(ids["sack"]),
                "owner_character_id": str(ids["brisk"]),
                "with_contents": True,
                "move_to_owner": True,
            }
        ],
    )

    assert assigned.status_code == 200
    [result] = assigned.json()
    assert [(c["title"], c["status"]) for c in result["contents"]] == [("Pebble", "ok")]
    assert await _owner_of(pack, "pebble") == ids["brisk"]
    assert await _container_of(pack, "sack") == ids["brisk"]
    assert await _container_of(pack, "pebble") == ids["sack"]

    await _tear_down(pack)


async def test_giving_part_of_a_stack_with_contents_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)

    assigned = await client.post(
        f"/tenants/{pack.tenant_id}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(pack.ids["backpack"]),
                "owner_character_id": str(pack.ids["brisk"]),
                "quantity": 1,
                "with_contents": True,
            }
        ],
    )

    assert assigned.status_code == 422

    await _tear_down(pack)


async def test_a_dry_run_answers_and_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids
    base = f"/tenants/{t}/item-instances"

    assigned = await client.post(
        f"{base}/bulk-assign",
        params={"dry_run": "true"},
        json=[
            {
                "entity_id": str(ids["backpack"]),
                "owner_character_id": str(ids["brisk"]),
                "with_contents": True,
            }
        ],
    )
    given = await client.post(
        f"{base}/{ids['pouch']}/give-contents",
        params={"dry_run": "true"},
        json={"owner_character_id": str(ids["brisk"])},
    )

    assert assigned.status_code == 200
    assert assigned.json()[0]["status"] == "ok"
    assert len(assigned.json()[0]["contents"]) == 5
    assert given.status_code == 200
    assert sorted(c["title"] for c in given.json()) == ["Coin", "Gem"]
    for name in ["backpack", "pouch", "coin", "rope"]:
        assert await _owner_of(pack, name) == ids["alice"]
    assert await _owner_of(pack, "gem") is None
    async with admin_session_factory() as session:
        logged = await session.scalar(
            select(AuditLog.id).where(
                AuditLog.tenant_id == t, AuditLog.action.like("item_instance.%")
            )
        )
        told = await session.scalar(select(EntityChange.id).where(EntityChange.tenant_id == t))
    assert logged is None
    assert told is None

    await _tear_down(pack)


async def test_gives_everything_inside_but_not_the_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids

    given = await client.post(
        f"/tenants/{t}/item-instances/{ids['backpack']}/give-contents",
        json={"owner_character_id": str(ids["brisk"])},
    )

    assert given.status_code == 200
    contents = _by_title(given.json())
    assert sorted(contents) == ["Belt pouch", "Coin", "Gem", "Potion", "Rope"]
    assert contents["Potion"]["status"] == "kept"
    assert await _owner_of(pack, "backpack") == ids["alice"]
    for name in ["pouch", "coin", "gem", "rope"]:
        assert await _owner_of(pack, name) == ids["brisk"]

    async with admin_session_factory() as session:
        logged = (
            await session.execute(
                select(AuditLog.action, AuditLog.target_id, AuditLog.detail).where(
                    AuditLog.tenant_id == t, AuditLog.action.like("item_instance.%")
                )
            )
        ).all()
        received = (
            await session.execute(
                select(EntityChange.entity_id).where(
                    EntityChange.user_id == pack.pia_user_id,
                    EntityChange.character_entity_id == ids["brisk"],
                    EntityChange.kind == "received",
                )
            )
        ).scalars()
        assert set(received) == {ids[name] for name in ["pouch", "coin", "gem", "rope"]}
    assert logged == [
        (
            "item_instance.contents_given",
            ids["backpack"],
            f"owner={ids['brisk']}; 4 given, 1 kept",
        )
    ]

    await _tear_down(pack)


async def test_gives_only_whats_directly_inside_when_not_recursive(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids

    given = await client.post(
        f"/tenants/{t}/item-instances/{ids['backpack']}/give-contents",
        json={"owner_character_id": str(ids["brisk"]), "recursive": False},
    )

    assert given.status_code == 200
    assert sorted(c["title"] for c in given.json()) == ["Belt pouch", "Potion", "Rope"]
    assert await _owner_of(pack, "pouch") == ids["brisk"]
    assert await _owner_of(pack, "coin") == ids["alice"]

    await _tear_down(pack)


async def test_a_gm_gives_everything_inside(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids
    async with admin_session_factory() as session:
        session.add(CampaignGm(user_id=test_user_id, campaign_id=ids["pias_campaign"], tenant_id=t))
        await session.commit()

    given = await client.post(
        f"/tenants/{t}/item-instances/{ids['backpack']}/give-contents",
        json={"owner_character_id": str(ids["brisk"])},
    )

    assert given.status_code == 200
    assert {c["status"] for c in given.json()} == {"ok"}
    assert await _owner_of(pack, "potion") == ids["brisk"]

    await _tear_down(pack)


async def test_give_contents_refuses_a_container_out_of_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids
    async with admin_session_factory() as session:
        chest = await _instance(session, t, "Chest", owner=ids["pia"], container=ids["pia"])
        await session.commit()
    base = f"/tenants/{t}/item-instances"
    to_brisk = {"owner_character_id": str(ids["brisk"])}

    out_of_reach = await client.post(f"{base}/{chest}/give-contents", json=to_brisk)
    missing = await client.post(f"{base}/{uuid.uuid4()}/give-contents", json=to_brisk)
    nobody = await client.post(
        f"{base}/{ids['backpack']}/give-contents",
        json={"owner_character_id": str(uuid.uuid4())},
    )

    assert out_of_reach.status_code == 403
    assert out_of_reach.json()["type"] == "item-instance-management-forbidden"
    assert missing.status_code == 404
    assert nobody.status_code == 404

    await _tear_down(pack)


async def test_bulk_activity_counts_what_was_given_along(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    pack = await _make_pack(test_user_id)
    t, ids = pack.tenant_id, pack.ids

    assigned = await client.post(
        f"/tenants/{t}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(ids["backpack"]),
                "owner_character_id": str(ids["brisk"]),
                "with_contents": True,
            }
        ],
    )

    assert assigned.status_code == 200
    async with admin_session_factory() as session:
        detail = await session.scalar(
            select(AuditLog.detail).where(
                AuditLog.tenant_id == t, AuditLog.action == "item_instance.bulk_assigned"
            )
        )
    assert detail == "1 ok, 0 failed; inside: 4 given along, 1 kept"

    await _tear_down(pack)
