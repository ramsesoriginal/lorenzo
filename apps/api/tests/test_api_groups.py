import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_character, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, GroupMember, Tenant


async def test_list_groups_returns_distinct_group_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0045: a group is any entity with at least one GroupMember row
    naming it - DISTINCT so a group with two members appears once, not
    once per member.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        goblins = Entity(tenant_id=tenant_id, name="Goblins")
        thieves_guild = Entity(tenant_id=tenant_id, name="Thieves' Guild")
        not_a_group = Entity(tenant_id=tenant_id, name="Just an Entity")
        session.add_all([goblins, thieves_guild, not_a_group])
        await session.flush()
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        session.add_all(
            [
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=bob.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=thieves_guild.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        goblins_id, thieves_guild_id, not_a_group_id = goblins.id, thieves_guild.id, not_a_group.id

    response = await client.get(f"/tenants/{tenant_id}/groups")

    assert response.status_code == 200
    group_ids = {item["id"] for item in response.json()["items"]}
    assert group_ids == {str(goblins_id), str(thieves_guild_id)}
    assert str(not_a_group_id) not in group_ids

    await delete_tenant(tenant_id)


async def test_list_group_members_returns_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        goblins = Entity(tenant_id=tenant_id, name="Goblins")
        session.add(goblins)
        await session.flush()
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        session.add_all(
            [
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=bob.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        goblins_id = goblins.id
        alice_id, bob_id = alice.entity_id, bob.entity_id

    response = await client.get(f"/tenants/{tenant_id}/groups/{goblins_id}/members")

    assert response.status_code == 200
    member_ids = {item["id"] for item in response.json()}
    assert member_ids == {str(alice_id), str(bob_id)}

    await delete_tenant(tenant_id)


async def test_list_group_members_empty_list_for_a_real_entity_with_no_members(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0045: unlike ADR 0040's item-instance precedent, "exists but has
    no members" stays a distinguishable 200/[] here, not collapsed into a
    404 - a group's bare existence isn't a secret.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Just an Entity")
        session.add(entity)
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/groups/{entity_id}/members")

    assert response.status_code == 200
    assert response.json() == []

    await delete_tenant(tenant_id)


async def test_list_group_members_404_for_unknown_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/groups/00000000-0000-0000-0000-000000000000/members"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_list_groups_404_for_non_participant(client: AsyncClient) -> None:
    """No test_user_id fixture use at all - an authenticated caller with
    zero standing in this tenant (no Membership/Player/CampaignGm row)
    can't browse its groups, mirroring routers/item_instances.py's
    identical _require_participant precedent.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/groups")

    assert response.status_code == 404
    await delete_tenant(tenant_id)
