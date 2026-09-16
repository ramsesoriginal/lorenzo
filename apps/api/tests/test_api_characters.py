import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Containment,
    Entity,
    GroupMember,
    Information,
    Knowledge,
    Membership,
    MembershipRole,
    Ownership,
    Player,
    Tenant,
    User,
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


async def test_list_character_groups_returns_groups_the_character_belongs_to(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0045's nice-to-have - the reverse of GET .../groups/{id}/members."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        goblins = Entity(tenant_id=tenant_id, name="Goblins")
        thieves_guild = Entity(tenant_id=tenant_id, name="Thieves' Guild")
        session.add_all([goblins, thieves_guild])
        await session.flush()
        session.add(
            GroupMember(
                group_entity_id=goblins.id,
                character_entity_id=alice.entity_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        alice_id, goblins_id, thieves_guild_id = alice.entity_id, goblins.id, thieves_guild.id

    response = await client.get(f"/tenants/{tenant_id}/characters/{alice_id}/groups")

    assert response.status_code == 200
    group_ids = {item["id"] for item in response.json()}
    assert group_ids == {str(goblins_id)}
    assert str(thieves_guild_id) not in group_ids

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


async def test_list_characters_404_for_a_plain_player_without_tenant_membership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The router's own gating dependency moved from get_tenant_context to
    get_tenant_or_404 (ADR 0036/RFC 0007, so self-service writes can reach
    it without a tenant-wide Membership row) - but list_characters/
    get_character re-add their own explicit membership check, so a plain
    player (no Membership) still can't browse the tenant's full roster,
    same as before this change.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/characters")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


# --- POST /characters (ADR 0036/RFC 0007) ---------------------------------


async def test_create_character_self_service_folds_owner_into_roster(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A player rolling their own PC needs no GM involvement - and
    owner_player_id is automatically added to player_ids if not already
    present.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        player = Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id = player.id

    response = await client.post(
        f"/tenants/{tenant_id}/characters",
        json={"name": "Alice", "owner_player_id": str(player_id), "player_ids": []},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice"
    assert body["owner_player_id"] == str(player_id)
    assert body["created_by"] == str(test_user_id)
    assert body["updated_by"] == str(test_user_id)
    assert [p["id"] for p in body["players"]] == [str(player_id)]
    assert response.headers["location"].endswith(
        f"/tenants/{tenant_id}/characters/{body['entity_id']}"
    )

    async with admin_session_factory() as session:
        entity = await session.get_one(Entity, uuid.UUID(body["entity_id"]))
        assert entity.created_by == test_user_id
        assert entity.updated_by == test_user_id

    await delete_tenant(tenant_id)


async def test_create_character_403_when_player_ids_span_a_campaign_caller_cant_manage(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Roster-link tier, every-campaign shape: managing campaign A alone
    isn't enough when player_ids also touches campaign B.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id)
        )
        player_a_user = User(authgear_subject_id=f"authgear|a-{uuid.uuid4()}")
        player_b_user = User(authgear_subject_id=f"authgear|b-{uuid.uuid4()}")
        session.add_all([player_a_user, player_b_user])
        await session.flush()
        player_a = Player(user_id=player_a_user.id, campaign_id=campaign_a.id, tenant_id=tenant_id)
        player_b = Player(user_id=player_b_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add_all([player_a, player_b])
        await session.commit()
        player_a_id, player_b_id = player_a.id, player_b.id

    response = await client.post(
        f"/tenants/{tenant_id}/characters",
        json={"name": "Party NPC", "player_ids": [str(player_a_id), str(player_b_id)]},
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_create_character_201_when_managing_every_touched_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Same shape as above, but the caller manages *both* campaigns."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id)
        )
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_b.id)
        )
        player_a_user = User(authgear_subject_id=f"authgear|a-{uuid.uuid4()}")
        player_b_user = User(authgear_subject_id=f"authgear|b-{uuid.uuid4()}")
        session.add_all([player_a_user, player_b_user])
        await session.flush()
        player_a = Player(user_id=player_a_user.id, campaign_id=campaign_a.id, tenant_id=tenant_id)
        player_b = Player(user_id=player_b_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add_all([player_a, player_b])
        await session.commit()
        player_a_id, player_b_id = player_a.id, player_b.id

    response = await client.post(
        f"/tenants/{tenant_id}/characters",
        json={"name": "Shared NPC", "player_ids": [str(player_a_id), str(player_b_id)]},
    )

    assert response.status_code == 201

    await delete_tenant(tenant_id)


async def test_create_character_ownerless_falls_back_to_any_campaign_in_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/characters", json={"name": "NPC", "player_ids": []}
    )

    assert response.status_code == 201
    assert response.json()["owner_player_id"] is None
    assert response.json()["players"] == []

    await delete_tenant(tenant_id)


async def test_create_character_ownerless_403_without_any_manage_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.post(
        f"/tenants/{tenant_id}/characters", json={"name": "NPC", "player_ids": []}
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)


async def test_create_character_404_for_a_nonexistent_player_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/characters",
        json={"name": "Ghost", "player_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404

    await delete_tenant(tenant_id)


# --- PUT /characters/{id} (promote, ADR 0036/RFC 0007) --------------------


async def test_promote_character_first_call_is_201_repeat_call_is_200(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The RFC's own explicitly-called-out two-status-code behavior - each
    branch gets its own assertion here, not just one shared happy path.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        player = Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        entity = Entity(tenant_id=tenant_id, name="Bob")
        session.add(entity)
        await session.flush()
        session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        being_id, player_id = entity.id, player.id

    first = await client.put(
        f"/tenants/{tenant_id}/characters/{being_id}",
        json={"owner_player_id": str(player_id)},
    )
    assert first.status_code == 201
    assert first.headers["location"].endswith(f"/tenants/{tenant_id}/characters/{being_id}")
    body = first.json()
    assert body["created_by"] == str(test_user_id)
    assert body["updated_by"] == str(test_user_id)

    async with admin_session_factory() as session:
        entity_row = await session.get_one(Entity, being_id)
        # entity.created_by is untouched by promotion - it was never set to
        # begin with here (the being predates the promoter, ADR 0029).
        assert entity_row.created_by is None

    second_player_user = User(authgear_subject_id=f"authgear|second-{uuid.uuid4()}")
    async with admin_session_factory() as session:
        session.add(second_player_user)
        await session.flush()
        second_player = Player(
            user_id=second_player_user.id, campaign_id=campaign_id, tenant_id=tenant_id
        )
        session.add(second_player)
        # Give test_user_id a second player of their own too, so the
        # second PUT (reassigning to it) is still self-service - a
        # different campaign, since one user can only have one Player row
        # per campaign (UniqueConstraint(campaign_id, user_id)).
        second_campaign = await make_campaign(session, tenant_id=tenant_id, name="Second")
        await session.flush()
        third_player = Player(
            user_id=test_user_id, campaign_id=second_campaign.id, tenant_id=tenant_id
        )
        session.add(third_player)
        await session.commit()
        third_player_id = third_player.id

    second = await client.put(
        f"/tenants/{tenant_id}/characters/{being_id}",
        json={"owner_player_id": str(third_player_id)},
    )
    assert second.status_code == 200
    assert "location" not in second.headers
    second_body = second.json()
    assert second_body["owner_player_id"] == str(third_player_id)
    assert second_body["updated_by"] == str(test_user_id)

    async with admin_session_factory() as session:
        entity_row = await session.get_one(Entity, being_id)
        # A repeat PUT never touches entity's own columns.
        assert entity_row.created_by is None
        assert entity_row.updated_by is None

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, second_player_user.id))
        await session.commit()


async def test_promote_character_managed_by_a_campaign_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        other_player = Player(user_id=other_user.id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(other_player)
        being_entity = Entity(tenant_id=tenant_id, name="NPC-to-be")
        session.add(being_entity)
        await session.flush()
        session.add(Being(entity_id=being_entity.id, tenant_id=tenant_id))
        await session.commit()
        being_id, other_player_id = being_entity.id, other_player.id

    response = await client.put(
        f"/tenants/{tenant_id}/characters/{being_id}",
        json={"owner_player_id": str(other_player_id)},
    )

    assert response.status_code == 201

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user.id))
        await session.commit()


async def test_promote_character_403_without_manage_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        other_player = Player(user_id=other_user.id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(other_player)
        being_entity = Entity(tenant_id=tenant_id, name="NPC-to-be")
        session.add(being_entity)
        await session.flush()
        session.add(Being(entity_id=being_entity.id, tenant_id=tenant_id))
        await session.commit()
        being_id, other_player_id = being_entity.id, other_player.id

    response = await client.put(
        f"/tenants/{tenant_id}/characters/{being_id}",
        json={"owner_player_id": str(other_player_id)},
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user.id))
        await session.commit()


async def test_promote_character_ownerless_by_tenant_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        being_entity = Entity(tenant_id=tenant_id, name="Unclaimed")
        session.add(being_entity)
        await session.flush()
        session.add(Being(entity_id=being_entity.id, tenant_id=tenant_id))
        await session.commit()
        being_id = being_entity.id

    response = await client.put(f"/tenants/{tenant_id}/characters/{being_id}", json={})

    assert response.status_code == 201
    assert response.json()["owner_player_id"] is None

    await delete_tenant(tenant_id)


async def test_promote_character_404_when_target_is_not_a_being(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        plain_entity = Entity(tenant_id=tenant_id, name="Just an entity")
        session.add(plain_entity)
        await session.commit()
        entity_id = plain_entity.id

    response = await client.put(f"/tenants/{tenant_id}/characters/{entity_id}", json={})

    assert response.status_code == 404

    await delete_tenant(tenant_id)


# --- PATCH /characters/{id} (ADR 0036/RFC 0007) ---------------------------


async def test_update_character_rename_as_self(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}", json={"name": "New Name"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

    await delete_tenant(tenant_id)


async def test_update_character_rename_managed_by_any_one_of_several_campaigns(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Any-one-current-campaign tier: managing just ONE of the character's
    two campaigns is enough for a rename - unlike DELETE's every-campaign
    tier.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id)
        )
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        player_a = Player(user_id=owner_user.id, campaign_id=campaign_a.id, tenant_id=tenant_id)
        player_b = Player(user_id=owner_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add_all([player_a, player_b])
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player_a.id)
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_a.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_b.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}", json={"name": "Renamed"}
    )

    assert response.status_code == 200

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_update_character_rename_403_without_standing_in_any_current_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        player = Player(user_id=owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        # test_user_id has a Player row somewhere, so get_tenant_or_404's
        # own tenant-existence check passes, but no manage standing at all.
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}", json={"name": "Renamed"}
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_update_character_rename_unrostered_character_by_tenant_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A character with no current roster/owner at all falls back to
    can_manage_any_campaign_in_tenant, mirroring the roster-link tier's own
    ownerless fallback - not named explicitly by the RFC's own text, but
    needed so this case isn't authorized by vacuous truth instead.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, name="Orphan NPC")
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}", json={"name": "Renamed Orphan"}
    )

    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_update_character_rename_unrostered_character_403_for_a_plain_participant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        character = await make_character(session, tenant_id=tenant_id, name="Orphan NPC")
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}", json={"name": "Renamed Orphan"}
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)


async def test_update_character_reassign_owner_as_self(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        # Two campaigns - one user can only have one Player row per
        # campaign (UniqueConstraint(campaign_id, user_id)), and old_player/
        # new_player must both belong to test_user_id here.
        old_campaign = await make_campaign(session, tenant_id=tenant_id, name="Old")
        new_campaign = await make_campaign(session, tenant_id=tenant_id, name="New")
        await session.flush()
        old_player = Player(user_id=test_user_id, campaign_id=old_campaign.id, tenant_id=tenant_id)
        new_player = Player(user_id=test_user_id, campaign_id=new_campaign.id, tenant_id=tenant_id)
        session.add_all([old_player, new_player])
        await session.flush()
        character = await make_character(
            session, tenant_id=tenant_id, owner_player_id=old_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=old_player.id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        character_id, new_player_id = character.entity_id, new_player.id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}",
        json={"owner_player_id": str(new_player_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["owner_player_id"] == str(new_player_id)
    assert str(new_player_id) in {p["id"] for p in body["players"]}

    await delete_tenant(tenant_id)


async def test_update_character_reassign_owner_403_without_managing_new_owners_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        original_user = User(authgear_subject_id=f"authgear|orig-{uuid.uuid4()}")
        new_owner_user = User(authgear_subject_id=f"authgear|new-{uuid.uuid4()}")
        session.add_all([original_user, new_owner_user])
        await session.flush()
        old_player = Player(user_id=original_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        new_player = Player(user_id=new_owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add_all([old_player, new_player])
        await session.flush()
        character = await make_character(
            session, tenant_id=tenant_id, owner_player_id=old_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=old_player.id,
                tenant_id=tenant_id,
            )
        )
        # test_user_id needs *some* standing to reach get_tenant_or_404's
        # own tenant-existence check, but none over this specific campaign.
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        character_id, new_player_id = character.entity_id, new_player.id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}",
        json={"owner_player_id": str(new_player_id)},
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, original_user.id))
        await session.delete(await session.get_one(User, new_owner_user.id))
        await session.commit()


async def test_update_character_owner_player_id_set_to_current_value_uses_rename_tier(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Setting owner_player_id to its own current value is not a
    reassignment - it uses the any-one-current-campaign tier, same as a
    plain rename, not the roster-link tier.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        player = Player(user_id=owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}",
        json={"owner_player_id": str(player_id)},
    )

    # A GM of the character's one current campaign is enough here (the
    # any-one tier) - if this were treated as a real reassignment, the
    # roster-link tier would apply instead, requiring the *specific*
    # player's campaign, which happens to be the same campaign here
    # regardless - so this alone doesn't distinguish the two tiers, but the
    # 200 at least proves neither tier rejects the no-op.
    assert response.status_code == 200

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_update_character_404_for_a_nonexistent_new_owner(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}",
        json={"owner_player_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_update_character_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.patch(
        f"/tenants/{tenant_id}/characters/{character_id}",
        json={"name": "New Name"},
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412

    await delete_tenant(tenant_id)


# --- DELETE /characters/{id} (demote, ADR 0036/RFC 0007) ------------------


async def test_delete_character_demotes_without_touching_being_entity_or_its_belongings(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The RFC's own explicitly-called-out reverse-of-the-obvious test:
    the character row is gone, but being/entity survive, along with
    anything it owned, contained, or knew.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.flush()
        character_id = character.entity_id

        owned_item = Entity(tenant_id=tenant_id, name="Owned Sword")
        location = Entity(tenant_id=tenant_id, name="Tavern")
        session.add_all([owned_item, location])
        await session.flush()
        session.add(
            Ownership(
                owned_entity_id=owned_item.id, owner_character_id=character_id, tenant_id=tenant_id
            )
        )
        session.add(
            Containment(
                child_entity_id=character_id, parent_entity_id=location.id, tenant_id=tenant_id
            )
        )
        info = Information(
            tenant_id=tenant_id, entity_id=location.id, title="A secret", type="description"
        )
        session.add(info)
        await session.flush()
        knowledge = Knowledge(
            knower_entity_id=character_id, information_id=info.id, tenant_id=tenant_id
        )
        session.add(knowledge)
        await session.commit()
        owned_item_id, knowledge_id = owned_item.id, knowledge.id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{character_id}")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Character, character_id) is None
        # being/entity survive untouched.
        assert await session.get(Being, character_id) is not None
        assert await session.get(Entity, character_id) is not None
        # Everything it owned, contained (lived in), or knew survives too.
        assert await session.get(Ownership, owned_item_id) is not None
        assert await session.get(Containment, character_id) is not None
        assert await session.get(Knowledge, knowledge_id) is not None

    await delete_tenant(tenant_id)


async def test_delete_character_every_campaign_tier_requires_all_not_any(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """DELETE's every-campaign tier: managing only ONE of the character's
    two campaigns is not enough - the opposite of PATCH-rename's any-one
    tier.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id)
        )
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        player_a = Player(user_id=owner_user.id, campaign_id=campaign_a.id, tenant_id=tenant_id)
        player_b = Player(user_id=owner_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add_all([player_a, player_b])
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player_a.id)
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_a.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_b.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{character_id}")

    assert response.status_code == 403
    async with admin_session_factory() as session:
        assert await session.get(Character, character_id) is not None

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_delete_character_204_when_managing_every_current_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id)
        )
        session.add(
            CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_b.id)
        )
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        player_a = Player(user_id=owner_user.id, campaign_id=campaign_a.id, tenant_id=tenant_id)
        player_b = Player(user_id=owner_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add_all([player_a, player_b])
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player_a.id)
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_a.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_b.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_id = character.entity_id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{character_id}")

    assert response.status_code == 204

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_delete_character_unrostered_character_by_tenant_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Every-campaign tier's own "nothing to scope to" fallback - without
    it, an unrostered character's demotion would be authorized by a
    vacuous all([]) regardless of who's asking.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, name="Orphan NPC")
        await session.commit()
        character_id = character.entity_id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{character_id}")

    assert response.status_code == 204

    await delete_tenant(tenant_id)


async def test_delete_character_unrostered_character_403_for_a_plain_participant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        character = await make_character(session, tenant_id=tenant_id, name="Orphan NPC")
        await session.commit()
        character_id = character.entity_id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{character_id}")

    assert response.status_code == 403
    async with admin_session_factory() as session:
        assert await session.get(Character, character_id) is not None

    await delete_tenant(tenant_id)


async def test_delete_character_404_for_a_bare_being(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Unnamed Goblin")
        session.add(entity)
        await session.flush()
        session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id

    response = await client.delete(f"/tenants/{tenant_id}/characters/{entity_id}")

    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_delete_character_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id)
        await session.commit()
        character_id = character.entity_id

    response = await client.delete(
        f"/tenants/{tenant_id}/characters/{character_id}", headers={"If-Match": 'W/"stale"'}
    )

    assert response.status_code == 412

    await delete_tenant(tenant_id)


# --- PUT/DELETE /characters/{id}/players/{player_id} (ADR 0036/RFC 0007) --


async def test_add_character_player_self_service_is_idempotent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    second_player_user = User(authgear_subject_id=f"authgear|co-pilot-{uuid.uuid4()}")
    async with admin_session_factory() as session:
        session.add(second_player_user)
        await session.flush()
        second_player = Player(
            user_id=second_player_user.id, campaign_id=campaign.id, tenant_id=tenant_id
        )
        session.add(second_player)
        await session.commit()

    first = await client.put(f"/tenants/{tenant_id}/characters/{character_id}/players/{player_id}")
    assert first.status_code == 200
    assert [p["id"] for p in first.json()["players"]] == [str(player_id)]

    # Re-adding the same link is a no-op, not a duplicate/error.
    second = await client.put(f"/tenants/{tenant_id}/characters/{character_id}/players/{player_id}")
    assert second.status_code == 200
    assert [p["id"] for p in second.json()["players"]] == [str(player_id)]

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, second_player_user.id))
        await session.commit()


async def test_add_character_player_managed_by_that_players_campaign_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        owner_player = Player(user_id=owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(owner_player)
        await session.flush()
        character = await make_character(
            session, tenant_id=tenant_id, owner_player_id=owner_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=owner_player.id,
                tenant_id=tenant_id,
            )
        )
        co_pilot_user = User(authgear_subject_id=f"authgear|co-pilot-{uuid.uuid4()}")
        session.add(co_pilot_user)
        await session.flush()
        co_pilot_player = Player(
            user_id=co_pilot_user.id, campaign_id=campaign.id, tenant_id=tenant_id
        )
        session.add(co_pilot_player)
        await session.commit()
        character_id, co_pilot_player_id = character.entity_id, co_pilot_player.id

    response = await client.put(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{co_pilot_player_id}"
    )

    assert response.status_code == 200
    assert str(co_pilot_player_id) in {p["id"] for p in response.json()["players"]}

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.delete(await session.get_one(User, co_pilot_user.id))
        await session.commit()


async def test_add_character_player_403_without_managing_that_players_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        owner_player = Player(user_id=owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(owner_player)
        await session.flush()
        character = await make_character(
            session, tenant_id=tenant_id, owner_player_id=owner_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=owner_player.id,
                tenant_id=tenant_id,
            )
        )
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        other_player = Player(user_id=other_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(other_player)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        character_id, other_player_id = character.entity_id, other_player.id

    response = await client.put(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{other_player_id}"
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.delete(await session.get_one(User, other_user.id))
        await session.commit()


async def test_add_character_player_404_for_a_nonexistent_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id)
        await session.commit()
        character_id = character.entity_id

    response = await client.put(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{uuid.uuid4()}"
    )

    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_remove_character_player_self_service(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{player_id}"
    )

    assert response.status_code == 200
    assert response.json()["players"] == []
    async with admin_session_factory() as session:
        assert await session.get(CharacterPlayer, (character_id, player_id)) is None
        # The character itself survives - this only removes one link.
        assert await session.get(Character, character_id) is not None

    await delete_tenant(tenant_id)


async def test_remove_character_player_is_a_no_op_when_no_link_exists(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id)
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{player_id}"
    )

    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_remove_character_player_403_without_managing_that_players_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        owner_user = User(authgear_subject_id=f"authgear|owner-{uuid.uuid4()}")
        session.add(owner_user)
        await session.flush()
        owner_player = Player(user_id=owner_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(owner_player)
        await session.flush()
        character = await make_character(
            session, tenant_id=tenant_id, owner_player_id=owner_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=owner_player.id,
                tenant_id=tenant_id,
            )
        )
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        character_id, owner_player_id = character.entity_id, owner_player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{owner_player_id}"
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_user.id))
        await session.commit()


async def test_remove_character_player_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_id = character.entity_id, player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/characters/{character_id}/players/{player_id}",
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412

    await delete_tenant(tenant_id)
