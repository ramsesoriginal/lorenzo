import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient

from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    Campaign,
    CampaignGm,
    Character,
    Entity,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


async def test_list_campaigns_hides_secret_from_a_plain_participant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: a plain participant (a Player row, no
    Membership/CampaignGm) sees non-secret campaigns but not a secret one
    they don't GM."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        visible = await make_campaign(session, tenant_id=tenant_id, name="Visible")
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await make_player(session, tenant_id=tenant_id, campaign_id=visible.id)
        # The caller (test_user_id) needs their own Player row too, in
        # *some* campaign, to count as is_tenant_participant at all.
        session.add(Player(user_id=test_user_id, campaign_id=visible.id, tenant_id=tenant_id))
        await session.commit()
        visible_id, secret_id = visible.id, secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(visible_id) in ids
    assert str(secret_id) not in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_shows_secret_to_its_own_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=secret.id))
        await session.commit()
        secret_id = secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(secret_id) in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_shows_secret_to_a_tenant_admin(
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
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await session.commit()
        secret_id = secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(secret_id) in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_404_for_a_caller_with_no_relationship_to_the_tenant(
    client: AsyncClient,
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_campaign_reachable_via_player_gm_or_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Reachable")
        await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(campaign_id)
    assert body["name"] == "Reachable"
    assert body["secret"] is False
    assert "entity_id" not in body

    await delete_tenant(tenant_id)


async def test_get_campaign_ignores_secret_when_otherwise_reachable(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: secret only governs the browse-all list, not
    whether someone who already has a legitimate way to reach a campaign
    (their own Player row here) can open it directly."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Secret But Mine")
        campaign.secret = True
        await session.flush()
        await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_get_campaign_404_when_caller_cannot_access_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """get_tenant_or_404 (unlike get_tenant_context) admits any real tenant
    regardless of membership - test_user_id reaches the tenant fine here,
    then get_campaign_context's own can_access_campaign check is what
    actually rejects a campaign they have no player/gm/admin relationship
    to (ADR 0030/RFC 0003), the "reachable tenant, unreachable campaign"
    case this dependency exists to distinguish.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Not Mine")
        # Someone else's Player row, not test_user_id's - proves the
        # campaign is real and has players, just not this caller.
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        session.add(Player(user_id=other_user.id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_campaign_404_for_unknown_campaign_in_a_real_tenant(
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

    unknown_campaign_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/tenants/{tenant_id}/campaigns/{unknown_campaign_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


# --- POST /campaigns (ADR 0034/RFC 0006) --------------------------------


async def test_create_campaign_creates_entity_and_sets_attribution(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "The Ashen Crown",
            "game_system": "D&D 5e",
            "slug": "ashen-crown",
            "description": "A campaign.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "The Ashen Crown"
    assert body["slug"] == "ashen-crown"
    assert body["secret"] is False
    assert body["created_by"] == str(test_user_id)
    assert body["updated_by"] == str(test_user_id)
    assert response.headers["location"].endswith(f"/tenants/{tenant_id}/campaigns/{body['id']}")

    async with admin_session_factory() as session:
        campaign = await session.get_one(Campaign, uuid.UUID(body["id"]))
        # The dedicated Entity is real and created server-side, not
        # something the client supplied.
        assert await session.get(Entity, campaign.entity_id) is not None

    await delete_tenant(tenant_id)


async def test_create_campaign_defaults_secret_to_false_and_allows_override(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Secret Campaign",
            "game_system": "D&D 5e",
            "slug": "secret-campaign",
            "description": "",
            "secret": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["secret"] is True

    await delete_tenant(tenant_id)


async def test_create_campaign_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={"name": "X", "game_system": "D&D 5e", "slug": "x", "description": ""},
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


# --- PATCH /campaigns/{id} (ADR 0034/RFC 0006) --------------------------


async def test_update_campaign_renames_and_stamps_updated_by_as_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Old Name")
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        await session.commit()

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}", json={"name": "New Name"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["updated_by"] == str(test_user_id)

    await delete_tenant(tenant_id)


async def test_update_campaign_as_tenant_admin_updates_every_field(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Old Name")
        await session.commit()
        campaign_id = campaign.id

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}",
        json={
            "name": "New Name",
            "game_system": "Pathfinder 2e",
            "slug": "new-slug",
            "description": "New description.",
            "secret": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["game_system"] == "Pathfinder 2e"
    assert body["slug"] == "new-slug"
    assert body["description"] == "New description."
    assert body["secret"] is True

    await delete_tenant(tenant_id)


async def test_update_campaign_403_for_a_plain_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A Player row gives get_campaign_context access but not
    can_manage_campaign - the two-tier 404-then-403 shape (ADR 0032/0034)."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}", json={"name": "New Name"}
    )
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_update_campaign_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/00000000-0000-0000-0000-000000000000",
        json={"name": "x"},
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_update_campaign_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}",
        json={"name": "New Name"},
        headers={"If-Match": 'W/"stale"'},
    )
    assert response.status_code == 412

    await delete_tenant(tenant_id)


async def test_update_campaign_succeeds_with_correct_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id
        current_etag = etag_for(campaign.updated_at)

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}",
        json={"name": "New Name"},
        headers={"If-Match": current_etag},
    )
    assert response.status_code == 200

    await delete_tenant(tenant_id)


# --- DELETE /campaigns/{id} (ADR 0034/RFC 0006) -------------------------


async def test_delete_campaign_removes_campaign_and_its_entity_when_empty(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id, entity_id = campaign.id, campaign.entity_id

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Campaign, campaign_id) is None
        # The dedicated Entity is explicitly cleaned up too, not left
        # dangling now that campaign.entity_id no longer references it.
        assert await session.get(Entity, entity_id) is None

    await delete_tenant(tenant_id)


async def test_delete_campaign_409_when_a_player_exists_without_force(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        await make_player(session, tenant_id=tenant_id, campaign_id=campaign_id)
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    async with admin_session_factory() as session:
        assert await session.get(Campaign, campaign_id) is not None

    await delete_tenant(tenant_id)


async def test_delete_campaign_409_when_a_gm_exists_without_force(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        other_user = User(authgear_subject_id=f"authgear|other-gm-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=other_user.id, campaign_id=campaign_id))
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")

    assert response.status_code == 409

    await delete_tenant(tenant_id)


async def test_delete_campaign_force_true_cascades_and_orphans_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """RFC 0006's own cascade shape: force=true takes the roster with it,
    but a character outlives the campaign it was created in - its
    owner_player_id is SET NULL (becomes an NPC), it is not deleted.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id, entity_id = campaign.id, campaign.entity_id
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_id)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        await session.flush()
        character_entity_id, player_id = character.entity_id, player.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}?force=true")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Campaign, campaign_id) is None
        assert await session.get(Entity, entity_id) is None
        assert await session.get(Player, player_id) is None
        character = await session.get_one(Character, character_entity_id)
        assert character.owner_player_id is None

        await session.delete(await session.get_one(Entity, character_entity_id))
        await session.commit()

    await delete_tenant(tenant_id)


async def test_delete_campaign_gated_by_tenant_context_survives_own_opt_out(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """RFC 0006's central point for this route: DELETE is gated by
    get_tenant_context, not get_campaign_context - an opted-out tenant
    admin with no Player/CampaignGm row for this campaign can no longer
    even GET it, but must still be able to delete it.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id
            )
        )
        await session.commit()

    # Confirm the opt-out really does block ordinary read access first.
    get_response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert get_response.status_code == 404

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 204

    await delete_tenant(tenant_id)


async def test_delete_campaign_404_for_unknown_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_delete_campaign_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_delete_campaign_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}", headers={"If-Match": 'W/"stale"'}
    )
    assert response.status_code == 412
    async with admin_session_factory() as session:
        assert await session.get(Campaign, campaign_id) is not None

    await delete_tenant(tenant_id)


# --- PUT/DELETE .../gms/{user_id} (ADR 0034/RFC 0006) -------------------


async def test_grant_campaign_gm_creates_row_with_granter_as_created_by(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        new_gm = User(authgear_subject_id=f"authgear|new-gm-{uuid.uuid4()}")
        session.add(new_gm)
        await session.commit()
        new_gm_id = new_gm.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{new_gm_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(campaign_id)
    async with admin_session_factory() as session:
        gm = await session.get_one(CampaignGm, (tenant_id, new_gm_id, campaign_id))
        # created_by is the granter (test_user_id, the caller), not the
        # grantee (new_gm_id).
        assert gm.created_by == test_user_id

    await delete_tenant(tenant_id)


async def test_grant_campaign_gm_is_idempotent_and_keeps_original_created_by(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        original_granter = User(authgear_subject_id=f"authgear|original-granter-{uuid.uuid4()}")
        gm_user = User(authgear_subject_id=f"authgear|gm-{uuid.uuid4()}")
        session.add_all([original_granter, gm_user])
        await session.flush()
        session.add(
            CampaignGm(
                tenant_id=tenant_id,
                user_id=gm_user.id,
                campaign_id=campaign_id,
                created_by=original_granter.id,
            )
        )
        await session.commit()
        gm_user_id, original_granter_id = gm_user.id, original_granter.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{gm_user_id}")

    assert response.status_code == 200
    async with admin_session_factory() as session:
        gm = await session.get_one(CampaignGm, (tenant_id, gm_user_id, campaign_id))
        # Re-granting an existing GM is a no-op - created_by isn't
        # overwritten to the second caller (test_user_id).
        assert gm.created_by == original_granter_id

    await delete_tenant(tenant_id)


async def test_grant_campaign_gm_403_for_a_plain_player(
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
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.commit()
        other_user_id = other_user.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{other_user_id}")
    assert response.status_code == 403

    await delete_tenant(tenant_id)


async def test_grant_campaign_gm_404_for_caller_with_no_access_to_the_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{test_user_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_revoke_campaign_gm_by_a_manager(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        gm_user = User(authgear_subject_id=f"authgear|gm-{uuid.uuid4()}")
        session.add(gm_user)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user.id, campaign_id=campaign_id))
        await session.commit()
        gm_user_id = gm_user.id

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{gm_user_id}")

    assert response.status_code == 200
    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, gm_user_id, campaign_id)) is None

    await delete_tenant(tenant_id)


async def test_revoke_campaign_gm_self_removal_without_manage_permission(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A plain GM (no tenant-wide Membership) can always remove their own
    grant, even though they'd fail can_manage_campaign for anyone else's.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        await session.commit()

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{test_user_id}"
    )

    assert response.status_code == 200
    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, test_user_id, campaign_id)) is None

    await delete_tenant(tenant_id)


async def test_revoke_campaign_gm_403_for_an_unrelated_caller(
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
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        other_gm = User(authgear_subject_id=f"authgear|other-gm-{uuid.uuid4()}")
        session.add(other_gm)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=other_gm.id, campaign_id=campaign_id))
        await session.commit()
        other_gm_id = other_gm.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{other_gm_id}"
    )
    assert response.status_code == 403

    await delete_tenant(tenant_id)


async def test_revoke_campaign_gm_idempotent_when_not_a_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id
    not_a_gm_id = uuid.uuid4()

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{not_a_gm_id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(campaign_id)

    await delete_tenant(tenant_id)


# --- PUT/DELETE .../admin-opt-out (ADR 0034/RFC 0006) -------------------


async def test_admin_opt_out_put_as_owner_records_created_by(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert response.status_code == 200
    async with admin_session_factory() as session:
        opt_out = await session.get_one(
            TenantAdminCampaignOptOut, (tenant_id, test_user_id, campaign_id)
        )
        assert opt_out.created_by == test_user_id

    await delete_tenant(tenant_id)


async def test_admin_opt_out_put_as_orga(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")
    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_admin_opt_out_put_422_for_a_plain_player(
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
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_admin_opt_out_put_is_idempotent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A second PUT is a no-op at the row level - test_user_id also holds a
    Player row here so opting out doesn't strip their own
    get_campaign_context access entirely (see
    test_admin_opt_out_put_twice_without_any_other_standing_404s below for
    what happens without one - a real, documented consequence of RFC 0006's
    own endpoint table, ADR 0034).
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

    first = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")
    second = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert first.status_code == 200
    assert second.status_code == 200

    await delete_tenant(tenant_id)


async def test_admin_opt_out_put_twice_without_any_other_standing_404s(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A documented edge case (ADR 0034's Consequences): opting out of a
    campaign the caller has no Player/CampaignGm row in removes their only
    route to get_campaign_context for it - including, notably, back to the
    admin-opt-out routes themselves. Implemented exactly as RFC 0006's own
    endpoint table specifies (get_campaign_context on both PUT and DELETE),
    not silently worked around.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    first = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")
    second = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert first.status_code == 200
    assert second.status_code == 404

    await delete_tenant(tenant_id)


async def test_admin_opt_out_delete_removes_the_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """test_user_id also holds a Player row here, same reasoning as
    test_admin_opt_out_put_is_idempotent above - without one, an already
    opted-out tenant admin has no route left through get_campaign_context
    to reach this DELETE route at all (ADR 0034's documented consequence).
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id
            )
        )
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert response.status_code == 200
    async with admin_session_factory() as session:
        assert (
            await session.get(TenantAdminCampaignOptOut, (tenant_id, test_user_id, campaign_id))
            is None
        )

    await delete_tenant(tenant_id)


async def test_admin_opt_out_delete_is_a_no_op_when_no_row_exists(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")

    assert response.status_code == 200
    assert response.json()["id"] == str(campaign_id)

    await delete_tenant(tenant_id)
