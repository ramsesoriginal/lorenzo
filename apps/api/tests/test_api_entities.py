import uuid
from decimal import Decimal

from _admin_db import admin_session_factory
from httpx import AsyncClient

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
    Information,
    Membership,
    MembershipRole,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)


async def test_list_entities_returns_paginated_summaries_ordered_by_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        session.add_all(
            [
                Entity(tenant_id=tenant.id, name="Charlie"),
                Entity(tenant_id=tenant.id, name="Alpha"),
                Entity(tenant_id=tenant.id, name="Bravo"),
            ]
        )
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"page": 1, "size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["size"] == 2
    assert body["pages"] == 2
    assert [item["name"] for item in body["items"]] == ["Alpha", "Bravo"]

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"page": 2, "size": 2})
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Charlie"]

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_list_entities_only_returns_the_requesting_tenants_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=tenant_a.id, user_id=test_user_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b.id, user_id=test_user_id, role=MembershipRole.OWNER),
            ]
        )
        session.add(Entity(tenant_id=tenant_a.id, name="Tenant A Entity"))
        session.add(Entity(tenant_id=tenant_b.id, name="Tenant B Entity"))
        await session.commit()
        tenant_a_id, tenant_b_id = tenant_a.id, tenant_b.id

    response = await client.get(f"/tenants/{tenant_a_id}/entities")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Tenant A Entity"]

    response = await client.get(f"/tenants/{tenant_b_id}/entities")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Tenant B Entity"]

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_a_id))
        await session.delete(await session.get_one(Tenant, tenant_b_id))
        await session.commit()


async def test_list_entities_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000/entities")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


async def test_get_entity_returns_full_detail_with_every_relationship_resolved(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """One entity wired up with all four StatDefinition.value_types, all
    four Payload kinds (with one Information row bundling two heterogeneous
    kinds - a real fixture fact, confirmed in test_v_item.py, not assumed),
    a prototype/instance pair, and a parent/child pair.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        main = Entity(tenant_id=tenant_id, name="Main Entity")
        proto = Entity(tenant_id=tenant_id, name="Proto Entity")
        instance = Entity(tenant_id=tenant_id, name="Instance Entity")
        parent = Entity(tenant_id=tenant_id, name="Parent Entity")
        child = Entity(tenant_id=tenant_id, name="Child Entity")
        session.add_all([main, proto, instance, parent, child])
        await session.flush()

        session.add_all(
            [
                EntityPrototype(entity_id=main.id, prototype_id=proto.id, tenant_id=tenant_id),
                EntityPrototype(entity_id=instance.id, prototype_id=main.id, tenant_id=tenant_id),
                Containment(
                    child_entity_id=main.id, parent_entity_id=parent.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=child.id, parent_entity_id=main.id, tenant_id=tenant_id
                ),
            ]
        )

        stat_group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(stat_group)
        await session.flush()
        session.add(
            EntityStatGroup(entity_id=main.id, stat_group_id=stat_group.id, tenant_id=tenant_id)
        )

        weight_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        label_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="label",
            value_type=StatValueType.TEXT,
        )
        sharpness_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="sharpness",
            value_type=StatValueType.FLOAT,
        )
        magical_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="is_magical",
            value_type=StatValueType.BOOL,
        )
        session.add_all([weight_def, label_def, sharpness_def, magical_def])
        await session.flush()

        session.add_all(
            [
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=weight_def.id,
                    tenant_id=tenant_id,
                    value_int=3,
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=label_def.id,
                    tenant_id=tenant_id,
                    value_text="sharp",
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=sharpness_def.id,
                    tenant_id=tenant_id,
                    value_float=9.5,
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=magical_def.id,
                    tenant_id=tenant_id,
                    value_bool=True,
                ),
            ]
        )

        # Information #1: description + picture as sibling payloads under
        # the *same* information_id - the mixed-kinds-per-row fixture fact.
        info1 = Information(
            tenant_id=tenant_id, entity_id=main.id, title="A fine sword", type="description"
        )
        session.add(info1)
        await session.flush()
        description_payload = Payload(tenant_id=tenant_id, information_id=info1.id)
        picture_payload = Payload(tenant_id=tenant_id, information_id=info1.id)
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
                data=b"\x89PNG\r\n\x1a\n",
                file_type="image/png",
            )
        )

        # Information #2: number + document, rounding out all four payload
        # kinds across the entity's information as a whole.
        info2 = Information(
            tenant_id=tenant_id, entity_id=main.id, title="Appraisal", type="gm-note"
        )
        session.add(info2)
        await session.flush()
        number_payload = Payload(tenant_id=tenant_id, information_id=info2.id)
        document_payload = Payload(tenant_id=tenant_id, information_id=info2.id)
        session.add_all([number_payload, document_payload])
        await session.flush()
        session.add(
            PayloadNumber(payload_id=number_payload.id, tenant_id=tenant_id, value=Decimal("42.5"))
        )
        session.add(
            PayloadDocument(
                payload_id=document_payload.id,
                tenant_id=tenant_id,
                data=b"%PDF-1.4",
                filename="appraisal.pdf",
                file_type="application/pdf",
            )
        )

        await session.commit()
        main_id, picture_payload_id, document_payload_id = (
            main.id,
            picture_payload.id,
            document_payload.id,
        )

    response = await client.get(f"/tenants/{tenant_id}/entities/{main_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == str(main_id)
    assert body["name"] == "Main Entity"
    assert body["created_at"]
    assert body["updated_at"]

    stats = {s["name"]: s["value"] for s in body["stats"]}
    assert stats == {"weight": 3, "label": "sharp", "sharpness": 9.5, "is_magical": True}

    assert [g["name"] for g in body["stat_groups"]] == ["physical"]

    information_by_type = {info["type"]: info for info in body["information"]}
    assert set(information_by_type) == {"description", "gm-note"}

    description_info = information_by_type["description"]
    assert description_info["title"] == "A fine sword"
    payloads_by_kind = {p["kind"]: p for p in description_info["payloads"]}
    assert set(payloads_by_kind) == {"description", "picture"}
    assert payloads_by_kind["description"]["content"] == "A gleaming blade."
    assert payloads_by_kind["description"]["locale"] == "en-US"
    assert payloads_by_kind["picture"]["file_type"] == "image/png"
    assert payloads_by_kind["picture"]["url"].endswith(
        f"/tenants/{tenant_id}/payloads/{picture_payload_id}/content"
    )

    gm_note_info = information_by_type["gm-note"]
    payloads_by_kind = {p["kind"]: p for p in gm_note_info["payloads"]}
    assert set(payloads_by_kind) == {"number", "document"}
    assert payloads_by_kind["number"]["value"] == "42.5"
    assert payloads_by_kind["document"]["filename"] == "appraisal.pdf"
    assert payloads_by_kind["document"]["url"].endswith(
        f"/tenants/{tenant_id}/payloads/{document_payload_id}/content"
    )

    assert [e["name"] for e in body["prototypes"]] == ["Proto Entity"]
    assert [e["name"] for e in body["instances"]] == ["Instance Entity"]
    assert body["parent"] is not None
    assert body["parent"]["name"] == "Parent Entity"
    assert [e["name"] for e in body["children"]] == ["Child Entity"]

    # The picture/document URLs must actually resolve, through the
    # already-existing payload_content route - confirms url_for's route
    # name matches, not just that a plausible-looking string was built.
    content_response = await client.get(payloads_by_kind["document"]["url"])
    assert content_response.status_code == 200
    assert content_response.content == b"%PDF-1.4"

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_get_entity_404_for_unknown_entity_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(
        f"/tenants/{tenant_id}/entities/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_get_entity_404_for_entity_belonging_to_a_different_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Membership on *both* tenants, deliberately - the 404 here must be
    about the entity belonging to a different tenant, not merely about
    missing membership in tenant_b (a different, already-covered case).
    """
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=tenant_a.id, user_id=test_user_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b.id, user_id=test_user_id, role=MembershipRole.OWNER),
            ]
        )
        entity = Entity(tenant_id=tenant_a.id, name="Tenant A's Entity")
        session.add(entity)
        await session.commit()
        tenant_a_id, tenant_b_id, entity_id = tenant_a.id, tenant_b.id, entity.id

    # Entity exists, but under tenant_a - requesting it via tenant_b's path
    # must 404, not leak it across tenants.
    response = await client.get(f"/tenants/{tenant_b_id}/entities/{entity_id}")
    assert response.status_code == 404

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_a_id))
        await session.delete(await session.get_one(Tenant, tenant_b_id))
        await session.commit()


async def test_get_entity_404_for_unknown_tenant_id(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/entities/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
