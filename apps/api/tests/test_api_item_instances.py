import uuid
from datetime import datetime

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    CampaignGm,
    Character,
    CharacterPlayer,
    Containment,
    Entity,
    EntityPrototype,
    Information,
    Item,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    Payload,
    PayloadDescription,
    Player,
    Tenant,
    User,
)


async def _make_own_character(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> Character:
    """A Player+Character+CharacterPlayer roster link for user_id
    specifically (unlike conftest's make_player, which always creates its
    own fresh user) - what the self-or-managed tests below need to make
    `client`'s fixed test_user_id actually control a character.
    """
    player = Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id)
    session.add(player)
    await session.flush()
    character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
    session.add(
        CharacterPlayer(
            character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
        )
    )
    await session.flush()
    return character


async def _make_item(tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def test_list_item_instances_paginates_and_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)

    async with admin_session_factory() as session:
        e1 = Entity(tenant_id=tenant_a, name="A1")
        e2 = Entity(tenant_id=tenant_a, name="A2")
        e3 = Entity(tenant_id=tenant_b, name="B1")
        session.add_all([e1, e2, e3])
        await session.flush()
        session.add_all(
            [
                ItemInstance(entity_id=e1.id, tenant_id=tenant_a),
                ItemInstance(entity_id=e2.id, tenant_id=tenant_a),
                ItemInstance(entity_id=e3.id, tenant_id=tenant_b),
            ]
        )
        await session.commit()
        e1_id, e2_id = e1.id, e2.id

    response = await client.get(f"/tenants/{tenant_a}/item-instances")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {i["entity_id"] for i in body["items"]} == {str(e1_id), str(e2_id)}

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_list_item_instances_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000/item-instances")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


async def _make_cross_owner_fixture(
    tenant_id: uuid.UUID, *, test_user_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """ADR 0040's own fixture shape: Alice (test_user_id's own character, in
    Campaign A) owns one instance; Bob, a character rostered only in a
    separate Campaign B test_user_id has no standing over, owns another; a
    third instance has no owner at all. Returns (campaign_b_id, bob_id,
    alice_item_id, bob_item_id, loose_item_id, bob_user_id) - the last one
    for callers to clean up after delete_tenant, mirroring
    test_update_item_instance_allowed_for_gm_of_current_owners_campaign's
    own cleanup (a Tenant delete doesn't cascade to User, ADR 0022).
    """
    async with admin_session_factory() as session:
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="Campaign A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="Campaign B")
        await session.flush()
        alice = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id
        )

        bob_user = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(bob_user)
        await session.flush()
        bob_player = Player(user_id=bob_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add(bob_player)
        await session.flush()
        bob = await make_character(
            session, tenant_id=tenant_id, name="Bob", owner_player_id=bob_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=bob.entity_id, player_id=bob_player.id, tenant_id=tenant_id
            )
        )

        alice_item = Entity(tenant_id=tenant_id, name="Alice's Sword")
        bob_item = Entity(tenant_id=tenant_id, name="Bob's Dagger")
        loose_item = Entity(tenant_id=tenant_id, name="Loose Loot")
        session.add_all([alice_item, bob_item, loose_item])
        await session.flush()
        session.add_all(
            [
                ItemInstance(entity_id=alice_item.id, tenant_id=tenant_id),
                ItemInstance(entity_id=bob_item.id, tenant_id=tenant_id),
                ItemInstance(entity_id=loose_item.id, tenant_id=tenant_id),
            ]
        )
        session.add_all(
            [
                Ownership(
                    owned_entity_id=alice_item.id,
                    owner_character_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
                Ownership(
                    owned_entity_id=bob_item.id,
                    owner_character_id=bob.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        return (
            campaign_b.id,
            bob.entity_id,
            alice_item.id,
            bob_item.id,
            loose_item.id,
            bob_user.id,
        )


async def test_list_item_instances_hides_items_owned_by_an_unrelated_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040. test_user_id is tenant OWNER here (make_tenant's default)
    and controls Alice, but has no CampaignGm/Player standing in Bob's own
    campaign and no ORGA role - plain OWNER gets no bonus read visibility
    over another character's inventory, only self/GM/ORGA do (see the
    dedicated tests below for those). Ownerless stays visible regardless.
    """
    tenant_id = await make_tenant(test_user_id)
    _, _, alice_item_id, bob_item_id, loose_item_id, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )

    response = await client.get(f"/tenants/{tenant_id}/item-instances")

    assert response.status_code == 200
    visible_ids = {i["entity_id"] for i in response.json()["items"]}
    assert visible_ids == {str(alice_item_id), str(loose_item_id)}
    assert str(bob_item_id) not in visible_ids

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_owned_by_returns_empty_groups_for_an_owner_the_caller_cannot_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040. No separate existence check is needed for this route - the
    shared visibility predicate already makes an unreachable owner's
    inventory come back indistinguishable from "owns nothing."
    """
    tenant_id = await make_tenant(test_user_id)
    _, bob_id, _, _, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )

    response = await client.get(f"/tenants/{tenant_id}/item-instances/owned-by/{bob_id}")

    assert response.status_code == 200
    assert response.json()["groups"] == []

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_get_item_instance_404_for_an_owned_item_the_caller_cannot_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040. Existence hidden, the same path an unknown/cross-tenant id
    already takes - not a redacted 200.
    """
    tenant_id = await make_tenant(test_user_id)
    _, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )

    response = await client.get(f"/tenants/{tenant_id}/item-instances/{bob_item_id}")

    assert response.status_code == 404

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_list_item_instances_gm_of_owners_campaign_sees_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040's GM tier - a genuine CampaignGm row on Bob's own campaign,
    not the OWNER-bypass test_update_item_instance_allowed_for_gm_of_
    current_owners_campaign relies on for write authorization. Membership
    is removed first so this only proves the GM path, not OWNER's own
    (deliberately absent) read bonus.
    """
    tenant_id = await make_tenant(test_user_id)
    campaign_b_id, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Membership, (tenant_id, test_user_id)))
        session.add(
            CampaignGm(user_id=test_user_id, campaign_id=campaign_b_id, tenant_id=tenant_id)
        )
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances")

    assert response.status_code == 200
    assert str(bob_item_id) in {i["entity_id"] for i in response.json()["items"]}

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_list_item_instances_orga_sees_items_owned_by_unrelated_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040's admin tier is is_orga specifically, not is_tenant_admin -
    proven here by promoting test_user_id's existing OWNER Membership to
    ORGA (make_tenant's default role, which the earlier hides-Bob's-item
    test already proves gets no bonus on its own)."""
    tenant_id = await make_tenant(test_user_id)
    _, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances")

    assert response.status_code == 200
    assert str(bob_item_id) in {i["entity_id"] for i in response.json()["items"]}

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_get_item_instance_returns_detail(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="My Sword")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")

    assert response.status_code == 200
    assert response.json()["entity_id"] == str(entity_id)

    await delete_tenant(tenant_id)


async def test_get_item_instance_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/item-instances/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_get_item_instance_404_for_wrong_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_a, name="My Sword")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_a))
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_b}/item-instances/{entity_id}")

    assert response.status_code == 404

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_owned_by_route_is_not_shadowed_by_the_detail_route(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """/owned-by/{owner_entity_id} is registered before the generic
    /{entity_id} precisely so this doesn't happen - confirmed here, not
    just reasoned through, since getting the registration order backwards
    would make this 422 (owned-by treated as an entity_id) instead of the
    real owned-by response.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        owner = Entity(tenant_id=tenant_id, name="Owner")
        session.add(owner)
        await session.commit()
        owner_id = owner.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances/owned-by/{owner_id}")

    assert response.status_code == 200
    assert response.json() == {"groups": []}

    await delete_tenant(tenant_id)


async def test_owned_by_groups_multiple_owners_multiple_containers_and_uncontained(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ORGA, not OWNER (ADR 0040): owner1/owner2 are bare Entity rows, not
    characters test_user_id controls or GMs - this test is about the
    owned-by grouping/pagination mechanism, not read-visibility scoping, so
    it needs the is_orga bypass to see across both owners at all.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))

        owner1 = Entity(tenant_id=tenant_id, name="Owner One")
        owner2 = Entity(tenant_id=tenant_id, name="Owner Two")
        container1 = Entity(tenant_id=tenant_id, name="Backpack")
        container2 = Entity(tenant_id=tenant_id, name="Chest")
        session.add_all([owner1, owner2, container1, container2])
        await session.flush()

        instance_a = Entity(tenant_id=tenant_id, name="Instance A")
        instance_b = Entity(tenant_id=tenant_id, name="Instance B")
        instance_c = Entity(tenant_id=tenant_id, name="Instance C (uncontained)")
        instance_d = Entity(tenant_id=tenant_id, name="Instance D")
        session.add_all([instance_a, instance_b, instance_c, instance_d])
        await session.flush()

        session.add_all(
            [
                ItemInstance(entity_id=instance_a.id, tenant_id=tenant_id),
                ItemInstance(entity_id=instance_b.id, tenant_id=tenant_id),
                ItemInstance(entity_id=instance_c.id, tenant_id=tenant_id),
                ItemInstance(entity_id=instance_d.id, tenant_id=tenant_id),
            ]
        )
        session.add_all(
            [
                Ownership(
                    owned_entity_id=instance_a.id, owner_character_id=owner1.id, tenant_id=tenant_id
                ),
                Ownership(
                    owned_entity_id=instance_b.id, owner_character_id=owner1.id, tenant_id=tenant_id
                ),
                Ownership(
                    owned_entity_id=instance_c.id, owner_character_id=owner1.id, tenant_id=tenant_id
                ),
                Ownership(
                    owned_entity_id=instance_d.id, owner_character_id=owner2.id, tenant_id=tenant_id
                ),
            ]
        )
        session.add_all(
            [
                Containment(
                    child_entity_id=instance_a.id,
                    parent_entity_id=container1.id,
                    tenant_id=tenant_id,
                ),
                Containment(
                    child_entity_id=instance_b.id,
                    parent_entity_id=container1.id,
                    tenant_id=tenant_id,
                ),
                # instance_c is deliberately left uncontained.
                Containment(
                    child_entity_id=instance_d.id,
                    parent_entity_id=container2.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        owner1_id, owner2_id = owner1.id, owner2.id
        container1_id, container2_id = container1.id, container2.id
        a_id, b_id, c_id, d_id = instance_a.id, instance_b.id, instance_c.id, instance_d.id

    response1 = await client.get(f"/tenants/{tenant_id}/item-instances/owned-by/{owner1_id}")
    assert response1.status_code == 200
    body1 = response1.json()
    groups_by_container = {
        (g["container"]["id"] if g["container"] is not None else None): {
            i["entity_id"] for i in g["item_instances"]
        }
        for g in body1["groups"]
    }
    assert groups_by_container == {
        str(container1_id): {str(a_id), str(b_id)},
        None: {str(c_id)},
    }

    response2 = await client.get(f"/tenants/{tenant_id}/item-instances/owned-by/{owner2_id}")
    assert response2.status_code == 200
    body2 = response2.json()
    assert len(body2["groups"]) == 1
    assert body2["groups"][0]["container"]["id"] == str(container2_id)
    assert {i["entity_id"] for i in body2["groups"][0]["item_instances"]} == {str(d_id)}

    await delete_tenant(tenant_id)


async def test_owned_by_returns_empty_groups_when_owner_has_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        owner = Entity(tenant_id=tenant_id, name="Empty-handed Owner")
        session.add(owner)
        await session.commit()
        owner_id = owner.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances/owned-by/{owner_id}")

    assert response.status_code == 200
    assert response.json() == {"groups": []}

    await delete_tenant(tenant_id)


async def test_owned_by_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/item-instances/owned-by/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


async def test_container_filter_direct_children_non_recursive(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Default recursive=false - deliberately not exercised via an explicit
    query param here, so this also proves the default itself is false.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        root = Entity(tenant_id=tenant_id, name="Root Container")
        child1 = Entity(tenant_id=tenant_id, name="Direct Child 1")
        child2 = Entity(tenant_id=tenant_id, name="Direct Child 2")
        grandchild = Entity(tenant_id=tenant_id, name="Grandchild")
        session.add_all([root, child1, child2, grandchild])
        await session.flush()

        session.add_all(
            [
                ItemInstance(entity_id=child1.id, tenant_id=tenant_id),
                ItemInstance(entity_id=child2.id, tenant_id=tenant_id),
                ItemInstance(entity_id=grandchild.id, tenant_id=tenant_id),
            ]
        )
        session.add_all(
            [
                Containment(
                    child_entity_id=child1.id, parent_entity_id=root.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=child2.id, parent_entity_id=root.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=grandchild.id, parent_entity_id=child1.id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()
        root_id = root.id
        child1_id, child2_id, grandchild_id = child1.id, child2.id, grandchild.id

    response = await client.get(
        f"/tenants/{tenant_id}/item-instances", params={"container_id": str(root_id)}
    )

    assert response.status_code == 200
    body = response.json()
    returned_ids = {i["entity_id"] for i in body["items"]}
    assert returned_ids == {str(child1_id), str(child2_id)}
    assert str(grandchild_id) not in returned_ids

    await delete_tenant(tenant_id)


async def test_container_filter_recursive_includes_deep_chain_and_handles_cycle(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Covers both risky cases from ADR 0016 / the task brief in one fixture
    set: a legitimately deep acyclic chain, and an actual containment
    cycle. The cycle is deliberately a standalone pair (X<->Y), not nested
    under `root` - containment's PK is child_entity_id alone (at most one
    parent per entity, ever), so a node already inside a 2-cycle can't also
    have an external parent from outside it; it's queried directly by its
    own id instead, matching tests/test_containment.py's own precedent for
    constructing a cycle.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        root = Entity(tenant_id=tenant_id, name="Root")
        session.add(root)
        await session.flush()

        chain_ids: list[uuid.UUID] = []
        parent_id = root.id
        for i in range(4):
            e = Entity(tenant_id=tenant_id, name=f"Chain {i}")
            session.add(e)
            await session.flush()
            session.add(ItemInstance(entity_id=e.id, tenant_id=tenant_id))
            session.add(
                Containment(child_entity_id=e.id, parent_entity_id=parent_id, tenant_id=tenant_id)
            )
            chain_ids.append(e.id)
            parent_id = e.id

        x = Entity(tenant_id=tenant_id, name="X")
        y = Entity(tenant_id=tenant_id, name="Y")
        session.add_all([x, y])
        await session.flush()
        session.add(ItemInstance(entity_id=x.id, tenant_id=tenant_id))
        session.add(ItemInstance(entity_id=y.id, tenant_id=tenant_id))
        session.add(Containment(child_entity_id=y.id, parent_entity_id=x.id, tenant_id=tenant_id))
        session.add(Containment(child_entity_id=x.id, parent_entity_id=y.id, tenant_id=tenant_id))
        await session.commit()
        root_id = root.id
        x_id, y_id = x.id, y.id

    response = await client.get(
        f"/tenants/{tenant_id}/item-instances",
        params={"container_id": str(root_id), "recursive": "true", "size": 100},
    )
    assert response.status_code == 200
    body = response.json()
    returned_ids = {i["entity_id"] for i in body["items"]}
    assert returned_ids == {str(e) for e in chain_ids}
    assert body["total"] == len(chain_ids)

    # The cycle must terminate (200, not a hang/500) and return exactly the
    # one other node in the pair, never X itself.
    cycle_response = await client.get(
        f"/tenants/{tenant_id}/item-instances",
        params={"container_id": str(x_id), "recursive": "true"},
    )
    assert cycle_response.status_code == 200
    cycle_body = cycle_response.json()
    assert {i["entity_id"] for i in cycle_body["items"]} == {str(y_id)}
    assert cycle_body["total"] == 1

    await delete_tenant(tenant_id)


async def test_container_filter_404_when_container_belongs_to_another_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)

    async with admin_session_factory() as session:
        container = Entity(tenant_id=tenant_a, name="Tenant A's Container")
        session.add(container)
        await session.commit()
        container_id = container.id

    # Exists, but under tenant_a - requesting it via tenant_b's path must
    # 404 exactly like an unknown id would, whether recursive or not.
    response = await client.get(
        f"/tenants/{tenant_b}/item-instances", params={"container_id": str(container_id)}
    )
    assert response.status_code == 404

    recursive_response = await client.get(
        f"/tenants/{tenant_b}/item-instances",
        params={"container_id": str(container_id), "recursive": "true"},
    )
    assert recursive_response.status_code == 404

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_container_filter_404_for_unknown_container_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/item-instances",
        params={"container_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_container_filter_recursive_pagination_spans_multiple_pages(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        root = Entity(tenant_id=tenant_id, name="Big Container")
        session.add(root)
        await session.flush()

        instance_ids: list[uuid.UUID] = []
        for i in range(5):
            e = Entity(tenant_id=tenant_id, name=f"Instance {i}")
            session.add(e)
            await session.flush()
            session.add(ItemInstance(entity_id=e.id, tenant_id=tenant_id))
            session.add(
                Containment(child_entity_id=e.id, parent_entity_id=root.id, tenant_id=tenant_id)
            )
            instance_ids.append(e.id)
        await session.commit()
        root_id = root.id

    seen: set[str] = set()
    totals: set[int] = set()
    pages_reported: set[int] = set()
    for page in (1, 2, 3):
        response = await client.get(
            f"/tenants/{tenant_id}/item-instances",
            params={
                "container_id": str(root_id),
                "recursive": "true",
                "size": 2,
                "page": page,
            },
        )
        assert response.status_code == 200
        body = response.json()
        totals.add(body["total"])
        pages_reported.add(body["pages"])
        assert body["page"] == page
        seen.update(i["entity_id"] for i in body["items"])

    assert totals == {5}
    assert pages_reported == {3}
    assert seen == {str(i) for i in instance_ids}

    await delete_tenant(tenant_id)


async def test_get_item_instance_hides_gm_only_description_from_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Same information-visibility fix as items.py/entities.py/payloads.py
    (ADR 0028's addendum), confirmed wired up here too - the underlying
    mechanism (EntityViewMixin/eager_load_options) is shared with items.py
    and is exhaustively tested there; this just proves the wiring in this
    router specifically.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="My Sword")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        info = Information(
            tenant_id=tenant_id,
            entity_id=entity.id,
            title="A fine sword",
            type="description",
            is_public=False,
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="A gleaming blade.",
            )
        )
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert response.status_code == 200
    assert response.json()["descriptions"] == []

    await delete_tenant(tenant_id)


async def test_get_item_instance_gm_with_no_tenant_membership_sees_gm_only_secret(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The milestone's own scenario, end to end (RFC 0009/ADR 0035): Zorro,
    GM of "The Ashen Crown" with zero tenant-wide Membership, must see that
    Ashfang - owned by Alice's character, on his campaign's own roster - is
    cursed. Demotes test_user_id from make_tenant's default OWNER
    Membership first (same technique as
    test_create_item_instance_ownerless_forbidden_for_plain_player above),
    so this genuinely proves the CampaignGm-only path reaches
    is_tenant_participant's gate on this router (ADR 0032), not an
    accidental OWNER/ORGA bypass.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)

        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Ashen Crown")
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))

        alice = User(authgear_subject_id=f"authgear|alice-{uuid.uuid4()}")
        session.add(alice)
        await session.flush()
        alice_player = Player(user_id=alice.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(alice_player)
        await session.flush()
        alice_character = await make_character(
            session, tenant_id=tenant_id, name="Alice", owner_player_id=alice_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=alice_character.entity_id,
                player_id=alice_player.id,
                tenant_id=tenant_id,
            )
        )
        await session.flush()

        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=alice_character.entity_id,
                tenant_id=tenant_id,
            )
        )
        info = Information(
            tenant_id=tenant_id,
            entity_id=entity.id,
            title="A fiery blade",
            type="description",
            is_public=False,
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="The blade is cursed.",
            )
        )
        await session.commit()
        entity_id, alice_id = entity.id, alice.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert response.status_code == 200
    assert [d["content"] for d in response.json()["descriptions"]] == ["The blade is cursed."]

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, alice_id))
        await session.commit()


async def test_create_item_instance_self_service_with_owner_and_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The milestone's own creation shape: Ashfang prototypes Flaming Sword,
    owned by Alice, inside Alice's backpack - all in one call, self-service
    since the caller controls Alice.
    """
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id, "Flaming Sword")
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        backpack = Entity(tenant_id=tenant_id, name="Alice's Backpack")
        session.add(backpack)
        await session.commit()
        character_id, backpack_id = character.entity_id, backpack.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={
            "name": "Ashfang",
            "prototype_id": str(prototype_id),
            "owner_character_id": str(character_id),
            "container_entity_id": str(backpack_id),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["owner_entity_id"] == str(character_id)
    assert body["container_entity_id"] == str(backpack_id)
    assert response.headers["location"].endswith(
        f"/tenants/{tenant_id}/item-instances/{body['entity_id']}"
    )

    await delete_tenant(tenant_id)


async def test_create_item_instance_invalid_prototype_422(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_create_item_instance_with_slug_resolves_by_slug(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0043: a client can name an instance once at creation and resolve
    it again later by that name alone, with no need to have persisted its
    entity_id out-of-band.
    """
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id, "Flaming Sword")

    create_response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "slug": "ashfang"},
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["entity_id"]
    assert create_response.json()["slug"] == "ashfang"

    lookup_response = await client.get(f"/tenants/{tenant_id}/item-instances/by-slug/ashfang")
    assert lookup_response.status_code == 200
    assert lookup_response.json()["entity_id"] == entity_id

    await delete_tenant(tenant_id)


async def test_get_item_instance_by_slug_404_for_unknown_slug(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(f"/tenants/{tenant_id}/item-instances/by-slug/no-such-slug")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_create_item_instance_duplicate_slug_is_a_conflict(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id, "Flaming Sword")
    first = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "slug": "ashfang"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "slug": "ashfang"},
    )

    assert second.status_code == 409
    await delete_tenant(tenant_id)


async def test_get_item_instance_by_slug_404_for_a_slug_the_caller_cannot_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040's read-visibility predicate applies to the by-slug lookup
    too - a slug is just an alternate name for an instance, not a separate,
    unfiltered path into someone else's hidden inventory.
    """
    tenant_id = await make_tenant(test_user_id)
    _, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        bob_instance = await session.get_one(ItemInstance, bob_item_id)
        bob_instance.slug = "bobs-dagger"
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/by-slug/bobs-dagger")

    assert response.status_code == 404
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_create_item_instance_ownerless_forbidden_for_plain_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id)
    # test_user_id is tenant OWNER by default (make_tenant) - demote it to a
    # bare campaign participant with no GM/admin standing anywhere, so the
    # ownerless-creation tenant-wide fallback genuinely has nothing to grant.
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": str(prototype_id)}
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def test_create_item_instance_assign_to_other_character_requires_manage_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        # Bob, rostered into `campaign` by a different user entirely - Bob
        # needs a real Player row for campaign_ids_for_character to resolve
        # (RFC 0005's "at least one of that character's campaigns" rule
        # needs a campaign to check can_manage_campaign against at all),
        # but test_user_id doesn't control him.
        bob_owner = User(authgear_subject_id=f"bob-owner-{uuid.uuid4()}")
        session.add(bob_owner)
        await session.flush()
        bob_player = Player(user_id=bob_owner.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(bob_player)
        await session.flush()
        bob = await make_character(
            session, tenant_id=tenant_id, name="Bob", owner_player_id=bob_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=bob.entity_id, player_id=bob_player.id, tenant_id=tenant_id
            )
        )
        # Demote test_user_id from tenant OWNER to a bare participant.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        bob_id = bob.entity_id

    forbidden_response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "owner_character_id": str(bob_id)},
    )
    assert forbidden_response.status_code == 403

    # Grant test_user_id CampaignGm on Bob's campaign - now allowed.
    async with admin_session_factory() as session:
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))
        await session.commit()

    allowed_response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "owner_character_id": str(bob_id)},
    )
    assert allowed_response.status_code == 201
    assert allowed_response.json()["owner_entity_id"] == str(bob_id)

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_owner.id))
        await session.commit()


async def test_update_item_instance_self_service_rename(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        entity_id = entity.id

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}", json={"name": "Renamed Ashfang"}
    )

    assert response.status_code == 200
    # No description authored - title falls back to entity.name (ADR 0067),
    # so it reflects the rename too even though rename only ever touches
    # entity.name, never a description payload's own title.
    assert response.json()["title"] == "Renamed Ashfang"
    async with admin_session_factory() as session:
        updated_entity = await session.get_one(Entity, entity_id)
        assert updated_entity.name == "Renamed Ashfang"

    await delete_tenant(tenant_id)


async def test_update_item_instance_403_for_unrelated_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        # Owned by an unrelated character, no CampaignGm/admin standing.
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}", json={"name": "Stolen Sword"}
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def _make_bare_instance(tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def test_update_item_instance_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}",
        json={"name": "x"},
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412
    await delete_tenant(tenant_id)


async def test_get_item_instance_exposes_etag_and_updated_at_for_round_tripping(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0042: a client obtains its concurrency token purely from the HTTP
    response (either the ETag header or the updated_at field), closing the
    "If-Match is unusable, nothing hands out a token" gap - no direct DB
    access needed, unlike test_update_item_instance_precondition_failed_
    with_stale_if_match above (which only exercises the failure side).
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)

    get_response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert "updated_at" in body
    assert get_response.headers["etag"] == etag_for(datetime.fromisoformat(body["updated_at"]))

    patch_response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}",
        json={"name": "Ashfang, Renamed"},
        headers={"If-Match": get_response.headers["etag"]},
    )
    assert patch_response.status_code == 200
    assert "etag" in patch_response.headers
    assert patch_response.json()["updated_at"] != body["updated_at"]

    await delete_tenant(tenant_id)


async def test_delete_item_instance_self_service_removes_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)

    response = await client.delete(f"/tenants/{tenant_id}/item-instances/{entity_id}")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Entity, entity_id) is None

    await delete_tenant(tenant_id)


async def test_set_and_clear_item_instance_owner(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        await session.commit()
        character_id = character.entity_id

    set_response = await client.put(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/owner",
        json={"owner_character_id": str(character_id)},
    )
    assert set_response.status_code == 200
    assert set_response.json()["owner_entity_id"] == str(character_id)

    clear_response = await client.delete(f"/tenants/{tenant_id}/item-instances/{entity_id}/owner")
    assert clear_response.status_code == 200
    assert clear_response.json()["owner_entity_id"] is None

    await delete_tenant(tenant_id)


async def test_set_container_moves_item(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    """The milestone's own "Alice moves the sword into a chest" step."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        chest = Entity(tenant_id=tenant_id, name="Chest")
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add_all([backpack, chest, entity])
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Containment(
                child_entity_id=entity.id, parent_entity_id=backpack.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        entity_id, chest_id = entity.id, chest.id

    response = await client.put(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/container",
        json={"container_entity_id": str(chest_id)},
    )

    assert response.status_code == 200
    assert response.json()["container_entity_id"] == str(chest_id)

    clear_response = await client.delete(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/container"
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["container_entity_id"] is None

    await delete_tenant(tenant_id)


async def test_list_item_instances_404_for_non_participant(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/item-instances")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_update_item_instance_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/00000000-0000-0000-0000-000000000000",
        json={"name": "x"},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_create_item_instance_ownerless_allowed_for_tenant_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_item(tenant_id)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": str(prototype_id)}
    )

    assert response.status_code == 201
    assert response.json()["owner_entity_id"] is None
    await delete_tenant(tenant_id)


async def test_update_item_instance_allowed_for_gm_of_current_owners_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The GM-oversight tier of _authorize_instance_write: not self-service
    (test_user_id controls no characters here), but the entity's current
    owner (Bob) is rostered in a campaign test_user_id can manage.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        bob_owner = User(authgear_subject_id=f"bob-owner-{uuid.uuid4()}")
        session.add(bob_owner)
        await session.flush()
        bob_player = Player(user_id=bob_owner.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(bob_player)
        await session.flush()
        bob = await make_character(
            session, tenant_id=tenant_id, name="Bob", owner_player_id=bob_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=bob.entity_id, player_id=bob_player.id, tenant_id=tenant_id
            )
        )
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        await session.commit()
        entity_id, bob_owner_id = entity.id, bob_owner.id

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}", json={"name": "Renamed by GM"}
    )

    assert response.status_code == 200
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_owner_id))
        await session.commit()


async def test_update_item_instance_response_correct_even_when_caller_cannot_read_it_back(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040's own flagged edge case: test_user_id here manages Bob's
    item purely via the tenant OWNER bypass in can_manage_any_of_campaigns
    (no CampaignGm row, no ORGA role - the exact same fixture as
    test_update_item_instance_allowed_for_gm_of_current_owners_campaign
    above). The write must still return the correct, fully-populated body
    - _item_instance_out's post-write fetch deliberately does not apply
    the new read-visibility predicate, precisely to avoid a caller 404ing
    on the very write they just made. A fresh, independent GET afterwards
    does 404, though - proving the two are genuinely decoupled, not that
    the predicate silently never applies.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        bob_owner = User(authgear_subject_id=f"bob-owner-{uuid.uuid4()}")
        session.add(bob_owner)
        await session.flush()
        bob_player = Player(user_id=bob_owner.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(bob_player)
        await session.flush()
        bob = await make_character(
            session, tenant_id=tenant_id, name="Bob", owner_player_id=bob_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=bob.entity_id, player_id=bob_player.id, tenant_id=tenant_id
            )
        )
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        await session.commit()
        entity_id, bob_owner_id = entity.id, bob_owner.id

    patch_response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{entity_id}", json={"name": "Renamed by Owner"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["entity_id"] == str(entity_id)

    get_response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert get_response.status_code == 404

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_owner_id))
        await session.commit()


async def test_set_item_instance_owner_reassigns_existing_ownership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        # Alice already owns it (self-service, authorized against *current*
        # state) - reassigning to an unrelated character (Bob) still
        # succeeds, since self-or-managed never re-checks the new target
        # (RFC 0005: "giving it to a party member's character is all just
        # acting on your own stuff").
        alice = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        session.add(
            Ownership(
                owned_entity_id=entity_id, owner_character_id=alice.entity_id, tenant_id=tenant_id
            )
        )
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        await session.commit()
        bob_id = bob.entity_id

    response = await client.put(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/owner",
        json={"owner_character_id": str(bob_id)},
    )

    assert response.status_code == 200
    assert response.json()["owner_entity_id"] == str(bob_id)
    await delete_tenant(tenant_id)


async def test_set_item_instance_container_when_none_existed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        session.add(
            Ownership(
                owned_entity_id=entity_id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        await session.commit()
        chest_id = chest.id

    response = await client.put(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/container",
        json={"container_entity_id": str(chest_id)},
    )

    assert response.status_code == 200
    assert response.json()["container_entity_id"] == str(chest_id)
    await delete_tenant(tenant_id)


async def _make_stacked_instance(
    tenant_id: uuid.UUID, *, test_user_id: uuid.UUID, quantity: int
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A stack of `quantity` arrows, owned by test_user_id's own character,
    contained in a backpack - ADR 0041's own split fixture shape. Returns
    (entity_id, character_id, container_id).
    """
    prototype_id = await _make_item(tenant_id, "Arrow")
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        entity = Entity(tenant_id=tenant_id, name="Arrows")
        session.add_all([backpack, entity])
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            EntityPrototype(entity_id=entity.id, prototype_id=prototype_id, tenant_id=tenant_id)
        )
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Containment(
                child_entity_id=entity.id,
                parent_entity_id=backpack.id,
                tenant_id=tenant_id,
                quantity=quantity,
            )
        )
        await session.commit()
        return entity.id, character.entity_id, backpack.id


async def test_split_item_instance_creates_new_stack_and_decrements_source(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, character_id, backpack_id = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=20
    )

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split", json={"quantity": 12}
    )

    assert response.status_code == 201
    new_body = response.json()
    assert new_body["quantity"] == 12
    assert new_body["container_entity_id"] == str(backpack_id)
    assert new_body["owner_entity_id"] == str(character_id)
    new_entity_id = new_body["entity_id"]
    assert new_entity_id != str(entity_id)
    assert response.headers["location"].endswith(
        f"/tenants/{tenant_id}/item-instances/{new_entity_id}"
    )

    source_response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert source_response.status_code == 200
    assert source_response.json()["quantity"] == 8

    await delete_tenant(tenant_id)


async def test_split_item_instance_422_when_quantity_not_less_than_stack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, _ = await _make_stacked_instance(tenant_id, test_user_id=test_user_id, quantity=5)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split", json={"quantity": 5}
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_split_item_instance_422_when_uncontained(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_instance(tenant_id)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split", json={"quantity": 1}
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_split_item_instance_403_for_unrelated_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        entity = Entity(tenant_id=tenant_id, name="Arrows")
        session.add_all([backpack, entity])
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        session.add(
            Containment(
                child_entity_id=entity.id,
                parent_entity_id=backpack.id,
                tenant_id=tenant_id,
                quantity=10,
            )
        )
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split", json={"quantity": 4}
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def test_split_item_instance_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/00000000-0000-0000-0000-000000000000/split",
        json={"quantity": 1},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_split_item_instance_with_owner_assigns_new_owner(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0044: the split-off piece goes to owner_character_id when given,
    instead of copying the source's own current owner.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id, character_id, backpack_id = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=20
    )
    async with admin_session_factory() as session:
        other_character = await make_character(session, tenant_id=tenant_id, name="Other")
        await session.commit()
        other_character_id = other_character.entity_id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split",
        json={"quantity": 12, "owner_character_id": str(other_character_id)},
    )

    assert response.status_code == 201
    new_body = response.json()
    assert new_body["owner_entity_id"] == str(other_character_id)
    assert new_body["owner_entity_id"] != str(character_id)
    assert new_body["container_entity_id"] == str(backpack_id)

    await delete_tenant(tenant_id)


async def test_merge_item_instance_combines_stacks_and_deletes_source(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, character_id, backpack_id = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=5
    )
    split_response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/split", json={"quantity": 3}
    )
    assert split_response.status_code == 201
    other_entity_id = split_response.json()["entity_id"]

    merge_response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": other_entity_id},
    )

    assert merge_response.status_code == 200
    merged = merge_response.json()
    assert merged["entity_id"] == other_entity_id
    assert merged["quantity"] == 5
    assert merged["owner_entity_id"] == str(character_id)
    assert merged["container_entity_id"] == str(backpack_id)

    gone_response = await client.get(f"/tenants/{tenant_id}/item-instances/{entity_id}")
    assert gone_response.status_code == 404

    await delete_tenant(tenant_id)


async def test_merge_item_instance_422_into_itself(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, _ = await _make_stacked_instance(tenant_id, test_user_id=test_user_id, quantity=5)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": str(entity_id)},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_merge_item_instance_422_uncontained_target(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, character_id, _ = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=5
    )
    async with admin_session_factory() as session:
        uncontained = Entity(tenant_id=tenant_id, name="Loose Arrows")
        session.add(uncontained)
        await session.flush()
        session.add(ItemInstance(entity_id=uncontained.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=uncontained.id,
                owner_character_id=character_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        uncontained_id = uncontained.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": str(uncontained_id)},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_merge_item_instance_422_different_containers(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, character_id, _ = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=5
    )
    async with admin_session_factory() as session:
        other_backpack = Entity(tenant_id=tenant_id, name="Other Backpack")
        other_entity = Entity(tenant_id=tenant_id, name="Other Arrows")
        session.add_all([other_backpack, other_entity])
        await session.flush()
        session.add(ItemInstance(entity_id=other_entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=other_entity.id,
                owner_character_id=character_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Containment(
                child_entity_id=other_entity.id,
                parent_entity_id=other_backpack.id,
                tenant_id=tenant_id,
                quantity=2,
            )
        )
        await session.commit()
        other_entity_id = other_entity.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": str(other_entity_id)},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_merge_item_instance_422_different_owners(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, backpack_id = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=5
    )
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Other Campaign")
        await session.flush()
        other_character = await make_character(session, tenant_id=tenant_id, name="Other")
        # other_character needs *some* campaign standing, or
        # _authorize_instance_write 403s on it before this test ever
        # reaches the different-owners guard it means to exercise -
        # test_user_id's own tenant OWNER role (make_tenant's default)
        # then covers it via can_manage_campaign's OWNER/ORGA bypass
        # (ADR 0032), same as it would for any other campaign in this
        # tenant.
        dummy_user = User(authgear_subject_id=f"dummy-{uuid.uuid4()}")
        session.add(dummy_user)
        await session.flush()
        dummy_player = Player(user_id=dummy_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(dummy_player)
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=other_character.entity_id,
                player_id=dummy_player.id,
                tenant_id=tenant_id,
            )
        )
        other_entity = Entity(tenant_id=tenant_id, name="Other Arrows")
        session.add(other_entity)
        await session.flush()
        session.add(ItemInstance(entity_id=other_entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=other_entity.id,
                owner_character_id=other_character.entity_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Containment(
                child_entity_id=other_entity.id,
                parent_entity_id=backpack_id,
                tenant_id=tenant_id,
                quantity=2,
            )
        )
        await session.commit()
        other_entity_id = other_entity.id
        dummy_user_id = dummy_user.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": str(other_entity_id)},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, dummy_user_id))
        await session.commit()


async def test_merge_item_instance_404_for_unknown_target(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, _ = await _make_stacked_instance(tenant_id, test_user_id=test_user_id, quantity=5)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/{entity_id}/merge",
        json={"into_entity_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_bulk_assign_reports_mixed_outcomes_without_failing_the_batch(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0044: never all-or-nothing - a stale If-Match on one item, and an
    unrelated player's item with no standing, don't stop the rest of the
    batch from applying and being reported "ok".
    """
    tenant_id = await make_tenant(test_user_id)
    ok_entity_id, _, _ = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=10
    )
    _, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        other_character = await make_character(session, tenant_id=tenant_id, name="Recipient")
        # Downgrade test_user_id away from make_tenant's default tenant
        # OWNER role - can_manage_campaign's own bypass (ADR 0032) lets
        # OWNER/ORGA manage *any* campaign's items, which would otherwise
        # make bob_item_id succeed too and defeat this test's whole point.
        # Self-management of ok_entity_id (via its own Player/CharacterPlayer
        # rows, unrelated to Membership) is unaffected by this downgrade -
        # mirrors test_split_item_instance_403_for_unrelated_player's own
        # identical setup.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()
        recipient_id = other_character.entity_id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(ok_entity_id),
                "owner_character_id": str(recipient_id),
                "quantity": 4,
            },
            {
                "entity_id": str(ok_entity_id),
                "owner_character_id": str(recipient_id),
                "if_match": 'W/"stale"',
            },
            {"entity_id": str(bob_item_id), "owner_character_id": str(recipient_id)},
        ],
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 3
    assert results[0]["status"] == "ok"
    assert results[0]["item_instance"]["owner_entity_id"] == str(recipient_id)
    assert results[0]["item_instance"]["quantity"] == 4
    assert results[1]["status"] == "error"
    assert results[1]["problem"]["status"] == 412
    assert results[2]["status"] == "error"
    assert results[2]["problem"]["status"] == 403

    # The successful item really did apply, despite the other two failing.
    source_response = await client.get(f"/tenants/{tenant_id}/item-instances/{ok_entity_id}")
    assert source_response.json()["quantity"] == 6

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_bulk_assign_without_quantity_reassigns_whole_instance(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0044: quantity omitted delegates to the plain owner-PUT path
    (_perform_set_owner), reassigning entity_id itself rather than
    splitting a piece off it.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, _ = await _make_stacked_instance(tenant_id, test_user_id=test_user_id, quantity=1)
    async with admin_session_factory() as session:
        recipient = await make_character(session, tenant_id=tenant_id, name="Recipient")
        await session.commit()
        recipient_id = recipient.entity_id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-assign",
        json=[{"entity_id": str(entity_id), "owner_character_id": str(recipient_id)}],
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["entity_id"] == str(entity_id)
    assert results[0]["item_instance"]["entity_id"] == str(entity_id)
    assert results[0]["item_instance"]["owner_entity_id"] == str(recipient_id)

    await delete_tenant(tenant_id)


async def _make_two_stacked_instances_in_same_container(
    tenant_id: uuid.UUID, *, test_user_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Two owned item instances contained in the *same* backpack - what
    bulk-move's from_container_entity_id mode needs to move more than one
    at once. Returns (backpack_id, entity_id_1, entity_id_2).
    """
    prototype_id = await _make_item(tenant_id, "Coin")
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        entity_1 = Entity(tenant_id=tenant_id, name="Coin A")
        entity_2 = Entity(tenant_id=tenant_id, name="Coin B")
        session.add_all([backpack, entity_1, entity_2])
        await session.flush()
        session.add_all(
            [
                ItemInstance(entity_id=entity_1.id, tenant_id=tenant_id),
                ItemInstance(entity_id=entity_2.id, tenant_id=tenant_id),
            ]
        )
        session.add_all(
            [
                EntityPrototype(
                    entity_id=entity_1.id, prototype_id=prototype_id, tenant_id=tenant_id
                ),
                EntityPrototype(
                    entity_id=entity_2.id, prototype_id=prototype_id, tenant_id=tenant_id
                ),
            ]
        )
        session.add_all(
            [
                Ownership(
                    owned_entity_id=entity_1.id,
                    owner_character_id=character.entity_id,
                    tenant_id=tenant_id,
                ),
                Ownership(
                    owned_entity_id=entity_2.id,
                    owner_character_id=character.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        session.add_all(
            [
                Containment(
                    child_entity_id=entity_1.id, parent_entity_id=backpack.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=entity_2.id, parent_entity_id=backpack.id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()
        return backpack.id, entity_1.id, entity_2.id


async def test_bulk_move_from_container_moves_every_direct_child(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0065: from_container_entity_id resolves to every item instance
    directly contained there, moving each into to_container_entity_id in
    one call.
    """
    tenant_id = await make_tenant(test_user_id)
    backpack_id, entity_1, entity_2 = await _make_two_stacked_instances_in_same_container(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        await session.commit()
        chest_id = chest.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={
            "to_container_entity_id": str(chest_id),
            "from_container_entity_id": str(backpack_id),
        },
    )

    assert response.status_code == 200
    results = {r["entity_id"]: r for r in response.json()}
    assert len(results) == 2
    for entity_id in (str(entity_1), str(entity_2)):
        assert results[entity_id]["status"] == "ok"
        assert results[entity_id]["item_instance"]["container_entity_id"] == str(chest_id)

    await delete_tenant(tenant_id)


async def test_bulk_move_with_explicit_items_list(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0065: the items mode moves exactly the given list, quantity
    riding along untouched (a move isn't a split, ADR 0041).
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id, _, _ = await _make_stacked_instance(tenant_id, test_user_id=test_user_id, quantity=3)
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        await session.commit()
        chest_id = chest.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={"to_container_entity_id": str(chest_id), "items": [{"entity_id": str(entity_id)}]},
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["item_instance"]["container_entity_id"] == str(chest_id)
    assert results[0]["item_instance"]["quantity"] == 3

    await delete_tenant(tenant_id)


async def test_bulk_move_reports_mixed_outcomes_without_failing_the_batch(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0065: never all-or-nothing - an unrelated player's item with no
    standing doesn't stop the rest of the batch, mirroring bulk-assign's
    identical mixed-outcome precedent (ADR 0044).
    """
    tenant_id = await make_tenant(test_user_id)
    ok_entity_id, _, _ = await _make_stacked_instance(
        tenant_id, test_user_id=test_user_id, quantity=1
    )
    _, _, _, bob_item_id, _, bob_user_id = await _make_cross_owner_fixture(
        tenant_id, test_user_id=test_user_id
    )
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        # Downgrade test_user_id away from make_tenant's default tenant
        # OWNER role - can_manage_campaign's own bypass would otherwise let
        # bob_item_id succeed too and defeat this test's whole point,
        # mirroring test_bulk_assign_reports_mixed_outcomes_without_
        # failing_the_batch's identical setup.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()
        chest_id = chest.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={
            "to_container_entity_id": str(chest_id),
            "items": [{"entity_id": str(ok_entity_id)}, {"entity_id": str(bob_item_id)}],
        },
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["status"] == "ok"
    assert results[0]["item_instance"]["container_entity_id"] == str(chest_id)
    assert results[1]["status"] == "error"
    assert results[1]["problem"]["status"] == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_bulk_move_requires_exactly_one_source_mode(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0065: from_container_entity_id/items is a request-shape
    invariant (Pydantic's own model_validator, not a typed Problem) -
    neither given, or both given, is a plain 422.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        await session.commit()
        chest_id = chest.id

    neither = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={"to_container_entity_id": str(chest_id)},
    )
    assert neither.status_code == 422

    both = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={
            "to_container_entity_id": str(chest_id),
            "from_container_entity_id": str(chest_id),
            "items": [],
        },
    )
    assert both.status_code == 422

    await delete_tenant(tenant_id)


async def test_bulk_move_404_for_unknown_destination_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={
            "to_container_entity_id": "00000000-0000-0000-0000-000000000000",
            "items": [],
        },
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_bulk_move_404_for_unknown_source_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=tenant_id, name="Chest")
        session.add(chest)
        await session.commit()
        chest_id = chest.id

    response = await client.post(
        f"/tenants/{tenant_id}/item-instances/bulk-move",
        json={
            "to_container_entity_id": str(chest_id),
            "from_container_entity_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)
