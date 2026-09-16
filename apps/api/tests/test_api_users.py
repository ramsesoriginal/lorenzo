import uuid
from collections.abc import AsyncGenerator

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient

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

# --- DELETE /me (ADR 0036/RFC 0007) ---------------------------------------
#
# test_user_id is a session-scoped fixture (conftest.py) - a real,
# persistent app_user row every other test file in this suite also relies
# on existing. Every test below that actually succeeds in deleting it must
# recreate it before finishing, in a try/finally, so a failed assertion
# can't leave the row missing for every test that runs afterward - the
# fixture's own teardown deletes it exactly once, at session end.


@pytest.fixture
async def _restore_test_user_id(test_user_id: uuid.UUID) -> AsyncGenerator[None]:
    yield
    async with admin_session_factory() as session:
        if await session.get(User, test_user_id) is None:
            session.add(User(id=test_user_id, authgear_subject_id="conftest-fixture-user"))
            await session.commit()


async def test_delete_me_removes_the_user(
    client: AsyncClient, test_user_id: uuid.UUID, _restore_test_user_id: None
) -> None:
    """The plain happy path: a caller with no OWNER memberships at all can
    always delete themselves.
    """
    response = await client.delete("/me")
    assert response.status_code == 204

    async with admin_session_factory() as session:
        assert await session.get(User, test_user_id) is None


async def test_delete_me_409_when_sole_owner_of_a_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.delete("/me")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    async with admin_session_factory() as session:
        # Nothing was deleted - the user survives the failed guard.
        assert await session.get(User, test_user_id) is not None

    await delete_tenant(tenant_id)


async def test_delete_me_204_when_a_co_owner_exists(
    client: AsyncClient, test_user_id: uuid.UUID, _restore_test_user_id: None
) -> None:
    """Not the *only* OWNER - the guard only fires for a sole OWNER, not
    merely being an OWNER at all.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        co_owner = User(authgear_subject_id=f"authgear|co-owner-{uuid.uuid4()}")
        session.add(co_owner)
        await session.flush()
        session.add(Membership(tenant_id=tenant_id, user_id=co_owner.id, role=MembershipRole.OWNER))
        await session.commit()
        co_owner_id = co_owner.id

    response = await client.delete("/me")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(User, test_user_id) is None
        assert await session.get(Membership, (tenant_id, co_owner_id)) is not None

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, co_owner_id))
        await session.commit()


async def test_delete_me_409_checks_every_owned_tenant_before_deleting_anything(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Two tenants: sole OWNER of one, co-owned in the other - the guard
    must still fire (and leave *both* tenants' memberships untouched), not
    just delete the safe one and 409 on the other.
    """
    tenant_a_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        tenant_b = Tenant()
        session.add(tenant_b)
        await session.flush()
        tenant_b_id = tenant_b.id
        session.add(
            Membership(tenant_id=tenant_b_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        co_owner = User(authgear_subject_id=f"authgear|co-owner-{uuid.uuid4()}")
        session.add(co_owner)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant_b_id, user_id=co_owner.id, role=MembershipRole.OWNER)
        )
        await session.commit()
        co_owner_id = co_owner.id

    response = await client.delete("/me")

    assert response.status_code == 409
    async with admin_session_factory() as session:
        assert await session.get(User, test_user_id) is not None
        assert await session.get(Membership, (tenant_a_id, test_user_id)) is not None
        assert await session.get(Membership, (tenant_b_id, test_user_id)) is not None

    await delete_tenant(tenant_a_id)
    await delete_tenant(tenant_b_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, co_owner_id))
        await session.commit()


async def test_delete_me_cascades_and_nulls_attribution_across_every_table(
    client: AsyncClient, test_user_id: uuid.UUID, _restore_test_user_id: None
) -> None:
    """ADR 0029/0036: deleting the acting user cascades every Membership/
    Player/CampaignGm/TenantAdminCampaignOptOut row *this user held*, and
    SETs NULL every created_by/updated_by *this user left behind* on other
    rows they didn't hold a stake in themselves - a different, wider set.
    Verified empirically (a real DELETE, not just reasoned from the FK
    definitions) per this ADR's own explicit callout.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        # A co-owner, so the guard doesn't fire for this tenant.
        co_owner = User(authgear_subject_id=f"authgear|co-owner-{uuid.uuid4()}")
        session.add(co_owner)
        await session.flush()
        session.add(Membership(tenant_id=tenant_id, user_id=co_owner.id, role=MembershipRole.OWNER))

        # test_user_id's own ORGA membership - held by them, must be
        # deleted outright (not just have its attribution nulled).
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))

        # A membership *invited by* test_user_id, but held by someone else -
        # this row survives, only its created_by/updated_by are nulled.
        invitee = User(authgear_subject_id=f"authgear|invitee-{uuid.uuid4()}")
        session.add(invitee)
        await session.flush()
        session.add(
            Membership(
                tenant_id=tenant_id,
                user_id=invitee.id,
                role=MembershipRole.ORGA,
                created_by=test_user_id,
                updated_by=test_user_id,
            )
        )

        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign.created_by = test_user_id
        campaign.updated_by = test_user_id
        campaign_entity = await session.get_one(Entity, campaign.entity_id)
        campaign_entity.created_by = test_user_id
        campaign_entity.updated_by = test_user_id

        character = await make_character(session, tenant_id=tenant_id)
        await session.flush()
        character.created_by = test_user_id
        character.updated_by = test_user_id

        # A player row test_user_id added (as the managing GM) for someone
        # else - held by invitee, attributed to test_user_id.
        player = Player(
            user_id=invitee.id,
            campaign_id=campaign.id,
            tenant_id=tenant_id,
            created_by=test_user_id,
            updated_by=test_user_id,
        )
        session.add(player)

        session.add(
            CampaignGm(
                tenant_id=tenant_id,
                user_id=invitee.id,
                campaign_id=campaign.id,
                created_by=test_user_id,
            )
        )
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id,
                user_id=invitee.id,
                campaign_id=campaign.id,
                created_by=test_user_id,
            )
        )
        await session.commit()

        campaign_id, campaign_entity_id = campaign.id, campaign.entity_id
        character_entity_id = character.entity_id
        invitee_id, player_id = invitee.id, player.id

    response = await client.delete("/me")
    assert response.status_code == 204

    async with admin_session_factory() as session:
        assert await session.get(User, test_user_id) is None
        # Held-by-test_user_id rows are gone outright.
        assert await session.get(Membership, (tenant_id, test_user_id)) is None

        # Rows test_user_id merely attributed to survive, attribution nulled.
        invited_membership = await session.get_one(Membership, (tenant_id, invitee_id))
        assert invited_membership.created_by is None
        assert invited_membership.updated_by is None

        campaign_row = await session.get_one(Campaign, campaign_id)
        assert campaign_row.created_by is None
        assert campaign_row.updated_by is None

        campaign_entity_row = await session.get_one(Entity, campaign_entity_id)
        assert campaign_entity_row.created_by is None
        assert campaign_entity_row.updated_by is None

        character_row = await session.get_one(Character, character_entity_id)
        assert character_row.created_by is None
        assert character_row.updated_by is None

        player_row = await session.get_one(Player, player_id)
        assert player_row.created_by is None
        assert player_row.updated_by is None

        gm_row = await session.get_one(CampaignGm, (tenant_id, invitee_id, campaign_id))
        assert gm_row.created_by is None

        opt_out_row = await session.get_one(
            TenantAdminCampaignOptOut, (tenant_id, invitee_id, campaign_id)
        )
        assert opt_out_row.created_by is None

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, invitee_id))
        await session.commit()
