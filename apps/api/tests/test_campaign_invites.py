"""Campaign invite management (create / list / revoke) and the
`campaign_invite` RLS policies - see ADR 0092.
"""

import uuid
from datetime import UTC, datetime, timedelta

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text, update

from lorenzo_api.db import async_session_factory
from lorenzo_api.invites import generate_token, hash_token
from lorenzo_api.models import AuditLog, CampaignInvite, Player, Tenant


def _in(**delta: int) -> str:
    return (datetime.now(tz=UTC) + timedelta(**delta)).isoformat()


async def _campaign(client: AsyncClient, tenant_id: uuid.UUID) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Invites",
            "game_system": "D&D 5e",
            "slug": f"invites-{uuid.uuid4()}",
            "description": "",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _entries(tenant_id: uuid.UUID, action: str) -> list[AuditLog]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.tenant_id == tenant_id, AuditLog.action == action
                    )
                )
            )
            .scalars()
            .all()
        )


async def test_create_returns_the_token_once_and_stores_only_its_hash(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    created = await client.post(base, json={"expires_at": _in(days=7), "max_uses": 5})

    assert created.status_code == 201, created.text
    body = created.json()
    token = body["token"]
    assert len(token) >= 40 and body["is_active"] is True
    assert body["use_count"] == 0 and body["max_uses"] == 5

    async with admin_session_factory() as session:
        row = await session.get_one(CampaignInvite, uuid.UUID(body["id"]))
        assert row.token_hash == hash_token(token)
        assert row.token_hash != token  # only the hash is stored

    listed = await client.get(base)
    assert listed.status_code == 200
    rows = listed.json()["items"]
    assert [r["id"] for r in rows] == [body["id"]]
    assert "token" not in rows[0]  # a list never carries a token
    assert token not in listed.text

    # The activity log records who made it - and never the token.
    (entry,) = await _entries(tenant_id, "campaign_invite.created")
    assert entry.actor_id == test_user_id
    assert token not in (entry.detail or "")
    assert "max_uses=5" in (entry.detail or "")

    await delete_tenant(tenant_id)


async def test_an_omitted_max_uses_means_unlimited(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)

    created = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites", json={"expires_at": _in(days=1)}
    )

    assert created.status_code == 201, created.text
    assert created.json()["max_uses"] is None
    (entry,) = await _entries(tenant_id, "campaign_invite.created")
    assert "max_uses=unlimited" in (entry.detail or "")

    await delete_tenant(tenant_id)


async def test_expiry_is_required_and_bounded(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    assert (await client.post(base, json={})).status_code == 422  # a link always ends
    assert (await client.post(base, json={"expires_at": _in(days=-1)})).status_code == 422
    assert (await client.post(base, json={"expires_at": _in(days=31)})).status_code == 422
    assert (await client.post(base, json={"expires_at": _in(days=29)})).status_code == 201
    naive = (datetime.now() + timedelta(days=1)).replace(tzinfo=None).isoformat()  # noqa: DTZ005
    assert (await client.post(base, json={"expires_at": naive})).status_code == 422
    assert (
        await client.post(base, json={"expires_at": _in(days=1), "max_uses": 0})
    ).status_code == 422

    await delete_tenant(tenant_id)


async def test_revoking_is_instant_and_idempotent_and_logged_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"
    invite = (await client.post(base, json={"expires_at": _in(days=1)})).json()

    assert (await client.delete(f"{base}/{invite['id']}")).status_code == 204
    assert (await client.delete(f"{base}/{invite['id']}")).status_code == 204  # no-op

    listed = (await client.get(base)).json()["items"][0]
    assert listed["is_active"] is False and listed["revoked_at"] is not None
    assert len(await _entries(tenant_id, "campaign_invite.revoked")) == 1
    assert (await client.delete(f"{base}/{uuid.uuid4()}")).status_code == 404

    await delete_tenant(tenant_id)


async def test_only_a_campaign_manager_can_manage_invites(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A player of the campaign can see it but not manage it: 403. Someone
    with no standing in it at all gets a 404 that hides it exists (ADR 0032).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        as_player = await make_campaign(session, tenant_id=tenant_id, name="Player Here")
        unrelated = await make_campaign(session, tenant_id=tenant_id, name="No Standing")
        session.add(Player(user_id=test_user_id, campaign_id=as_player.id, tenant_id=tenant_id))
        await session.commit()
        player_campaign_id, unrelated_campaign_id = as_player.id, unrelated.id

    def url(campaign_id: uuid.UUID) -> str:
        return f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    body = {"expires_at": _in(days=1)}
    assert (await client.post(url(player_campaign_id), json=body)).status_code == 403
    assert (await client.get(url(player_campaign_id))).status_code == 403
    assert (await client.post(url(unrelated_campaign_id), json=body)).status_code == 404
    assert (await client.get(url(unrelated_campaign_id))).status_code == 404

    await delete_tenant(tenant_id)


# --- RLS: run as the app's own restricted role, not the superuser ------------


async def _seed(tenant_id: uuid.UUID, campaign_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    token = generate_token()
    async with admin_session_factory() as session:
        invite = CampaignInvite(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            token_hash=hash_token(token),
            expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        )
        session.add(invite)
        await session.commit()
        return token, invite.id


async def test_rls_a_token_reads_exactly_its_own_invite_and_writes_nothing(
    test_user_id: uuid.UUID,
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign_a = await make_campaign(session, tenant_id=tenant_a)
        campaign_b = await make_campaign(session, tenant_id=tenant_b)
        await session.commit()
        campaign_a_id, campaign_b_id = campaign_a.id, campaign_b.id
    token_a, invite_a = await _seed(tenant_a, campaign_a_id)
    _, invite_b = await _seed(tenant_b, campaign_b_id)

    async def visible(session_setup: str | None = None, **settings: str) -> set[uuid.UUID]:
        async with async_session_factory() as session:
            for name, value in settings.items():
                await session.execute(
                    text("SELECT set_config(:n, :v, true)"),
                    {"n": name.replace("__", "."), "v": value},
                )
            rows = (await session.execute(select(CampaignInvite.id))).scalars().all()
            return set(rows)

    # No context at all: nothing visible (and no error - an unset setting is NULL).
    assert await visible() == set()
    # The token for A reveals A's invite - and only A's.
    assert await visible(app__invite_token_hash=hash_token(token_a)) == {invite_a}
    # A tenant context sees that tenant's own invites and no one else's.
    assert await visible(app__tenant_id=str(tenant_b)) == {invite_b}
    # A blank setting (what a lapsed transaction-local setting reads as) is
    # NULL too, not an "invalid uuid" error.
    assert await visible(app__tenant_id="", app__invite_token_hash="") == set()

    # Holding a token confers no write: the by-token policy is SELECT-only.
    async with async_session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.invite_token_hash', :h, true)"),
            {"h": hash_token(token_a)},
        )
        result = await session.execute(update(CampaignInvite).values(use_count=99))
        assert result.rowcount == 0  # type: ignore[attr-defined]
        await session.rollback()
    async with admin_session_factory() as session:
        assert (await session.get_one(CampaignInvite, invite_a)).use_count == 0

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)
