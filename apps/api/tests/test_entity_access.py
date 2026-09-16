import uuid

from _admin_db import admin_session_factory
from conftest import make_campaign, make_character, make_player

from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
    can_manage_campaign,
)
from lorenzo_api.entity_access import (
    can_self_manage_entity,
    controlled_character_entity_ids,
    reachable_entity_ids,
)
from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
    Containment,
    Entity,
    Membership,
    MembershipRole,
    Ownership,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


async def _make_gm_user() -> User:
    return User(authgear_subject_id=f"authgear|test-gm-{uuid.uuid4()}")


async def test_controlled_character_entity_ids_via_player_roster() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        user_id = player.user_id
        await session.commit()

        ids = await controlled_character_entity_ids(session, user_id=user_id, tenant_id=tenant_id)
        assert ids == frozenset({character.entity_id})

        await session.delete(tenant)
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_controlled_character_entity_ids_empty_with_no_player_rows() -> None:
    async with admin_session_factory() as session:
        assert (
            await controlled_character_entity_ids(
                session, user_id=uuid.uuid4(), tenant_id=uuid.uuid4()
            )
            == frozenset()
        )


async def test_reachable_entity_ids_includes_root_owned_and_transitively_contained() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        character = await make_character(session, tenant_id=tenant_id, name="Alice")

        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        chest = Entity(tenant_id=tenant_id, name="Chest")
        sword = Entity(tenant_id=tenant_id, name="Sword")
        unrelated = Entity(tenant_id=tenant_id, name="Unrelated")
        session.add_all([backpack, chest, sword, unrelated])
        await session.flush()

        # Alice owns the sword directly, and owns the chest. The sword is
        # inside the backpack, which is itself inside the chest - two hops
        # deep, proving the walk is genuinely recursive, not one level only.
        session.add(
            Ownership(
                owned_entity_id=sword.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Ownership(
                owned_entity_id=chest.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Containment(child_entity_id=backpack.id, parent_entity_id=chest.id, tenant_id=tenant_id)
        )
        session.add(
            Containment(child_entity_id=sword.id, parent_entity_id=backpack.id, tenant_id=tenant_id)
        )
        await session.commit()

        reachable = await reachable_entity_ids(
            session, root_entity_ids=frozenset({character.entity_id}), tenant_id=tenant_id
        )

        assert character.entity_id in reachable
        assert sword.id in reachable
        assert chest.id in reachable
        assert backpack.id in reachable
        assert unrelated.id not in reachable

        await session.delete(tenant)
        await session.commit()


async def test_reachable_entity_ids_empty_for_empty_roots() -> None:
    async with admin_session_factory() as session:
        assert (
            await reachable_entity_ids(session, root_entity_ids=frozenset(), tenant_id=uuid.uuid4())
            == frozenset()
        )


async def test_can_self_manage_entity_true_when_owned_by_own_character() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add(sword)
        await session.flush()
        session.add(
            Ownership(
                owned_entity_id=sword.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        user_id = player.user_id
        await session.commit()

        assert (
            await can_self_manage_entity(
                session, entity_id=sword.id, user_id=user_id, tenant_id=tenant_id
            )
            is True
        )

        await session.delete(tenant)
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_can_self_manage_entity_false_for_unrelated_entity_or_no_characters() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add(sword)
        await session.commit()

        assert (
            await can_self_manage_entity(
                session, entity_id=sword.id, user_id=uuid.uuid4(), tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.commit()


async def test_can_manage_campaign_true_for_campaign_gm_false_for_plain_player() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        gm_user = await _make_gm_user()
        session.add(gm_user)
        await session.flush()
        gm_user_id = gm_user.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign_id))
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_id)
        player_user_id = player.user_id
        await session.commit()

        assert (
            await can_manage_campaign(
                session, user_id=gm_user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is True
        )
        assert (
            await can_manage_campaign(
                session, user_id=player_user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(gm_user)
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_can_manage_campaign_true_for_tenant_owner_regardless_of_opt_out() -> None:
    """RFC 0006's own point: administrative capability over a campaign is a
    different axis from *play* visibility - an OrgaCampaignOptOut/
    TenantAdminCampaignOptOut exists so an admin can play an ordinary
    character without spoilers, but must not also strip their ability to
    manage the campaign as an object (ADR 0010).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        owner_user_id = uuid.uuid4()
        owner_user = User(id=owner_user_id, authgear_subject_id=f"owner-{owner_user_id}")
        session.add(owner_user)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant_id, user_id=owner_user_id, role=MembershipRole.OWNER)
        )
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=owner_user_id, campaign_id=campaign_id
            )
        )
        await session.commit()

        assert (
            await can_manage_campaign(
                session, user_id=owner_user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is True
        )

        await session.delete(tenant)
        await session.delete(owner_user)
        await session.commit()


async def test_can_manage_any_campaign_in_tenant_admin_or_gm_true_player_false() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        owner_user_id = uuid.uuid4()
        owner_user = User(id=owner_user_id, authgear_subject_id=f"owner-{owner_user_id}")
        session.add(owner_user)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant_id, user_id=owner_user_id, role=MembershipRole.OWNER)
        )
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        player_user_id = player.user_id
        await session.commit()

        assert (
            await can_manage_any_campaign_in_tenant(
                session, user_id=owner_user_id, tenant_id=tenant_id
            )
            is True
        )
        assert (
            await can_manage_any_campaign_in_tenant(
                session, user_id=player_user_id, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(owner_user)
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_campaign_ids_for_character_and_can_manage_any_of_campaigns() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="B")
        await session.flush()
        player_a = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_a.id)
        player_b = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_b.id)
        character = await make_character(session, tenant_id=tenant_id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player_a.id, tenant_id=tenant_id
            )
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player_b.id, tenant_id=tenant_id
            )
        )
        gm_user = await _make_gm_user()
        session.add(gm_user)
        await session.flush()
        gm_user_id = gm_user.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign_b.id))
        player_a_user_id, player_b_user_id = player_a.user_id, player_b.user_id
        await session.commit()

        campaign_ids = await campaign_ids_for_character(
            session, character_entity_id=character.entity_id, tenant_id=tenant_id
        )
        assert campaign_ids == frozenset({campaign_a.id, campaign_b.id})

        # GM of only campaign_b - "any one is enough" (RFC 0005).
        assert (
            await can_manage_any_of_campaigns(
                session, user_id=gm_user_id, campaign_ids=campaign_ids, tenant_id=tenant_id
            )
            is True
        )
        assert (
            await can_manage_any_of_campaigns(
                session, user_id=player_a_user_id, campaign_ids=campaign_ids, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(gm_user)
        await session.delete(await session.get_one(User, player_a_user_id))
        await session.delete(await session.get_one(User, player_b_user_id))
        await session.commit()
