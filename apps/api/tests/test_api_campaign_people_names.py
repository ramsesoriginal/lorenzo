"""A campaign's players and GMs come with their names - see ADR 0176.

`GET .../campaigns/{id}/players` (and its detail and create responses) and `GET .../gms` carry
`nickname`, `display_name` and `user_color`, behind the campaign gate that already admits a player,
a GM, or a tenant administrator: so a GM holding only a campaign grant, with no tenant membership
to be named through, can name the people at their table. Never the email.
"""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient
from sqlalchemy import select
from test_api_held_by import _character

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant, User

PIA = {"display_name": "Pia Player", "user_color": "#112233"}
CLEO = {"display_name": "Cleo", "user_color": "#445566"}


@dataclass
class _Table:
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    pia_user: uuid.UUID
    pia_nickname: str
    pia_player: uuid.UUID
    cleo_user: uuid.UUID
    nameless_user: uuid.UUID
    other_users: list[uuid.UUID]

    @property
    def base(self) -> str:
        return f"/tenants/{self.tenant_id}/campaigns/{self.campaign_id}"


async def _table(me: uuid.UUID, *, i_am: str) -> _Table:
    """One campaign with a named player (Pia, who has a character), a named co-GM (Cleo) and a
    player who set no name at all; `me` is a GM of it with no membership (`"gm"`), a player in it
    (`"player"`), a tenant owner (`"owner"`), or has no row in this tenant (`"stranger"`).
    """
    suffix = uuid.uuid4().hex[:8]
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        pia_nickname = f"pia-the-bard-{suffix}"
        pia = User(
            authgear_subject_id=f"authgear|names-pia-{suffix}",
            email=f"pia-{suffix}@example.com",
            nickname=pia_nickname,
            **PIA,
        )
        cleo = User(
            authgear_subject_id=f"authgear|names-cleo-{suffix}",
            email=f"cleo-{suffix}@example.com",
            nickname=f"cleo-gm-{suffix}",
            **CLEO,
        )
        nameless = User(authgear_subject_id=f"authgear|names-nameless-{suffix}")
        session.add_all([pia, cleo, nameless])
        await session.flush()
        t = tenant.id
        campaign = await make_campaign(session, tenant_id=t, name="A")
        session.add(CampaignGm(user_id=cleo.id, campaign_id=campaign.id, tenant_id=t))
        session.add(Player(user_id=nameless.id, campaign_id=campaign.id, tenant_id=t))
        await _character(session, t, campaign.id, pia.id, "Pia's bard")
        pia_player = (
            await session.execute(
                select(Player.id).where(Player.user_id == pia.id, Player.campaign_id == campaign.id)
            )
        ).scalar_one()
        if i_am == "gm":
            session.add(CampaignGm(user_id=me, campaign_id=campaign.id, tenant_id=t))
        elif i_am == "player":
            session.add(Player(user_id=me, campaign_id=campaign.id, tenant_id=t))
        elif i_am == "owner":
            session.add(Membership(tenant_id=t, user_id=me, role=MembershipRole.OWNER))
        await session.commit()
        return _Table(
            tenant_id=t,
            campaign_id=campaign.id,
            pia_user=pia.id,
            pia_nickname=pia_nickname,
            pia_player=pia_player,
            cleo_user=cleo.id,
            nameless_user=nameless.id,
            other_users=[pia.id, cleo.id, nameless.id],
        )


async def _tear_down(table: _Table) -> None:
    await delete_tenant(table.tenant_id)
    async with admin_session_factory() as session:
        for user_id in table.other_users:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


def _names(item: dict) -> dict:
    return {key: item[key] for key in ("nickname", "display_name", "user_color")}


async def test_a_gm_with_no_membership_names_the_players_at_their_table(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="gm")
    try:
        response = await client.get(f"{table.base}/players")

        assert response.status_code == 200
        by_user = {item["user_id"]: item for item in response.json()["items"]}
        pia = by_user[str(table.pia_user)]
        assert _names(pia) == {"nickname": table.pia_nickname, **PIA}
        assert [c["name"] for c in pia["characters"]] == ["Pia's bard"]
        # A player who set nothing is listed, with nothing to show.
        assert _names(by_user[str(table.nameless_user)]) == {
            "nickname": None,
            "display_name": None,
            "user_color": None,
        }
        # Never the email, anywhere in the body.
        assert "@example.com" not in response.text
        assert "email" not in response.text
    finally:
        await _tear_down(table)


async def test_a_gm_with_no_membership_names_the_campaigns_gms(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="gm")
    try:
        response = await client.get(f"{table.base}/gms")

        assert response.status_code == 200
        by_user = {item["user_id"]: item for item in response.json()}
        assert set(by_user) == {str(table.cleo_user), str(test_user_id)}
        cleo = by_user[str(table.cleo_user)]
        assert (cleo["display_name"], cleo["user_color"]) == (
            CLEO["display_name"],
            CLEO["user_color"],
        )
        assert "@example.com" not in response.text
    finally:
        await _tear_down(table)


async def test_a_player_at_the_table_reads_the_same_names(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="player")
    try:
        players = await client.get(f"{table.base}/players")
        gms = await client.get(f"{table.base}/gms")

        assert players.status_code == gms.status_code == 200
        assert any(item["display_name"] == PIA["display_name"] for item in players.json()["items"])
        assert any(item["display_name"] == CLEO["display_name"] for item in gms.json())
    finally:
        await _tear_down(table)


async def test_the_player_detail_carries_the_names_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="gm")
    try:
        response = await client.get(f"{table.base}/players/{table.pia_player}")

        assert response.status_code == 200
        assert response.json()["display_name"] == PIA["display_name"]
        assert response.json()["user_color"] == PIA["user_color"]
    finally:
        await _tear_down(table)


async def test_adding_a_player_answers_with_their_names(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="owner")
    try:
        response = await client.post(
            f"{table.base}/players", json={"user_id": str(table.cleo_user)}
        )

        assert response.status_code == 201
        assert response.json()["display_name"] == CLEO["display_name"]
        assert response.json()["user_color"] == CLEO["user_color"]
    finally:
        await _tear_down(table)


async def test_someone_with_no_standing_in_the_campaign_is_still_told_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="stranger")
    try:
        players = await client.get(f"{table.base}/players")
        gms = await client.get(f"{table.base}/gms")

        assert players.status_code == gms.status_code == 404
        assert "Pia" not in players.text + gms.text
    finally:
        await _tear_down(table)
