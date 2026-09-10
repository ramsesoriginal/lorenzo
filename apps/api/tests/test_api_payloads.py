import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    CharacterPlayer,
    Entity,
    Information,
    Knowledge,
    Membership,
    MembershipRole,
    Payload,
    PayloadDocument,
    PayloadPicture,
    Player,
    Tenant,
)


async def test_get_picture_content_returns_bytes_with_correct_content_type(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(
            tenant_id=tenant.id, entity_id=entity.id, title="x", type="description", is_public=True
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=payload.id,
                tenant_id=tenant.id,
                data=b"\x89PNG\r\n\x1a\n",
                file_type="image/png",
            )
        )
        await session.commit()
        tenant_id, payload_id = tenant.id, payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG\r\n\x1a\n"

    await delete_tenant(tenant_id)


async def test_get_document_content_returns_bytes_with_content_disposition(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(
            tenant_id=tenant.id, entity_id=entity.id, title="x", type="description", is_public=True
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDocument(
                payload_id=payload.id,
                tenant_id=tenant.id,
                data=b"%PDF-1.4",
                filename="appraisal.pdf",
                file_type="application/pdf",
            )
        )
        await session.commit()
        tenant_id, payload_id = tenant.id, payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="appraisal.pdf"'
    assert response.content == b"%PDF-1.4"

    await delete_tenant(tenant_id)


async def test_get_document_content_encodes_non_ascii_filename(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(
            tenant_id=tenant.id, entity_id=entity.id, title="x", type="description", is_public=True
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDocument(
                payload_id=payload.id,
                tenant_id=tenant.id,
                data=b"data",
                filename="rapport-été.pdf",
                file_type="application/pdf",
            )
        )
        await session.commit()
        tenant_id, payload_id = tenant.id, payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")

    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == "attachment; filename*=utf-8''rapport-%C3%A9t%C3%A9.pdf"
    )

    await delete_tenant(tenant_id)


async def test_get_content_404_when_payload_has_no_binary_content(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Nothing enforces "exactly one concrete kind" on Payload (ADR 0019) -
    a bare row with neither .picture nor .document must 404, not 500.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(
            tenant_id=tenant.id, entity_id=entity.id, title="x", type="description", is_public=True
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add(payload)
        await session.commit()
        tenant_id, payload_id = tenant.id, payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")

    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_get_content_404_for_unknown_payload(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/payloads/00000000-0000-0000-0000-000000000000/content"
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_content_404_for_wrong_tenant(
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
        entity = Entity(tenant_id=tenant_a.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(
            tenant_id=tenant_a.id, entity_id=entity.id, title="x", type="description"
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_a.id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=payload.id, tenant_id=tenant_a.id, data=b"x", file_type="image/png"
            )
        )
        await session.commit()
        tenant_a_id, tenant_b_id, payload_id = tenant_a.id, tenant_b.id, payload.id

    # Payload exists, but under tenant_a - requesting it via tenant_b's
    # path must 404, not leak content across tenants.
    response = await client.get(f"/tenants/{tenant_b_id}/payloads/{payload_id}/content")
    assert response.status_code == 404

    await delete_tenant(tenant_a_id)
    await delete_tenant(tenant_b_id)


async def test_get_content_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/payloads/"
        "00000000-0000-0000-0000-000000000000/content"
    )
    assert response.status_code == 404


async def test_get_content_404_for_gm_only_information_not_visible_to_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The core regression test (ADR 0028's addendum): a payload whose
    Information has no is_public and no Knowledge row is GM-only by
    default - a plain member must get the same 404 as a genuinely unknown
    payload, not the actual bytes.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(tenant_id=tenant.id, entity_id=entity.id, title="x", type="gm-note")
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=payload.id,
                tenant_id=tenant.id,
                data=b"\x89PNG\r\n\x1a\n",
                file_type="image/png",
            )
        )
        await session.commit()
        tenant_id, payload_id = tenant.id, payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_get_content_visible_via_knowledge_for_the_callers_own_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Proves the real Campaign/Player/Being/CharacterPlayer/Knowledge
    chain grants access to the payload bytes too, not just to
    GET /entities/{id}'s JSON body.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        character = Entity(tenant_id=tenant_id, name="Character")
        subject = Entity(tenant_id=tenant_id, name="Sword")
        session.add_all([character, subject])
        await session.flush()
        session.add(Being(entity_id=character.id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=character.id, player_id=player.id, tenant_id=tenant_id
            )
        )
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="x", type="gm-note")
        session.add(info)
        await session.flush()
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=character.id, information_id=info.id)
        )
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=payload.id, tenant_id=tenant_id, data=b"x", file_type="image/png"
            )
        )
        await session.commit()
        payload_id = payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")
    assert response.status_code == 200
    assert response.content == b"x"

    await delete_tenant(tenant_id)


async def test_get_content_orga_sees_everything_regardless_of_knowledge(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=entity.id, title="x", type="gm-note")
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=payload.id, tenant_id=tenant_id, data=b"x", file_type="image/png"
            )
        )
        await session.commit()
        payload_id = payload.id

    response = await client.get(f"/tenants/{tenant_id}/payloads/{payload_id}/content")
    assert response.status_code == 200
    assert response.content == b"x"

    await delete_tenant(tenant_id)
