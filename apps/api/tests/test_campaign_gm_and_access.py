import uuid

from _admin_db import admin_session_factory
from conftest import make_campaign
from sqlalchemy import text

from lorenzo_api.campaign_access import can_access_campaign, is_tenant_admin, is_tenant_participant
from lorenzo_api.db import engine
from lorenzo_api.models import (
    Campaign,
    CampaignGm,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    TenantAdminCampaignOptOut,
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
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()

        session.add(CampaignGm(tenant_id=tenant.id, user_id=user.id, campaign_id=campaign.id))
        await session.commit()

        fetched = await session.get(CampaignGm, (tenant.id, user.id, campaign.id))
        assert fetched is not None

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_create_and_read_tenant_admin_campaign_opt_out() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()

        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant.id, user_id=user.id, campaign_id=campaign.id)
        )
        await session.commit()

        fetched = await session.get(TenantAdminCampaignOptOut, (tenant.id, user.id, campaign.id))
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
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        opt_out_key = (tenant_id, user_id, campaign_id)
        assert await session.get(TenantAdminCampaignOptOut, opt_out_key) is None
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
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(Campaign, campaign_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        opt_out_key = (tenant_id, user_id, campaign_id)
        assert await session.get(TenantAdminCampaignOptOut, opt_out_key) is None
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
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id))
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
        )
        await session.commit()

        await session.delete(await session.get_one(User, user_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is None
        opt_out_key = (tenant_id, user_id, campaign_id)
        assert await session.get(TenantAdminCampaignOptOut, opt_out_key) is None
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
                "INSERT INTO tenant_admin_campaign_opt_out (tenant_id, user_id, campaign_id) "
                "VALUES (:t, :u, :c)"
            ),
            {"t": tenant_a, "u": user, "c": campaign_a},
        )
        await session.execute(
            text(
                "INSERT INTO tenant_admin_campaign_opt_out (tenant_id, user_id, campaign_id) "
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
                (await conn.execute(text("SELECT campaign_id FROM tenant_admin_campaign_opt_out")))
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

        # Neither app.tenant_id nor app.user_id set - campaign_gm's own
        # NULLIF(...)::uuid self-access relaxation (ADR 0030/RFC 0003,
        # added for GET /tenants) returns empty rather than erroring here,
        # matching membership's own precedent (ADR 0023) exactly - not the
        # stricter single-argument current_setting(name) every other
        # RLS-protected table still uses.
        async with engine.begin() as conn:
            gm_campaigns = (
                (await conn.execute(text("SELECT campaign_id FROM campaign_gm"))).scalars().all()
            )
            assert list(gm_campaigns) == []

        # Only app.user_id set - the self-access path GET /tenants relies
        # on: every campaign this user GMs, across both tenants, with no
        # tenant scoping at all.
        async with engine.begin() as conn:
            await conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user)})
            gm_campaigns = (
                (await conn.execute(text("SELECT campaign_id FROM campaign_gm"))).scalars().all()
            )
            assert sorted(gm_campaigns) == sorted([campaign_a, campaign_b])
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM tenant_admin_campaign_opt_out WHERE tenant_id IN (:a, :b)"),
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
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
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
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
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
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
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
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.ORGA))
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
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


async def test_can_access_campaign_via_owner_membership_without_opt_out() -> None:
    """ADR 0030/RFC 0003: can_access_campaign's blanket bypass widened from
    ORGA-only to is_tenant_admin (OWNER or ORGA) - this test used to assert
    the opposite (OWNER, with no player/gm row, could NOT reach a campaign)
    to prove the old ORGA-only rule; that rule is exactly what this ADR
    revises, so the assertion flips. Mirrors
    test_can_access_campaign_via_orga_membership_without_opt_out below.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
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


async def test_cannot_access_campaign_as_owner_with_opt_out() -> None:
    """The opt-out mechanism widens symmetrically (ADR 0030/RFC 0003): an
    OWNER can suppress their own new bypass exactly like an ORGA already
    could. Mirrors test_cannot_access_campaign_as_orga_with_opt_out above.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        tenant_id, user_id, campaign_id = tenant.id, user.id, campaign.id
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id)
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


async def test_cannot_access_campaign_with_no_membership_at_all() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        campaign = await make_campaign(
            session, tenant_id=tenant.id, name="Campaign", game_system="D&D 5e"
        )
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


async def test_is_tenant_admin_true_for_owner_and_orga() -> None:
    """ADR 0030/RFC 0003: is_tenant_admin widens is_tenant_orga's ORGA-only
    check to admit OWNER too - checked directly against both roles here,
    not just through can_access_campaign's own bypass branch.
    """
    async with admin_session_factory() as session:
        for role in (MembershipRole.OWNER, MembershipRole.ORGA):
            tenant = Tenant()
            user = _make_user()
            session.add_all([tenant, user])
            await session.flush()
            tenant_id, user_id = tenant.id, user.id
            session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=role))
            await session.commit()

            assert await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id) is True

            await session.delete(tenant)
            await session.delete(user)
            await session.commit()


async def test_is_tenant_admin_false_with_no_membership() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        await session.commit()

        assert await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id) is False

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()


async def test_is_tenant_participant_via_membership_player_or_campaign_gm() -> None:
    """ADR 0030/RFC 0003: any of the three rows, anywhere in the tenant,
    is enough - each checked independently, same short-circuiting shape as
    can_access_campaign itself.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id

        member = _make_user()
        session.add(member)
        await session.flush()
        session.add(Membership(tenant_id=tenant_id, user_id=member.id, role=MembershipRole.OWNER))

        player_user = _make_user()
        session.add(player_user)
        await session.flush()
        session.add(Player(user_id=player_user.id, campaign_id=campaign_id, tenant_id=tenant_id))

        gm_user = _make_user()
        session.add(gm_user)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user.id, campaign_id=campaign_id))

        await session.commit()

        for user_id in (member.id, player_user.id, gm_user.id):
            is_participant = await is_tenant_participant(
                session, tenant_id=tenant_id, user_id=user_id
            )
            assert is_participant is True

        await session.delete(tenant)
        await session.delete(member)
        await session.delete(player_user)
        await session.delete(gm_user)
        await session.commit()


async def test_is_tenant_participant_false_with_no_relationship_at_all() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = _make_user()
        session.add_all([tenant, user])
        await session.flush()
        tenant_id, user_id = tenant.id, user.id
        await session.commit()

        is_participant = await is_tenant_participant(session, tenant_id=tenant_id, user_id=user_id)
        assert is_participant is False

        await session.delete(tenant)
        await session.delete(user)
        await session.commit()
