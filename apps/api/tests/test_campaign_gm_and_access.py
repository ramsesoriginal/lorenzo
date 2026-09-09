import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lorenzo_api.campaign_access import can_access_campaign
from lorenzo_api.db import engine
from lorenzo_api.models import (
    Campaign,
    CampaignGm,
    Membership,
    MembershipRole,
    OrgaCampaignOptOut,
    Player,
    Tenant,
    User,
)


def _make_user() -> User:
    return User(authgear_subject_id=f"authgear|campaign-gm-{uuid.uuid4()}")


async def test_create_and_read_campaign_gm() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()

        session.add(CampaignGm(tenant_id=tenant.id, user_id=user.id, campaign_id=campaign.id))
        await session.commit()

        fetched = await session.get(CampaignGm, (tenant.id, user.id, campaign.id))
        assert fetched is not None

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_create_and_read_orga_campaign_opt_out() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()

        session.add(
            OrgaCampaignOptOut(tenant_id=tenant.id, user_id=user.id, campaign_id=campaign.id)
        )
        await session.commit()

        fetched = await session.get(OrgaCampaignOptOut, (tenant.id, user.id, campaign.id))
        assert fetched is not None

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_deleting_tenant_cascades_campaign_gm_and_opt_out() -> None:
    """passive_deletes=True means the ORM never learns about the DB-side
    CASCADE - checked through a fresh session, not the one that issued the
    delete, matching every other cascade test in this codebase.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            OrgaCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(OrgaCampaignOptOut, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(User, user_id) is not None

        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_deleting_campaign_cascades_campaign_gm_and_opt_out_but_not_user_or_tenant() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            OrgaCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Campaign, campaign_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(OrgaCampaignOptOut, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(Tenant, tenant_id) is not None
        assert await session.get(User, user_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_deleting_user_cascades_campaign_gm_and_opt_out_but_not_campaign() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            OrgaCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(User, user_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(OrgaCampaignOptOut, (tenant_id, user_id, campaign_id)) is None
        assert await session.get(Campaign, campaign_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_campaign_gm_and_opt_out_rls_isolates_tenants() -> None:
    """Standard tenant_isolation shape for both tables in one pass,
    matching test_campaign_player.py's own precedent - `engine` is the
    app's own real, restricted connection since ADR 0021.
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
                {"s": f"authgear|rls-campaign-gm-{uuid.uuid4()}"},
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
            text("INSERT INTO campaign_gm (tenant_id, user_id, campaign_id) VALUES (:t, :u, :c)"),
            {"t": tenant_a, "u": user, "c": campaign_a},
        )
        await session.execute(
            text("INSERT INTO campaign_gm (tenant_id, user_id, campaign_id) VALUES (:t, :u, :c)"),
            {"t": tenant_b, "u": user, "c": campaign_b},
        )
        await session.execute(
            text(
                "INSERT INTO orga_campaign_opt_out (tenant_id, user_id, campaign_id) "
                "VALUES (:t, :u, :c)"
            ),
            {"t": tenant_a, "u": user, "c": campaign_a},
        )
        await session.execute(
            text(
                "INSERT INTO orga_campaign_opt_out (tenant_id, user_id, campaign_id) "
                "VALUES (:t, :u, :c)"
            ),
            {"t": tenant_b, "u": user, "c": campaign_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            gm_campaigns = (
                (await conn.execute(text("SELECT campaign_id FROM campaign_gm"))).scalars().all()
            )
            assert list(gm_campaigns) == [campaign_a]
            opt_out_campaigns = (
                (await conn.execute(text("SELECT campaign_id FROM orga_campaign_opt_out")))
                .scalars()
                .all()
            )
            assert list(opt_out_campaigns) == [campaign_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            gm_campaigns = (
                (await conn.execute(text("SELECT campaign_id FROM campaign_gm"))).scalars().all()
            )
            assert list(gm_campaigns) == [campaign_b]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT campaign_id FROM campaign_gm"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM orga_campaign_opt_out WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM campaign_gm WHERE tenant_id IN (:a, :b)"),
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


async def test_can_access_campaign_via_player_row() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is True
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_can_access_campaign_via_campaign_gm_row() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is True
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_can_access_campaign_via_orga_membership_without_opt_out() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.ORGA))
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is True
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_cannot_access_campaign_as_orga_with_opt_out() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.ORGA))
        session.add(
            OrgaCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_cannot_access_campaign_as_non_orga_member_with_no_player_or_gm_row() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_cannot_access_campaign_with_no_membership_at_all() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = Campaign(tenant_id=tenant.id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        await session.commit()

        assert (
            await can_access_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            is False
        )

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()
