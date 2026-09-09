import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import Campaign, Player, Tenant, User


async def test_create_and_read_campaign() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        campaign = Campaign(tenant_id=tenant.id, name="The Sunken Keep", game_system="D&D 5e")
        session.add(campaign)
        await session.commit()

        assert campaign.id is not None
        assert campaign.created_at is not None
        assert campaign.updated_at is not None

        fetched = await session.get(Campaign, campaign.id)
        assert fetched is not None
        assert fetched.name == "The Sunken Keep"
        assert fetched.game_system == "D&D 5e"

        await session.delete(tenant)
        await session.commit()


async def test_create_and_read_player() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|player-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="One-Shot", game_system="Blades in the Dark")
        session.add(campaign)
        await session.flush()

        player = Player(user_id=user.id, campaign_id=campaign.id, tenant_id=tenant.id)
        session.add(player)
        await session.commit()

        fetched = await session.get(Player, player.id)
        assert fetched is not None
        assert fetched.user_id == user.id
        assert fetched.campaign_id == campaign.id
        assert fetched.tenant_id == tenant.id

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_player_is_unique_per_campaign_and_user() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|dupe-player-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()

        session.add_all(
            [
                Player(user_id=user.id, campaign_id=campaign.id, tenant_id=tenant.id),
                Player(user_id=user.id, campaign_id=campaign.id, tenant_id=tenant.id),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_deleting_tenant_cascades_campaign_and_player() -> None:
    """passive_deletes=True means the ORM never learns about the DB-side
    CASCADE - checked through a fresh session, not the one that issued the
    delete, which would just return its own stale identity-map object.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|cascade-tenant-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Campaign, campaign_id) is None
        # Deleting the tenant cascades campaign+player, but the user itself
        # (global, not tenant-scoped) must survive it.
        assert await session.get(User, user_id) is not None

        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_deleting_campaign_cascades_player_but_not_user_or_tenant() -> None:
    """See test_deleting_tenant_cascades_campaign_and_player for why the
    post-delete checks use a fresh session.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|cascade-campaign-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        player = Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id = player.id

        await session.delete(await session.get_one(Campaign, campaign_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Player, player_id) is None
        assert await session.get(Tenant, tenant_id) is not None
        assert await session.get(User, user_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_deleting_user_cascades_player_but_not_campaign() -> None:
    """See test_deleting_tenant_cascades_campaign_and_player for why the
    post-delete checks use a fresh session.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|cascade-user-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        player = Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id = player.id

        await session.delete(await session.get_one(User, user_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(Player, player_id) is None
        assert await session.get(Campaign, campaign_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_campaign_and_player_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """Standard tenant_isolation shape, no self-access carve-out like
    membership's (ADR 0023/0024) - `engine` is the app's own real,
    restricted connection since ADR 0021.
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
                {"s": f"authgear|rls-campaign-player-{uuid.uuid4()}"},
            )
        ).scalar_one()

        campaign_a = (
            await session.execute(
                text(
                    "INSERT INTO campaign (tenant_id, name, game_system) "
                    "VALUES (:t, 'A', 'D&D 5e') RETURNING id"
                ),
                {"t": tenant_a},
            )
        ).scalar_one()
        campaign_b = (
            await session.execute(
                text(
                    "INSERT INTO campaign (tenant_id, name, game_system) "
                    "VALUES (:t, 'B', 'D&D 5e') RETURNING id"
                ),
                {"t": tenant_b},
            )
        ).scalar_one()
        await session.execute(
            text("INSERT INTO player (user_id, campaign_id, tenant_id) VALUES (:u, :c, :t)"),
            {"u": user, "c": campaign_a, "t": tenant_a},
        )
        await session.execute(
            text("INSERT INTO player (user_id, campaign_id, tenant_id) VALUES (:u, :c, :t)"),
            {"u": user, "c": campaign_b, "t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            names = (await conn.execute(text("SELECT name FROM campaign"))).scalars().all()
            assert list(names) == ["A"]
            campaign_ids = (
                (await conn.execute(text("SELECT campaign_id FROM player"))).scalars().all()
            )
            assert list(campaign_ids) == [campaign_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            names = (await conn.execute(text("SELECT name FROM campaign"))).scalars().all()
            assert list(names) == ["B"]
            campaign_ids = (
                (await conn.execute(text("SELECT campaign_id FROM player"))).scalars().all()
            )
            assert list(campaign_ids) == [campaign_b]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT name FROM campaign"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM player WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM campaign WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(text("DELETE FROM app_user WHERE id = :u"), {"u": user})
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()
