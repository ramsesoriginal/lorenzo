import uuid

from _admin_db import admin_session_factory
from conftest import make_campaign, make_character, make_player

from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
    Containment,
    Entity,
    GroupMember,
    Information,
    Membership,
    MembershipRole,
    Ownership,
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
        assert visibility.gm_reachable_entity_ids == frozenset()

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


# --- RFC 0009 / ADR 0035: campaign-scoped GM visibility ---------------------
#
# Information() below is built transient (never added to the session, never
# committed) with knowledge_links explicitly set to [] - InformationVisibility
# is documented as directly unit-testable against hand-built Information
# objects with no session at all, and can_see only ever reads entity_id/
# is_public/knowledge_links off it, none of which need a real row to exist.


async def test_resolve_information_visibility_gm_reachable_includes_characters_directly() -> None:
    """RFC 0009's step 1: a campaign's own characters are GM-visible
    directly, not just their belongings - flagged in the RFC itself as easy
    to misread as an inventory-only walk.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        gm_user = _make_user()
        session.add_all([tenant, gm_user])
        await session.flush()
        tenant_id, gm_user_id = tenant.id, gm_user.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Ashen Crown")
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign.id))
        await session.commit()
        character_id, player_user_id = character.entity_id, player.user_id

        visibility = await resolve_information_visibility(
            session, user_id=gm_user_id, tenant_id=tenant_id
        )
        assert character_id in visibility.gm_reachable_entity_ids

        secret = Information(
            tenant_id=tenant_id,
            entity_id=character_id,
            title="Secretly a doppelganger",
            type="gm-note",
            knowledge_links=[],
        )
        assert visibility.can_see(secret) is True

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_resolve_information_visibility_gm_reachable_includes_owned_and_contained_items() -> (
    None
):
    """RFC 0009's steps 2-3: extend through Ownership, then through
    Containment recursively - the milestone's own shape (Ashfang owned
    directly by a character; a coin purse nested inside a backpack that
    same character owns, two containment levels deep).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        gm_user = _make_user()
        session.add_all([tenant, gm_user])
        await session.flush()
        tenant_id, gm_user_id = tenant.id, gm_user.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Ashen Crown")
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign.id))

        sword = Entity(tenant_id=tenant_id, name="Ashfang")
        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        coin_purse = Entity(tenant_id=tenant_id, name="Coin Purse")
        session.add_all([sword, backpack, coin_purse])
        await session.flush()
        session.add_all(
            [
                Ownership(
                    owned_entity_id=sword.id,
                    owner_character_id=character.entity_id,
                    tenant_id=tenant_id,
                ),
                Ownership(
                    owned_entity_id=backpack.id,
                    owner_character_id=character.entity_id,
                    tenant_id=tenant_id,
                ),
                Containment(
                    child_entity_id=coin_purse.id,
                    parent_entity_id=backpack.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        sword_id, coin_purse_id, player_user_id = sword.id, coin_purse.id, player.user_id

        visibility = await resolve_information_visibility(
            session, user_id=gm_user_id, tenant_id=tenant_id
        )
        assert sword_id in visibility.gm_reachable_entity_ids
        assert coin_purse_id in visibility.gm_reachable_entity_ids

        cursed = Information(
            tenant_id=tenant_id,
            entity_id=sword_id,
            title="Ashfang is cursed",
            type="gm-note",
            knowledge_links=[],
        )
        assert visibility.can_see(cursed) is True

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_resolve_information_visibility_gm_reachable_includes_the_room() -> None:
    """ADR 0046: the upward-widening this ADR adds - a character placed
    inside a location entity via Containment (RFC 0001's own "a character
    in a room" example, already exercised for real in
    test_api_characters.py) makes that room, and everything else sharing
    it, GM-reachable too - not just what the character owns/carries.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        gm_user = _make_user()
        session.add_all([tenant, gm_user])
        await session.flush()
        tenant_id, gm_user_id = tenant.id, gm_user.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Ashen Crown")
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign.id))

        tavern = Entity(tenant_id=tenant_id, name="The Prancing Pony")
        bartender = Entity(tenant_id=tenant_id, name="Barliman")
        world = Entity(tenant_id=tenant_id, name="Bree")
        session.add_all([tavern, bartender, world])
        await session.flush()
        session.add_all(
            [
                # Alice is in the tavern; the bartender is too (a sibling,
                # not owned/contained by Alice at all); the tavern itself is
                # in the wider town.
                Containment(
                    child_entity_id=character.entity_id,
                    parent_entity_id=tavern.id,
                    tenant_id=tenant_id,
                ),
                Containment(
                    child_entity_id=bartender.id, parent_entity_id=tavern.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=tavern.id, parent_entity_id=world.id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()
        tavern_id, bartender_id, world_id, player_user_id = (
            tavern.id,
            bartender.id,
            world.id,
            player.user_id,
        )

        visibility = await resolve_information_visibility(
            session, user_id=gm_user_id, tenant_id=tenant_id
        )
        assert tavern_id in visibility.gm_reachable_entity_ids
        assert bartender_id in visibility.gm_reachable_entity_ids
        assert world_id in visibility.gm_reachable_entity_ids

        barliman_is_a_spy = Information(
            tenant_id=tenant_id,
            entity_id=bartender_id,
            title="Barliman is secretly a spy",
            type="gm-note",
            knowledge_links=[],
        )
        assert visibility.can_see(barliman_is_a_spy) is True

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_resolve_information_visibility_gm_reachable_excludes_a_campaign_not_gmd() -> None:
    """A GM of campaign A must not see campaign C's own character's items
    just because both campaigns exist in the same tenant - GM sight is
    per-campaign-grant, not tenant-wide.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        gm_user = _make_user()
        session.add_all([tenant, gm_user])
        await session.flush()
        tenant_id, gm_user_id = tenant.id, gm_user.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="Campaign A")
        campaign_c = await make_campaign(session, tenant_id=tenant_id, name="Campaign C")
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign_a.id))

        player_c = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_c.id)
        character_c = await make_character(session, tenant_id=tenant_id, name="Charlie")
        session.add(
            CharacterPlayer(
                character_entity_id=character_c.entity_id,
                player_id=player_c.id,
                tenant_id=tenant_id,
            )
        )
        item_c = Entity(tenant_id=tenant_id, name="Campaign C's Sword")
        session.add(item_c)
        await session.flush()
        session.add(
            Ownership(
                owned_entity_id=item_c.id,
                owner_character_id=character_c.entity_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        character_c_id, item_c_id, player_c_user_id = (
            character_c.entity_id,
            item_c.id,
            player_c.user_id,
        )

        visibility = await resolve_information_visibility(
            session, user_id=gm_user_id, tenant_id=tenant_id
        )
        assert character_c_id not in visibility.gm_reachable_entity_ids
        assert item_c_id not in visibility.gm_reachable_entity_ids

        secret = Information(
            tenant_id=tenant_id,
            entity_id=item_c_id,
            title="Not Zorro's business",
            type="gm-note",
            knowledge_links=[],
        )
        assert visibility.can_see(secret) is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.delete(await session.get_one(User, player_c_user_id))
        await session.commit()


async def test_resolve_information_visibility_gm_reachable_unions_every_campaign_gmd() -> None:
    """RFC 0009: "the full GM-reachable set is the union of this walk
    across every campaign the caller GMs" - GMing two campaigns at once
    grants exactly the union of each campaign's own bounded reachable set,
    not blanket tenant-wide visibility just because both grants share a
    user.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        gm_user = _make_user()
        session.add_all([tenant, gm_user])
        await session.flush()
        tenant_id, gm_user_id = tenant.id, gm_user.id
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="Campaign A")
        campaign_c = await make_campaign(session, tenant_id=tenant_id, name="Campaign C")
        await session.flush()
        session.add_all(
            [
                CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign_a.id),
                CampaignGm(tenant_id=tenant_id, user_id=gm_user_id, campaign_id=campaign_c.id),
            ]
        )

        player_a = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_a.id)
        character_a = await make_character(session, tenant_id=tenant_id, name="Alice")
        player_c = await make_player(session, tenant_id=tenant_id, campaign_id=campaign_c.id)
        character_c = await make_character(session, tenant_id=tenant_id, name="Charlie")
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character_a.entity_id,
                    player_id=player_a.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=character_c.entity_id,
                    player_id=player_c.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        character_a_id, character_c_id = character_a.entity_id, character_c.entity_id
        player_a_user_id, player_c_user_id = player_a.user_id, player_c.user_id

        visibility = await resolve_information_visibility(
            session, user_id=gm_user_id, tenant_id=tenant_id
        )
        assert visibility.gm_reachable_entity_ids == frozenset({character_a_id, character_c_id})

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.delete(await session.get_one(User, player_a_user_id))
        await session.delete(await session.get_one(User, player_c_user_id))
        await session.commit()


async def test_resolve_information_visibility_owner_without_gm_standing_hides_secret() -> None:
    """ADR 0028's "administrative access != automatic character knowledge"
    principle, re-confirmed by RFC 0009/ADR 0035: a tenant OWNER with no
    CampaignGm standing anywhere still can't see a GM-only secret on a
    character's owned item - an owner's administrative role must not imply
    GM omniscience either.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        owner_user = _make_user()
        session.add_all([tenant, owner_user])
        await session.flush()
        tenant_id, owner_user_id = tenant.id, owner_user.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=owner_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
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
        await session.commit()
        sword_id, player_user_id = sword.id, player.user_id

        visibility = await resolve_information_visibility(
            session, user_id=owner_user_id, tenant_id=tenant_id
        )
        assert visibility.is_orga is False
        assert sword_id not in visibility.gm_reachable_entity_ids

        secret = Information(
            tenant_id=tenant_id,
            entity_id=sword_id,
            title="Cursed",
            type="gm-note",
            knowledge_links=[],
        )
        assert visibility.can_see(secret) is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, owner_user_id))
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()
