import uuid

from _admin_db import admin_session_factory
from conftest import make_campaign, make_character

from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    CharacterPlayer,
    Entity,
    GroupMember,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


def _make_user() -> User:
    return User(authgear_subject_id=f"authgear|info-visibility-{uuid.uuid4()}")


async def test_resolve_information_visibility_orga_true_for_orga_membership() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.ORGA))
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.is_orga is True

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_false_for_owner_membership() -> None:
    """OWNER doesn't get the ORGA bypass - mirrors can_access_campaign's own
    precedent of only checking MembershipRole.ORGA.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.is_orga is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_false_with_no_membership() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.is_orga is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_empty_when_user_has_nothing() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.player_ids == frozenset()
        assert visibility.knower_entity_ids == frozenset()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_collects_player_ids_across_campaigns() -> None:
    """RFC 0002: a user gets a fresh Player row per campaign, on purpose -
    this route has no campaign parameter, so every campaign's Player row
    in this tenant is unioned in, a deliberate widening (see the module's
    own docstring).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign_1 = await make_campaign(session, tenant_id=tenant_id, name="Campaign 1")
        campaign_2 = await make_campaign(session, tenant_id=tenant_id, name="Campaign 2")
        player_1 = Player(user_id=user_id, campaign_id=campaign_1.id, tenant_id=tenant_id)
        player_2 = Player(user_id=user_id, campaign_id=campaign_2.id, tenant_id=tenant_id)
        session.add_all([player_1, player_2])
        await session.commit()
        player_1_id, player_2_id = player_1.id, player_2.id

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.player_ids == frozenset({player_1_id, player_2_id})

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_excludes_player_ids_from_a_different_tenant() -> None:
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        user = _make_user()
        session.add_all([tenant_a, tenant_b, user])
        await session.flush()
        tenant_a_id, tenant_b_id, user_id = tenant_a.id, tenant_b.id, user.id
        campaign_b = await make_campaign(
            session, tenant_id=tenant_b_id, name="Campaign B", game_system="D&D 5e"
        )
        await session.flush()
        session.add(Player(user_id=user_id, campaign_id=campaign_b.id, tenant_id=tenant_b_id))
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_a_id
        )
        assert visibility.player_ids == frozenset()

        await session.delete(await session.get_one(Tenant, tenant_a_id))
        await session.delete(await session.get_one(Tenant, tenant_b_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_collects_character_ids_via_roster_reuse() -> None:
    """One character linked to two Player rows across two campaigns
    (roster reuse, ADR 0025) - both campaigns' Player rows must resolve to
    the same character id.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign_1 = await make_campaign(session, tenant_id=tenant_id, name="Campaign 1")
        campaign_2 = await make_campaign(session, tenant_id=tenant_id, name="Campaign 2")
        player_1 = Player(user_id=user_id, campaign_id=campaign_1.id, tenant_id=tenant_id)
        player_2 = Player(user_id=user_id, campaign_id=campaign_2.id, tenant_id=tenant_id)
        session.add_all([player_1, player_2])
        await session.flush()

        character = await make_character(session, tenant_id=tenant_id, name="Character")
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_1.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player_2.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_id = character.entity_id

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert character_id in visibility.knower_entity_ids

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_collects_group_ids_one_level_via_group_member() -> (
    None
):
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = Player(user_id=user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        group = Entity(tenant_id=tenant_id, name="Group")
        session.add(group)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, name="Character")
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player.id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=group.id,
                    character_entity_id=character.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_id, group_id = character.entity_id, group.id

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.knower_entity_ids == frozenset({character_id, group_id})

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_orga_suppressed_by_active_opt_out() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.ORGA))
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign.id)
        )
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_id
        )
        assert visibility.is_orga is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_resolve_information_visibility_orga_opt_out_is_tenant_scoped() -> None:
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        user = _make_user()
        session.add_all([tenant_a, tenant_b, user])
        await session.flush()
        tenant_a_id, tenant_b_id, user_id = tenant_a.id, tenant_b.id, user.id
        session.add(Membership(tenant_id=tenant_a_id, user_id=user_id, role=MembershipRole.ORGA))
        campaign_b = await make_campaign(
            session, tenant_id=tenant_b_id, name="Campaign B", game_system="D&D 5e"
        )
        await session.flush()
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_b_id, user_id=user_id, campaign_id=campaign_b.id
            )
        )
        await session.commit()

        visibility = await resolve_information_visibility(
            session, user_id=user_id, tenant_id=tenant_a_id
        )
        assert visibility.is_orga is True

        await session.delete(await session.get_one(Tenant, tenant_a_id))
        await session.delete(await session.get_one(Tenant, tenant_b_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()
