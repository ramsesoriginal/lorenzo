import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    CharacterPlayer,
    Entity,
    Membership,
    MembershipRole,
    Player,
    Tenant,
)


async def test_list_characters_only_includes_promoted_beings(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0031/RFC 0004: specifically a roster of Character rows, not
    every Being - a bare being with no character row doesn't appear here.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        # A bare being, no Character row - must not appear below.
        npc_entity = Entity(tenant_id=tenant_id, name="Unnamed Goblin")
        session.add(npc_entity)
        await session.flush()
        session.add(Being(entity_id=npc_entity.id, tenant_id=tenant_id))
        await session.commit()
        character_id = character.entity_id

    response = await client.get(f"/tenants/{tenant_id}/characters")
    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body["items"]] == ["Alice"]
    assert body["items"][0]["entity_id"] == str(character_id)
    assert body["items"][0]["is_pc"] is False

    await delete_tenant(tenant_id)


async def test_get_character_detail_reports_owner_and_players(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """CharacterOut.players reuses PlayerSummaryOut whole - the accepted
    minor redundancy where the returned player entry re-includes the very
    character being viewed (ADR 0031/RFC 0004).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        character = await make_character(
            session, tenant_id=tenant_id, name="Alice", owner_player_id=player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    response = await client.get(f"/tenants/{tenant_id}/characters/{character_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alice"
    assert body["is_pc"] is True
    assert body["owner_player_id"] == str(player_id)
    assert len(body["players"]) == 1
    assert body["players"][0]["id"] == str(player_id)
    assert [c["name"] for c in body["players"][0]["characters"]] == ["Alice"]

    await delete_tenant(tenant_id)


async def test_get_character_404_for_a_bare_being_with_no_character_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """CharacterNotFoundError also covers "this is a being with no
    character row" - the same non-enumerable collapsing every other
    not-found condition in this codebase already does (ADR 0031/RFC 0004).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        npc_entity = Entity(tenant_id=tenant_id, name="Unnamed Goblin")
        session.add(npc_entity)
        await session.flush()
        session.add(Being(entity_id=npc_entity.id, tenant_id=tenant_id))
        await session.commit()
        npc_entity_id = npc_entity.id

    response = await client.get(f"/tenants/{tenant_id}/characters/{npc_entity_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_list_characters_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/characters")
    assert response.status_code == 404

    await delete_tenant(tenant_id)
