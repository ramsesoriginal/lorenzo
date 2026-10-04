"""GET /tenants/{id}/beings for someone who is not a tenant administrator - see ADR 0173.

A GM with no membership lists the beings in their reach (ADR 0035, 0046, 0152); a tenant
administrator lists every being, as before; a player, or anyone else, is told there is no such
tenant, as before.
"""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_character
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character

from lorenzo_api.models import (
    CampaignGm,
    Containment,
    Entity,
    Membership,
    MembershipRole,
    Tenant,
    User,
)


@dataclass
class _Table:
    tenant_id: uuid.UUID
    names: dict[uuid.UUID, str]
    other_users: list[uuid.UUID]

    def listed(self, body: dict) -> set[str]:
        return {self.names[uuid.UUID(item["entity_id"])] for item in body["items"]}


async def _author(session: AsyncSession, entity_id: uuid.UUID, author: uuid.UUID | None) -> None:
    await session.execute(update(Entity).where(Entity.id == entity_id).values(created_by=author))


async def _table(me: uuid.UUID, *, i_am: str) -> _Table:
    """A tenant with two campaigns, A and B, and what is around them.

    `me` is whoever the test client acts as: a GM of campaign A with no membership (`i_am="gm"`),
    a tenant administrator who GMs A too (`"orga"`), a player in A (`"player"`), or nobody at all
    (`"stranger"`, who has no row in this tenant).

    The beings: Pia, a player character in A; Brisk, one in B; Lurker, an NPC standing in the room
    Pia is in; Wanderer, a bare being in no campaign that nobody authored; Mine, a bare being in no
    campaign that `me` authored; Theirs, one a stranger to A authored (a GM of B, who is no co-GM
    of mine); and Crowd, a being containing nothing and in no campaign, authored by a co-GM of mine.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        others = {
            label: User(authgear_subject_id=f"authgear|gm-beings-{label}-{uuid.uuid4()}")
            for label in ("player_a", "player_b", "gm_b", "co_gm")
        }
        session.add_all(others.values())
        await session.flush()
        t = tenant.id
        camp_a = await make_campaign(session, tenant_id=t, name="A")
        camp_b = await make_campaign(session, tenant_id=t, name="B")
        session.add(CampaignGm(user_id=others["gm_b"].id, campaign_id=camp_b.id, tenant_id=t))
        session.add(CampaignGm(user_id=others["co_gm"].id, campaign_id=camp_a.id, tenant_id=t))
        if i_am in ("gm", "orga"):
            session.add(CampaignGm(user_id=me, campaign_id=camp_a.id, tenant_id=t))
        if i_am == "orga":
            session.add(Membership(tenant_id=t, user_id=me, role=MembershipRole.ORGA))

        pia = await _character(session, t, camp_a.id, others["player_a"].id, "Pia")
        brisk = await _character(session, t, camp_b.id, others["player_b"].id, "Brisk")
        if i_am == "player":
            # A second seat in A for `me`, with a character of their own.
            mine_pc = await _character(session, t, camp_a.id, me, "Mine PC")
        lurker = (await make_being(session, tenant_id=t, name="Lurker")).entity_id
        wanderer = (await make_being(session, tenant_id=t, name="Wanderer")).entity_id
        mine = (await make_being(session, tenant_id=t, name="Mine")).entity_id
        theirs = (await make_being(session, tenant_id=t, name="Theirs")).entity_id
        crowd = (await make_character(session, tenant_id=t, name="Crowd")).entity_id
        await _author(session, mine, me)
        await _author(session, theirs, others["gm_b"].id)
        await _author(session, crowd, others["co_gm"].id)

        room = Entity(tenant_id=t, name="Room")
        session.add(room)
        await session.flush()
        for child in (pia, lurker):
            session.add(Containment(child_entity_id=child, parent_entity_id=room.id, tenant_id=t))
        await session.commit()

        names = {
            pia: "Pia",
            brisk: "Brisk",
            lurker: "Lurker",
            wanderer: "Wanderer",
            mine: "Mine",
            theirs: "Theirs",
            crowd: "Crowd",
        }
        if i_am == "player":
            names[mine_pc] = "Mine PC"
        return _Table(t, names, [u.id for u in others.values()])


async def _share(tenant_id: uuid.UUID, shared: bool) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(npcs_shared_with_gms=shared)
        )
        await session.commit()


async def _tear_down(table: _Table) -> None:
    await delete_tenant(table.tenant_id)
    async with admin_session_factory() as session:
        for user_id in table.other_users:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


EVERYONE = {"Pia", "Brisk", "Lurker", "Wanderer", "Mine", "Theirs", "Crowd"}


async def test_a_gm_with_no_membership_lists_what_is_in_their_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """With the setting on (the default): their campaign's character, the NPC in its scene, and
    every being in no campaign: but not another table's player character."""
    table = await _table(test_user_id, i_am="gm")

    response = await client.get(f"/tenants/{table.tenant_id}/beings")

    assert response.status_code == 200, response.text
    assert table.listed(response.json()) == EVERYONE - {"Brisk"}
    assert response.json()["total"] == len(EVERYONE) - 1

    await _tear_down(table)


async def test_with_the_setting_off_a_gm_lists_what_they_and_their_co_gms_authored(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="gm")
    await _share(table.tenant_id, False)

    response = await client.get(f"/tenants/{table.tenant_id}/beings")

    assert response.status_code == 200, response.text
    # Pia and Lurker by campaign and scene; Mine, and Crowd by a co-GM; not what nobody authored,
    # nor what a GM of another table did.
    assert table.listed(response.json()) == {"Pia", "Lurker", "Mine", "Crowd"}

    await _tear_down(table)


async def test_a_tenant_administrator_lists_every_being_as_before(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="orga")
    await _share(table.tenant_id, False)

    response = await client.get(f"/tenants/{table.tenant_id}/beings")

    assert response.status_code == 200, response.text
    assert table.listed(response.json()) == EVERYONE

    await _tear_down(table)


async def test_a_player_is_told_there_is_no_such_tenant_as_before(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="player")

    response = await client.get(f"/tenants/{table.tenant_id}/beings")

    assert response.status_code == 404
    assert response.json()["detail"] == f"No tenant with id {table.tenant_id}"

    await _tear_down(table)


async def test_someone_with_no_row_in_the_tenant_is_told_the_same(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="stranger")

    response = await client.get(f"/tenants/{table.tenant_id}/beings")

    assert response.status_code == 404
    assert response.json()["detail"] == f"No tenant with id {table.tenant_id}"

    await _tear_down(table)


async def test_a_gms_list_is_searched_and_paged_like_any_other(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    table = await _table(test_user_id, i_am="gm")
    path = f"/tenants/{table.tenant_id}/beings"

    searched = await client.get(path, params={"q": "pi"})
    first = await client.get(path, params={"page": 1, "size": 2})
    last = await client.get(path, params={"page": 3, "size": 2})

    assert table.listed(searched.json()) == {"Pia"}
    assert (first.json()["total"], len(first.json()["items"])) == (6, 2)
    assert len(last.json()["items"]) == 2
    # A search never reaches past a GM's reach.
    brisk = await client.get(path, params={"q": "brisk"})
    assert brisk.json()["items"] == []

    await _tear_down(table)


async def test_a_gm_of_another_tenant_sees_nothing_of_this_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await _table(test_user_id, i_am="gm")
    other = await _table(test_user_id, i_am="stranger")

    response = await client.get(f"/tenants/{other.tenant_id}/beings")

    assert response.status_code == 404

    await _tear_down(mine)
    await _tear_down(other)
