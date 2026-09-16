import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import make_campaign, make_character, make_player
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import (
    Being,
    Character,
    CharacterPlayer,
    Entity,
    ItemInstance,
    Ownership,
    Player,
    Tenant,
    User,
    VItemInstance,
)


async def test_create_and_read_being_with_owner_player() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = await make_player(session, tenant_id=tenant.id, campaign_id=campaign.id)

        character = await make_character(
            session, tenant_id=tenant.id, name="Elara", owner_player_id=player.id
        )
        await session.commit()
        character_id, player_id, user_id = character.entity_id, player.id, player.user_id

        fetched = await session.get(Character, character_id)
        assert fetched is not None
        assert fetched.owner_player_id == player_id

        await session.delete(tenant)
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_being_owner_player_is_optional() -> None:
    """No owning player - an NPC, per RFC 0001's framing of "is this a PC"
    as a derived fact (owner_player_id IS NOT NULL). owner_player_id now
    lives on Character, not Being (ADR 0031) - this is about the column's
    own optionality, not the separate "bare Being, no Character row at
    all" case, so the NPC here still gets a Character row, just an
    unowned one.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        npc = await make_character(session, tenant_id=tenant.id, name="Innkeeper")
        await session.commit()
        npc_id = npc.entity_id

        fetched = await session.get(Character, npc_id)
        assert fetched is not None
        assert fetched.owner_player_id is None

        await session.delete(tenant)
        await session.commit()


async def test_deleting_player_sets_being_owner_null_but_deleting_own_entity_cascades() -> None:
    """The same deliberate exception ADR 0019 established for
    item_instance.owner_entity_id, now on Character.owner_player_id (ADR
    0031, moved from Being.owner_player_id per ADR 0025): losing the
    owning player just leaves the character player-less, but the
    character can't outlive its own entity.

    Both checks use a fresh session rather than the one that issued the
    delete - passive_deletes=True means SQLAlchemy never learns about
    either DB-side effect (the SET NULL or the CASCADE), so checking
    through the same session's identity map would return a stale,
    unrefreshed object instead of the real post-delete state.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = await make_player(session, tenant_id=tenant.id, campaign_id=campaign.id)
        user_id, player_id = player.user_id, player.id

        character = await make_character(
            session, tenant_id=tenant.id, name="Elara", owner_player_id=player_id
        )
        await session.commit()
        tenant_id, character_id = tenant.id, character.entity_id

        await session.delete(await session.get_one(Player, player_id))
        await session.commit()

    async with admin_session_factory() as session:
        still_there = await session.get(Character, character_id)
        assert still_there is not None
        assert still_there.owner_player_id is None

        await session.delete(await session.get_one(Entity, character_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Character, character_id) is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_character_player_is_genuinely_many_to_many() -> None:
    """RFC 0002: one player can control more than one character at once (a
    Vampire coterie), and one character can be linked into more than one
    campaign's player row (roster reuse) - both directions, deliberately
    kept separate from Character.owner_player_id's singular "primary owner".
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        campaign_1 = await make_campaign(
            session, tenant_id=tenant.id, name="Coterie One", game_system="Vampire"
        )
        campaign_2 = await make_campaign(
            session, tenant_id=tenant.id, name="Coterie Two", game_system="Vampire"
        )

        player_1 = await make_player(session, tenant_id=tenant.id, campaign_id=campaign_1.id)
        player_2 = await make_player(session, tenant_id=tenant.id, campaign_id=campaign_2.id)

        character_a = await make_character(session, tenant_id=tenant.id, name="Character A")
        character_b = await make_character(session, tenant_id=tenant.id, name="Character B")

        # player_1 controls both characters; character_a is also reused by
        # player_2 in the second campaign.
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character_a.entity_id,
                    player_id=player_1.id,
                    tenant_id=tenant.id,
                ),
                CharacterPlayer(
                    character_entity_id=character_b.entity_id,
                    player_id=player_1.id,
                    tenant_id=tenant.id,
                ),
                CharacterPlayer(
                    character_entity_id=character_a.entity_id,
                    player_id=player_2.id,
                    tenant_id=tenant.id,
                ),
            ]
        )
        await session.commit()
        user_1_id, user_2_id = player_1.user_id, player_2.user_id
        character_a_id, character_b_id = character_a.entity_id, character_b.entity_id
        player_1_id, player_2_id = player_1.id, player_2.id

        # Queried directly rather than via the character_links/player_links
        # relationship attributes: those are plain lazy="select" and would
        # raise MissingGreenlet accessed outside an active await, unlike
        # the eager (lazy="selectin") relationships elsewhere in this
        # schema.
        player_1_characters = (
            (
                await session.execute(
                    select(CharacterPlayer.character_entity_id).where(
                        CharacterPlayer.player_id == player_1_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert set(player_1_characters) == {character_a_id, character_b_id}

        character_a_players = (
            (
                await session.execute(
                    select(CharacterPlayer.player_id).where(
                        CharacterPlayer.character_entity_id == character_a_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert set(character_a_players) == {player_1_id, player_2_id}

        await session.delete(tenant)
        await session.commit()

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_1_id))
        await session.delete(await session.get_one(User, user_2_id))
        await session.commit()


async def test_deleting_character_or_player_cascades_character_player() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player_a = await make_player(session, tenant_id=tenant.id, campaign_id=campaign.id)
        player_b = await make_player(session, tenant_id=tenant.id, campaign_id=campaign.id)

        character = await make_character(session, tenant_id=tenant.id, name="Character")
        tenant_id, character_id = tenant.id, character.entity_id
        player_a_id, player_b_id = player_a.id, player_b.id
        user_a_id, user_b_id = player_a.user_id, player_b.user_id
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character_id, player_id=player_a_id, tenant_id=tenant_id
                ),
                CharacterPlayer(
                    character_entity_id=character_id, player_id=player_b_id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()

        # Deleting one player only removes that one link.
        await session.delete(await session.get_one(Player, player_a_id))
        await session.commit()

    async with admin_session_factory() as session:
        remaining = await session.get(CharacterPlayer, (character_id, player_a_id))
        assert remaining is None
        still_there = await session.get(CharacterPlayer, (character_id, player_b_id))
        assert still_there is not None

        # Deleting the character removes the rest.
        await session.delete(await session.get_one(Entity, character_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CharacterPlayer, (character_id, player_b_id)) is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_a_id))
        await session.delete(await session.get_one(User, user_b_id))
        await session.commit()


async def test_ownership_owned_entity_id_is_unique_globally() -> None:
    """owned_entity_id alone is the primary key (ADR 0025, matching
    Containment.child_entity_id's precedent) - an entity can only have one
    owner at a time.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        owner_1 = Entity(tenant_id=tenant_id, name="Owner One")
        owner_2 = Entity(tenant_id=tenant_id, name="Owner Two")
        owned = Entity(tenant_id=tenant_id, name="Sword")
        session.add_all([owner_1, owner_2, owned])
        await session.flush()

        session.add(
            Ownership(owned_entity_id=owned.id, owner_character_id=owner_1.id, tenant_id=tenant_id)
        )
        await session.commit()

        session.add(
            Ownership(owned_entity_id=owned.id, owner_character_id=owner_2.id, tenant_id=tenant_id)
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        # rollback() expires every object in the session regardless of
        # expire_on_commit - tenant.id itself would need a fresh SELECT to
        # reload, which can't happen outside an active await. tenant_id was
        # captured above for exactly this reason.
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_deleting_owner_character_cascades_ownership_but_owned_entity_survives() -> None:
    """Both of ownership's FKs are ON DELETE CASCADE, unlike
    Being.owner_player_id - the ownership fact is meaningless once either
    side is gone, so the row disappears entirely rather than nulling a
    column (ADR 0025).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        owner = Entity(tenant_id=tenant.id, name="Owner")
        owned = Entity(tenant_id=tenant.id, name="Sword")
        session.add_all([owner, owned])
        await session.flush()
        tenant_id, owner_id, owned_id = tenant.id, owner.id, owned.id
        session.add(
            Ownership(owned_entity_id=owned_id, owner_character_id=owner_id, tenant_id=tenant_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Entity, owner_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Ownership, owned_id) is None
        assert await session.get(Entity, owned_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_deleting_owned_entity_cascades_ownership() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        owner = Entity(tenant_id=tenant.id, name="Owner")
        owned = Entity(tenant_id=tenant.id, name="Sword")
        session.add_all([owner, owned])
        await session.flush()
        tenant_id, owner_id, owned_id = tenant.id, owner.id, owned.id
        session.add(
            Ownership(owned_entity_id=owned_id, owner_character_id=owner_id, tenant_id=tenant_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Entity, owned_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Ownership, owned_id) is None
        assert await session.get(Entity, owner_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_item_instance_ownership_reconciliation_via_v_item_instance() -> None:
    """The core proof for ADR 0025's reconciliation: v_item_instance still
    exposes owner_entity_id (same name/position/type), now derived via a
    join against `ownership` - and deleting the owning character cascades
    the Ownership row away (rather than SET NULL-ing a column the way the
    old item_instance.owner_entity_id placeholder did), leaving the item
    instance itself untouched but ownerless.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        character = Entity(tenant_id=tenant.id, name="Character")
        sword_entity = Entity(tenant_id=tenant.id, name="Sword")
        session.add_all([character, sword_entity])
        await session.flush()
        tenant_id, character_id, sword_id = tenant.id, character.id, sword_entity.id
        session.add(Being(entity_id=character_id, tenant_id=tenant_id))
        session.add(ItemInstance(entity_id=sword_id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=sword_id, owner_character_id=character_id, tenant_id=tenant_id
            )
        )
        await session.commit()

        view_row = await session.get(VItemInstance, sword_id)
        assert view_row is not None
        assert view_row.owner_entity_id == character_id

        await session.delete(await session.get_one(Entity, character_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Ownership, sword_id) is None
        assert await session.get(ItemInstance, sword_id) is not None

        view_row_after = await session.get(VItemInstance, sword_id)
        assert view_row_after is not None
        assert view_row_after.owner_entity_id is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_being_character_player_ownership_rls_isolates_tenants() -> None:
    """Standard tenant_isolation shape across all three new tables in one
    pass, matching test_campaign_player.py's own precedent - `engine` is
    the app's own real, restricted connection since ADR 0021.
    """
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        user = (
            await session.execute(
                text("INSERT INTO app_user (authgear_subject_id) VALUES (:s) RETURNING id"),
                {"s": f"authgear|rls-being-{uuid.uuid4()}"},
            )
        ).scalar_one()

        # campaign.entity_id (ADR 0030) needs a real Entity row to point at.
        entity_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'A') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'B') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        campaign_a = (
            await session.execute(
                text(
                    "INSERT INTO campaign "
                    "(tenant_id, name, game_system, slug, description, entity_id) "
                    "VALUES (:t, 'A', 'D&D 5e', 'campaign-a', '', :e) RETURNING id"
                ),
                {"t": tenant_a, "e": entity_a},
            )
        ).scalar_one()
        campaign_b = (
            await session.execute(
                text(
                    "INSERT INTO campaign "
                    "(tenant_id, name, game_system, slug, description, entity_id) "
                    "VALUES (:t, 'B', 'D&D 5e', 'campaign-b', '', :e) RETURNING id"
                ),
                {"t": tenant_b, "e": entity_b},
            )
        ).scalar_one()
        player_a = (
            await session.execute(
                text(
                    "INSERT INTO player (user_id, campaign_id, tenant_id) "
                    "VALUES (:u, :c, :t) RETURNING id"
                ),
                {"u": user, "c": campaign_a, "t": tenant_a},
            )
        ).scalar_one()
        player_b = (
            await session.execute(
                text(
                    "INSERT INTO player (user_id, campaign_id, tenant_id) "
                    "VALUES (:u, :c, :t) RETURNING id"
                ),
                {"u": user, "c": campaign_b, "t": tenant_b},
            )
        ).scalar_one()

        character_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'char-a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        character_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'char-b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        owned_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'owned-a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        owned_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'owned-b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()

        await session.execute(
            text("INSERT INTO being (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": character_a, "t": tenant_a},
        )
        await session.execute(
            text("INSERT INTO being (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": character_b, "t": tenant_b},
        )
        # owner_player_id lives on character now, not being (ADR 0031).
        await session.execute(
            text(
                "INSERT INTO character (entity_id, owner_player_id, tenant_id) VALUES (:e, :p, :t)"
            ),
            {"e": character_a, "p": player_a, "t": tenant_a},
        )
        await session.execute(
            text(
                "INSERT INTO character (entity_id, owner_player_id, tenant_id) VALUES (:e, :p, :t)"
            ),
            {"e": character_b, "p": player_b, "t": tenant_b},
        )
        await session.execute(
            text(
                "INSERT INTO character_player (character_entity_id, player_id, tenant_id) "
                "VALUES (:c, :p, :t)"
            ),
            {"c": character_a, "p": player_a, "t": tenant_a},
        )
        await session.execute(
            text(
                "INSERT INTO character_player (character_entity_id, player_id, tenant_id) "
                "VALUES (:c, :p, :t)"
            ),
            {"c": character_b, "p": player_b, "t": tenant_b},
        )
        await session.execute(
            text(
                "INSERT INTO ownership (owned_entity_id, owner_character_id, tenant_id) "
                "VALUES (:o, :c, :t)"
            ),
            {"o": owned_a, "c": character_a, "t": tenant_a},
        )
        await session.execute(
            text(
                "INSERT INTO ownership (owned_entity_id, owner_character_id, tenant_id) "
                "VALUES (:o, :c, :t)"
            ),
            {"o": owned_b, "c": character_b, "t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            beings = (await conn.execute(text("SELECT entity_id FROM being"))).scalars().all()
            assert list(beings) == [character_a]
            links = (
                (await conn.execute(text("SELECT character_entity_id FROM character_player")))
                .scalars()
                .all()
            )
            assert list(links) == [character_a]
            owned = (
                (await conn.execute(text("SELECT owned_entity_id FROM ownership"))).scalars().all()
            )
            assert list(owned) == [owned_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            beings = (await conn.execute(text("SELECT entity_id FROM being"))).scalars().all()
            assert list(beings) == [character_b]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT entity_id FROM being"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM ownership WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM character_player WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM character WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM being WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM player WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM campaign WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(text("DELETE FROM app_user WHERE id = :u"), {"u": user})
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()
