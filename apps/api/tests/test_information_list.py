"""ADR 0109: player knowers, knower listing, and the paged per-entity
information list - including the parity test that keeps
visible_information_clause (SQL) and InformationVisibility.can_see
(Python) one definition.
"""

import uuid
from itertools import product

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.information_visibility import InformationVisibility, visible_information_clause
from lorenzo_api.models import (
    AuditLog,
    CharacterPlayer,
    Entity,
    Information,
    Knowledge,
    Membership,
    Player,
    User,
)

# --- parity: SQL clause vs can_see -------------------------------------------


async def test_visible_information_clause_matches_can_see() -> None:
    """A fixed matrix of rows (public, GM-only, told to a character, a
    group, a player) on two entities, against a fixed matrix of callers
    (admin, nobody, GM reaching one entity, each kind of knower, and
    combinations). For every caller, the rows SQL returns must be exactly
    the rows can_see accepts."""
    owner_id = await _user()
    tenant_id = await make_tenant(owner_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=owner_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        group = Entity(tenant_id=tenant_id, name="The Party")
        near = Entity(tenant_id=tenant_id, name="Near")
        far = Entity(tenant_id=tenant_id, name="Far")
        session.add_all([group, near, far])
        await session.flush()
        rows: dict[str, Information] = {}
        for entity, label in ((near, "near"), (far, "far")):
            for kind in ("public", "gm", "character", "group", "player"):
                info = Information(
                    tenant_id=tenant_id,
                    entity_id=entity.id,
                    title=f"{label}-{kind}",
                    type="note",
                    is_public=kind == "public",
                )
                session.add(info)
                await session.flush()
                knower = {
                    "character": {"knower_entity_id": character.entity_id},
                    "group": {"knower_entity_id": group.id},
                    "player": {"knower_player_id": player.id},
                }.get(kind)
                if knower:
                    session.add(Knowledge(tenant_id=tenant_id, information_id=info.id, **knower))
                rows[info.title] = info
        await session.commit()
        ids = (player.id, character.entity_id, group.id, near.id)

    player_id, character_id, group_id, near_id = ids
    callers = {
        "admin": InformationVisibility(True, True, frozenset(), frozenset(), frozenset()),
        "nobody": InformationVisibility(False, False, frozenset(), frozenset(), frozenset()),
    }
    for p, c, g, gm in product((False, True), repeat=4):
        callers[f"p{p:d}c{c:d}g{g:d}gm{gm:d}"] = InformationVisibility(
            is_orga=False,
            is_admin=False,
            player_ids=frozenset({player_id} if p else ()),
            knower_entity_ids=frozenset(
                ({character_id} if c else set()) | ({group_id} if g else set())
            ),
            gm_reachable_entity_ids=frozenset({near_id} if gm else ()),
        )

    try:
        async with admin_session_factory() as session:
            loaded = (
                (
                    await session.execute(
                        select(Information)
                        .where(Information.tenant_id == tenant_id)
                        .options(selectinload(Information.knowledge_links))
                    )
                )
                .scalars()
                .all()
            )
            for label, vis in callers.items():
                python_side = {info.title for info in loaded if vis.can_see(info)}
                sql_side = set(
                    (
                        await session.execute(
                            select(Information.title).where(
                                Information.tenant_id == tenant_id,
                                visible_information_clause(vis),
                            )
                        )
                    ).scalars()
                )
                assert sql_side == python_side, label
    finally:
        await delete_tenant(tenant_id)
        await _delete_user(owner_id)


async def _user() -> uuid.UUID:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"test|{uuid.uuid4()}", display_name="Robin")
        session.add(user)
        await session.commit()
        return user.id


async def _delete_user(user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


# --- API ---------------------------------------------------------------------


async def _told_player_setup(test_user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A tenant the test user owns, with a Player seat for them in one
    campaign, and a sword. Returns (tenant_id, player_id, sword_id)."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add_all([player, sword])
        await session.commit()
        return tenant_id, player.id, sword.id


async def _demote_to_plain_player(tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Drops the tenant Membership - no administrative bypass any more -
    keeping the Player seat, so tenant reads still admit them."""
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Membership, (tenant_id, user_id)))
        await session.commit()


async def _create(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, **body: object
) -> dict:
    payload = {"title": "A note", "type": "note", "is_public": False, "content": "Text."}
    payload.update(body)
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_telling_a_player_makes_the_row_visible_to_them(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, player_id, sword_id = await _told_player_setup(test_user_id)
    told = await _create(client, tenant_id, sword_id, title="Told")
    untold = await _create(client, tenant_id, sword_id, title="Untold")
    url = f"/tenants/{tenant_id}/information/{told['id']}/player-knowers/{player_id}"

    first = await client.put(url)
    again = await client.put(url)
    await _demote_to_plain_player(tenant_id, test_user_id)
    seen = await client.get(f"/tenants/{tenant_id}/information/{told['id']}")
    unseen = await client.get(f"/tenants/{tenant_id}/information/{untold['id']}")

    assert first.status_code == 200, first.text
    assert again.status_code == 200
    assert seen.status_code == 200
    assert unseen.status_code == 404
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(Knowledge.id).where(Knowledge.knower_player_id == player_id)
            )
        ).all()
        entries = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail).where(
                    AuditLog.tenant_id == tenant_id, AuditLog.action.like("information.knower%")
                )
            )
        ).all()
    assert len(rows) == 1  # idempotent
    assert [tuple(e) for e in entries] == [("information.knower_added", f"player={player_id}")]
    await delete_tenant(tenant_id)


async def test_untelling_a_player(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id, player_id, sword_id = await _told_player_setup(test_user_id)
    told = await _create(client, tenant_id, sword_id)
    url = f"/tenants/{tenant_id}/information/{told['id']}/player-knowers/{player_id}"
    await client.put(url)

    removed = await client.delete(url)
    removed_again = await client.delete(url)
    await _demote_to_plain_player(tenant_id, test_user_id)

    assert removed.status_code == 200
    assert removed_again.status_code == 200
    assert (await client.get(f"/tenants/{tenant_id}/information/{told['id']}")).status_code == 404
    await delete_tenant(tenant_id)


async def test_telling_an_unknown_player_is_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, _, sword_id = await _told_player_setup(test_user_id)
    told = await _create(client, tenant_id, sword_id)

    response = await client.put(
        f"/tenants/{tenant_id}/information/{told['id']}/player-knowers/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_a_player_cannot_tell_themselves_a_gm_secret(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0101's edit gate covers player knowers too: without sight of the
    row (or having written it), standing isn't enough."""
    tenant_id, player_id, _ = await _told_player_setup(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player_id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player_id, tenant_id=tenant_id
            )
        )
        secret = Information(
            tenant_id=tenant_id, entity_id=character.entity_id, title="Curse", type="gm-note"
        )
        session.add(secret)
        await session.commit()
        secret_id = secret.id
    await _demote_to_plain_player(tenant_id, test_user_id)

    response = await client.put(
        f"/tenants/{tenant_id}/information/{secret_id}/player-knowers/{player_id}"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_knower_listing_covers_both_kinds_and_is_edit_gated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, player_id, sword_id = await _told_player_setup(test_user_id)
    async with admin_session_factory() as session:
        user = await session.get_one(User, test_user_id)
        user.display_name = "Robin"
        character = await make_character(session, tenant_id=tenant_id, name="Alice")
        await session.commit()
        character_id = character.entity_id
    told = await _create(client, tenant_id, sword_id)
    base = f"/tenants/{tenant_id}/information/{told['id']}"
    await client.put(f"{base}/knowers/{character_id}")
    await client.put(f"{base}/player-knowers/{player_id}")

    listed = await client.get(f"{base}/knowers")
    await _demote_to_plain_player(tenant_id, test_user_id)
    # Now a plain player who can still *see* the row (they were told) -
    # but who else knows is not theirs to learn.
    as_knower = await client.get(f"{base}/knowers")
    still_visible = await client.get(base)

    assert listed.status_code == 200, listed.text
    assert [(k["kind"], k["name"]) for k in listed.json()] == [
        ("entity", "Alice"),
        ("player", "Robin"),
    ]
    assert listed.json()[0]["knower_entity_id"] == str(character_id)
    assert listed.json()[1]["player_id"] == str(player_id)
    assert still_visible.status_code == 200
    assert as_knower.status_code == 403  # sight via authorship, but no standing
    async with admin_session_factory() as session:
        user = await session.get_one(User, test_user_id)
        user.display_name = None
        await session.commit()
    await delete_tenant(tenant_id)


async def test_entity_information_list_pages_in_order_and_filters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, _, sword_id = await _told_player_setup(test_user_id)
    for title, type_ in (
        ("Desc", "description"),
        ("Note 1", "note"),
        ("Note 2", "note"),
        ("Handout", "handout"),
    ):
        await _create(client, tenant_id, sword_id, title=title, type=type_, is_public=True)
    url = f"/tenants/{tenant_id}/entities/{sword_id}/information"

    first = await client.get(url, params={"size": 2})
    second = await client.get(url, params={"size": 2, "page": 2})
    notes = await client.get(url, params=[("type", "note"), ("type", "handout")])
    technical = await client.get(url, params={"category": "technical"})
    authored = await client.get(url, params={"category": "gm_authored"})
    unknown = await client.get(f"/tenants/{tenant_id}/entities/{uuid.uuid4()}/information")

    assert first.status_code == 200, first.text
    assert [i["title"] for i in first.json()["items"]] == ["Desc", "Note 1"]
    assert first.json()["total"] == 4
    assert [i["title"] for i in second.json()["items"]] == ["Note 2", "Handout"]
    assert [i["title"] for i in notes.json()["items"]] == ["Note 1", "Note 2", "Handout"]
    assert [i["title"] for i in technical.json()["items"]] == ["Desc"]
    assert [i["title"] for i in authored.json()["items"]] == ["Note 1", "Note 2", "Handout"]
    assert unknown.status_code == 404
    await delete_tenant(tenant_id)


async def test_entity_information_list_counts_only_visible_rows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Visibility applies before pagination: a plain player's page is
    never short and its total never counts hidden rows (RFC 0029 BL10)."""
    tenant_id, player_id, sword_id = await _told_player_setup(test_user_id)
    await _create(client, tenant_id, sword_id, title="Public", is_public=True)
    for n in range(3):
        await _create(client, tenant_id, sword_id, title=f"Secret {n}")
    told = await _create(client, tenant_id, sword_id, title="Told")
    await client.put(f"/tenants/{tenant_id}/information/{told['id']}/player-knowers/{player_id}")
    url = f"/tenants/{tenant_id}/entities/{sword_id}/information"

    as_owner = await client.get(url)
    await _demote_to_plain_player(tenant_id, test_user_id)
    as_player = await client.get(url, params={"size": 2})

    assert as_owner.json()["total"] == 5
    assert as_player.json()["total"] == 2
    assert [i["title"] for i in as_player.json()["items"]] == ["Public", "Told"]
    await delete_tenant(tenant_id)
