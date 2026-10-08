"""A library with two campaigns and what each holds, for ADR 0200: who reads the
GM-only text of an entry no campaign owns, and what stays out of reach.

Campaign X (what the GMs under test run) and campaign Y (another table of the
same library). Every entry below carries one GM-only note titled with its name.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from _admin_db import admin_session_factory
from conftest import make_campaign, make_tenant
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character, _instance

from lorenzo_api.models import (
    CampaignGm,
    Containment,
    Entity,
    GroupMember,
    Information,
    Item,
    Tenant,
)

# What campaign Y's characters hold, own, carry or stand in: never a GM of X's.
HELD_BY_Y = (
    "Yara",
    "Yara's Blade",
    "Backpack",
    "Gem",
    "Room",
    "Chair",
    "The Party",
    "Banner",
    "Loot",
)
# What campaign X's characters hold: a GM of X's own.
HELD_BY_X = ("Xan", "Staff")
# What no campaign owns: authored by a co-GM of X's GMs (Lantern), by a GM of Y (Crate), and
# by a co-GM of X's GMs again (Stash, in which lies Yara's Loot, so that a walk from Stash
# arrives at what a campaign holds).
UNOWNED = ("Lantern", "Crate", "Stash")
# The entry each campaign carries for itself (ADR 0030): no GM gains it.
CAMPAIGN_ENTRIES = ("Campaign X", "Campaign Y")

USER_ROLES = ("owner", "gm_x", "gm_x2", "gm_y", "player_x", "player_y")


@dataclass
class LibraryScene:
    tenant_id: uuid.UUID
    ids: dict[str, uuid.UUID] = field(default_factory=dict)


async def _note(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID, title: str
) -> None:
    session.add(
        Information(
            tenant_id=tenant_id,
            entity_id=entity_id,
            title=title,
            type="note",
            is_public=False,
        )
    )


async def build_library(users: dict[str, uuid.UUID]) -> LibraryScene:
    """`users` maps USER_ROLES to real user ids: `owner` owns the library;
    gm_x and gm_x2 GM campaign X (so are each other's co-GM); gm_y GMs Y;
    player_x and player_y have a seat and a character in X and in Y.
    """
    tenant_id = await make_tenant(users["owner"])
    scene = LibraryScene(tenant_id)
    ids = scene.ids
    async with admin_session_factory() as session:
        camp_x = await make_campaign(session, tenant_id=tenant_id, name="X")
        camp_y = await make_campaign(session, tenant_id=tenant_id, name="Y")
        for who, campaign in (("gm_x", camp_x), ("gm_x2", camp_x), ("gm_y", camp_y)):
            session.add(
                CampaignGm(user_id=users[who], campaign_id=campaign.id, tenant_id=tenant_id)
            )
        ids["X"], ids["Y"] = camp_x.id, camp_y.id
        ids["Campaign X"], ids["Campaign Y"] = camp_x.entity_id, camp_y.entity_id

        t = tenant_id
        ids["Xan"] = await _character(session, t, camp_x.id, users["player_x"], "Xan")
        ids["Yara"] = await _character(session, t, camp_y.id, users["player_y"], "Yara")
        ids["Staff"] = await _instance(session, t, "Staff", owner=ids["Xan"], container=ids["Xan"])

        # Y: a blade it holds, a backpack with a gem that nobody owns inside it, a room it
        # stands in with a chair, and a party that owns a banner.
        ids["Yara's Blade"] = await _instance(
            session, t, "Yara's Blade", owner=ids["Yara"], container=ids["Yara"]
        )
        ids["Backpack"] = await _instance(
            session, t, "Backpack", owner=ids["Yara"], container=ids["Yara"]
        )
        ids["Gem"] = await _instance(session, t, "Gem", container=ids["Backpack"])
        room = Entity(tenant_id=t, name="Room")
        party = Entity(tenant_id=t, name="The Party")
        session.add_all([room, party])
        await session.flush()
        chair = await _instance(session, t, "Chair", container=room.id)
        session.add(Containment(child_entity_id=ids["Yara"], parent_entity_id=room.id, tenant_id=t))
        session.add(
            GroupMember(group_entity_id=party.id, character_entity_id=ids["Yara"], tenant_id=t)
        )
        ids["Room"], ids["The Party"], ids["Chair"] = room.id, party.id, chair
        ids["Banner"] = await _instance(session, t, "Banner", owner=party.id)

        # No campaign owns these: a catalog item, and an inventory item in no container.
        lantern = Entity(tenant_id=t, name="Lantern", created_by=users["gm_x2"])
        session.add(lantern)
        await session.flush()
        session.add(Item(entity_id=lantern.id, tenant_id=t))
        ids["Lantern"] = lantern.id
        ids["Crate"] = await _instance(session, t, "Crate")
        await session.execute(
            update(Entity).where(Entity.id == ids["Crate"]).values(created_by=users["gm_y"])
        )

        stash = Entity(tenant_id=t, name="Stash", created_by=users["gm_x2"])
        session.add(stash)
        await session.flush()
        ids["Stash"] = stash.id
        ids["Loot"] = await _instance(session, t, "Loot", owner=ids["Yara"], container=stash.id)

        for name in (*HELD_BY_X, *HELD_BY_Y, *UNOWNED, *CAMPAIGN_ENTRIES):
            await _note(session, t, ids[name], name)
        await session.commit()
    return scene


async def set_sharing(tenant_id: uuid.UUID, shared: bool) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(npcs_shared_with_gms=shared)
        )
        await session.commit()
