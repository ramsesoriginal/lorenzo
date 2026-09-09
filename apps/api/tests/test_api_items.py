import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityStat,
    Information,
    Item,
    Membership,
    MembershipRole,
    Payload,
    PayloadDescription,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)


async def _make_item_with_description(
    tenant_id: uuid.UUID, *, is_public: bool
) -> tuple[uuid.UUID, uuid.UUID]:
    """Minimal fixture for information-visibility tests below - just an
    item with one description, no stats/picture/container. Returns
    (entity_id, information_id).
    """
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        info = Information(
            tenant_id=tenant_id,
            entity_id=entity.id,
            title="A fine sword",
            type="description",
            is_public=is_public,
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
        return entity.id, info.id


async def _make_bare_item(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _make_full_item(
    tenant_id: uuid.UUID, name: str = "Sword", container_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """A base item with a description, a picture, and stats spanning the
    physical and tags groups - mirrors tests/test_v_item.py's own fixture
    shape so the API's wrapped schema can be checked end to end against a
    known-good source of truth. Returns (entity_id, picture_payload_id).
    """
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        if container_id is not None:
            session.add(
                Containment(
                    child_entity_id=entity.id, parent_entity_id=container_id, tenant_id=tenant_id
                )
            )

        physical = StatGroup(tenant_id=tenant_id, name="physical")
        tags = StatGroup(tenant_id=tenant_id, name="tags")
        session.add_all([physical, tags])
        await session.flush()
        weight_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=physical.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        magical_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=tags.id,
            name="is_magical",
            value_type=StatValueType.BOOL,
        )
        session.add_all([weight_def, magical_def])
        await session.flush()
        session.add(
            EntityStat(
                entity_id=entity.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant_id,
                value_int=3,
            )
        )
        session.add(
            EntityStat(
                entity_id=entity.id,
                stat_definition_id=magical_def.id,
                tenant_id=tenant_id,
                value_bool=True,
            )
        )

        info = Information(
            tenant_id=tenant_id,
            entity_id=entity.id,
            title="A fine sword",
            type="description",
            is_public=True,
        )
        session.add(info)
        await session.flush()
        description_payload = Payload(tenant_id=tenant_id, information_id=info.id)
        picture_payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add_all([description_payload, picture_payload])
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=description_payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="A gleaming blade.",
            )
        )
        session.add(
            PayloadPicture(
                payload_id=picture_payload.id,
                tenant_id=tenant_id,
                data=b"\x89PNG",
                file_type="image/png",
            )
        )
        await session.commit()
        return entity.id, picture_payload.id


async def test_get_item_returns_full_wrapped_shape(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    # Any entity works as a container - it need not itself be item-tagged.
    chest_id = await _make_bare_item(tenant_id, "irrelevant-marker")
    entity_id, picture_payload_id = await _make_full_item(tenant_id, container_id=chest_id)

    response = await client.get(f"/tenants/{tenant_id}/items/{entity_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == str(entity_id)
    assert body["title"] == "A fine sword"
    assert body["weight"] == 3
    assert body["height"] is None
    assert body["is_magical"] is True
    assert body["is_cursed"] is None
    assert body["container_entity_id"] == str(chest_id)
    assert body["descriptions"] == [{"content": "A gleaming blade.", "locale": "en-US"}]
    assert len(body["pictures"]) == 1
    assert body["pictures"][0]["file_type"] == "image/png"
    # Never inline picture bytes into a (paginated) list-shaped response -
    # a url pointing at the existing payload-content endpoint instead,
    # consistent with how the Entities endpoint represents the same
    # underlying data (schemas/payloads.py's PayloadPictureOut). Confirm
    # the url actually resolves, not just that a plausible string was built.
    assert body["pictures"][0]["url"].endswith(
        f"/tenants/{tenant_id}/payloads/{picture_payload_id}/content"
    )
    content_response = await client.get(body["pictures"][0]["url"])
    assert content_response.status_code == 200
    assert content_response.content == b"\x89PNG"
    assert body["physical_stats"] == [{"name": "weight", "value": 3}]
    assert body["tags"] == [{"name": "is_magical", "value": True}]
    assert body["economic_stats"] == []
    assert body["destroyable_stats"] == []
    assert body["damaging_stats"] == []

    await delete_tenant(tenant_id)


async def test_get_item_hides_gm_only_description_from_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The same information-visibility gap fixed for GET /entities/{id} and
    GET /payloads/{id}/content (ADR 0028's addendum) - confirmed to exist
    here too and fixed the same way: a description with no is_public and
    no Knowledge row is GM-only by default and must not appear here.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id, _ = await _make_item_with_description(tenant_id, is_public=False)

    response = await client.get(f"/tenants/{tenant_id}/items/{entity_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["descriptions"] == []
    assert body["pictures"] == []

    await delete_tenant(tenant_id)


async def test_get_item_orga_sees_gm_only_description(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
    entity_id, _ = await _make_item_with_description(tenant_id, is_public=False)

    response = await client.get(f"/tenants/{tenant_id}/items/{entity_id}")
    assert response.status_code == 200
    assert response.json()["descriptions"] == [{"content": "A gleaming blade.", "locale": "en-US"}]

    await delete_tenant(tenant_id)


async def test_list_items_hides_gm_only_description_from_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Proves the visibility check is applied per-item in the paginated
    list too, not only on the single-item GET.
    """
    tenant_id = await make_tenant(test_user_id)
    await _make_item_with_description(tenant_id, is_public=False)

    response = await client.get(f"/tenants/{tenant_id}/items")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["descriptions"] == []

    await delete_tenant(tenant_id)


async def test_get_item_404_for_unknown_id(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(f"/tenants/{tenant_id}/items/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_item_404_for_wrong_tenant(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    # Membership on *both* tenants, deliberately - the 404 here must be
    # about the item belonging to a different tenant, not merely about
    # missing membership in tenant_b (a different, already-covered case).
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    entity_id = await _make_bare_item(tenant_a, "Sword")

    # Item exists, but under tenant_a - requesting it via tenant_b's path
    # must 404, not leak it across tenants.
    response = await client.get(f"/tenants/{tenant_b}/items/{entity_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_get_item_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/items/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


async def test_list_items_paginates_and_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    sword_id = await _make_bare_item(tenant_a, "Sword")
    shield_id = await _make_bare_item(tenant_a, "Shield")
    await _make_bare_item(tenant_b, "Other tenant's item")

    response = await client.get(f"/tenants/{tenant_a}/items")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    returned_ids = {item["entity_id"] for item in body["items"]}
    assert returned_ids == {str(sword_id), str(shield_id)}

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_list_items_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000/items")
    assert response.status_code == 404
