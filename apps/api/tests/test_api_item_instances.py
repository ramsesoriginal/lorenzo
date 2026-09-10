import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Containment,
    Entity,
    Information,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    Payload,
    PayloadDescription,
    Tenant,
)


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
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

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


async def test_get_item_instance_hides_gm_only_description_from_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Same information-visibility fix as items.py/entities.py/payloads.py
    (ADR 0028's addendum), confirmed wired up here too - the underlying
    mechanism (ItemViewMixin/eager_load_options) is shared with items.py
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
