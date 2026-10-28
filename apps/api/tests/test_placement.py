"""Placement and whereabouts (ADR 0333, ADR 0334)."""

import pathlib
import uuid
from typing import Any

from _admin_db import admin_session_factory
from _repository_actors import cleanup
from conftest import make_character
from sqlalchemy import select, text
from test_locations import place
from test_story_sessions import world

from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import CharacterPlayer, Containment, EntityLocation


async def entry(actor: Any, t: Any, name: str, kinds: tuple[str, ...] = ("item",)) -> str:
    response = await actor.post(f"/tenants/{t}/entities", json={"name": name, "kinds": list(kinds)})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def put_at(actor: Any, t: Any, who: str, where: str) -> Any:
    return await actor.put(f"/tenants/{t}/entities/{who}/at", json={"location_entity_id": where})


async def say(actor: Any, t: Any, who: str, character: Any) -> dict[str, Any]:
    response = await actor.get(
        f"/tenants/{t}/entities/{who}/whereabouts", params={"relative_to": str(character)}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def stored(who: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        return await session.scalar(
            select(EntityLocation.location_entity_id).where(EntityLocation.entity_id == who)
        )


async def character_of(t: Any, player: Any, name: str = "Bram") -> uuid.UUID:
    async with admin_session_factory() as session:
        made = await make_character(session, tenant_id=t, name=name, owner_player_id=player)
        session.add(
            CharacterPlayer(character_entity_id=made.entity_id, player_id=player, tenant_id=t)
        )
        await session.commit()
        return made.entity_id


async def contain(t: Any, child: str, parent: str) -> None:
    async with admin_session_factory() as session:
        session.add(Containment(child_entity_id=child, parent_entity_id=parent, tenant_id=t))
        await session.commit()


async def take_out(child: str) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Containment, child))
        await session.commit()


async def test_the_states_of_whereabouts(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        tavern = await place(gm, t, "Tavern", is_public=True)
        cellar = await place(gm, t, "Cellar", is_public=True, parent_id=tavern["id"])
        market = await place(gm, t, "Market", is_public=True)
        bram = await character_of(t, pid)
        sword = await entry(gm, t, "Sword")
        loose = await entry(gm, t, "Rope")
        # Nothing is placed: nothing is known.
        assert await say(player, t, sword, bram) == {"state": "unknown"}
        # The same place as the character: here, with no name.
        assert (await put_at(gm, t, str(bram), tavern["id"])).status_code == 200
        assert (await put_at(gm, t, sword, tavern["id"])).status_code == 200
        assert await say(player, t, sword, bram) == {"state": "stashed"}
        # One branch (the Cellar is in the Tavern): left there, named.
        assert (await put_at(gm, t, loose, cellar["id"])).status_code == 200
        said = await say(player, t, loose, bram)
        assert said["state"] == "stashed" and said["place"]["name"] == "Cellar"
        # Another branch: elsewhere.
        assert (await put_at(gm, t, sword, market["id"])).status_code == 200
        said = await say(player, t, sword, bram)
        assert said["state"] == "elsewhere" and said["place"]["name"] == "Market"
        # Carried: with you, and no name, by a container or by the character.
        pack = await entry(gm, t, "Pack")
        await contain(t, pack, str(bram))
        await contain(t, loose, pack)
        assert await say(player, t, loose, bram) == {"state": "with_you"}
        assert await say(player, t, str(bram), bram) == {"state": "with_you"}
        # Whose character may be asked about: not another player's, not an item.
        refused = await player.get(
            f"/tenants/{t}/entities/{sword}/whereabouts", params={"relative_to": sword}
        )
        assert refused.status_code == 404
        # The GM may ask about any character.
        assert (await say(gm, t, sword, bram))["state"] == "elsewhere"
    finally:
        await w.clean_up()


async def test_containment_wins_and_the_row_follows_the_container(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        tavern = await place(gm, t, "Tavern", is_public=True)
        market = await place(gm, t, "Market", is_public=True)
        sword = await entry(gm, t, "Sword")
        chest = await entry(gm, t, "Chest")
        assert (await put_at(gm, t, sword, tavern["id"])).status_code == 200
        assert (await put_at(gm, t, chest, market["id"])).status_code == 200
        assert await stored(sword) == uuid.UUID(tavern["id"])
        # Put into a container: no place of its own any more.
        await contain(t, sword, chest)
        assert await stored(sword) is None
        # A place written for something in a container is accepted and changes nothing.
        ignored = await put_at(gm, t, sword, tavern["id"])
        assert ignored.status_code == 200
        assert ignored.json() == {"entity_id": sword, "location_entity_id": tavern["id"]}
        assert await stored(sword) is None
        # Taken out: where the container is.
        await take_out(sword)
        assert await stored(sword) == uuid.UUID(market["id"])
        # Back in, and out again, with the chest moved: the earlier place is not restored.
        await contain(t, sword, chest)
        assert await stored(sword) is None
        assert (await put_at(gm, t, chest, tavern["id"])).status_code == 200
        await take_out(sword)
        assert await stored(sword) == uuid.UUID(tavern["id"])
        # A container with no place leaves what comes out of it unplaced.
        empty = await entry(gm, t, "Empty bag")
        thing = await entry(gm, t, "Thing")
        await contain(t, thing, empty)
        await take_out(thing)
        assert await stored(thing) is None
        # A Location that is a container is the place of what comes out of it.
        cell = await place(gm, t, "Cell", is_public=True)
        prisoner = await entry(gm, t, "Key")
        await contain(t, prisoner, cell["id"])
        await take_out(prisoner)
        assert await stored(prisoner) == uuid.UUID(cell["id"])
    finally:
        await w.clean_up()


async def test_a_hidden_place_and_a_hidden_level_leave_no_trace(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        bram = await character_of(t, pid)
        # Realm > Hold (restricted) > Camp, against Realm > Camp: the same answer.
        realm = await place(gm, t, "Realm", is_public=True)
        hold = await place(gm, t, "Hold", parent_id=realm["id"])
        camp = await place(gm, t, "Camp", parent_id=hold["id"], is_public=True)
        realm2 = await place(gm, t, "Realm", is_public=True)
        camp2 = await place(gm, t, "Camp", parent_id=realm2["id"], is_public=True)
        shield = await entry(gm, t, "Shield")
        shield2 = await entry(gm, t, "Shield")
        assert (await put_at(gm, t, str(bram), realm["id"])).status_code == 200
        assert (await put_at(gm, t, shield, camp["id"])).status_code == 200
        assert (await put_at(gm, t, shield2, camp2["id"])).status_code == 200
        first = await say(player, t, shield, bram)
        # The second shield is compared from a character at the second Realm.
        bram2 = await character_of(t, pid, "Bram again")
        assert (await put_at(gm, t, str(bram2), realm2["id"])).status_code == 200
        second = await say(player, t, shield2, bram2)
        assert first["state"] == second["state"] == "stashed"
        assert first["place"]["name"] == second["place"]["name"] == "Camp"
        assert "Hold" not in str(first)
        # A hidden place is unknown, never its visible ancestor.
        axe = await entry(gm, t, "Axe")
        assert (await put_at(gm, t, axe, hold["id"])).status_code == 200
        unplaced = await entry(gm, t, "Bow")
        assert await say(player, t, axe, bram) == await say(player, t, unplaced, bram)
        assert await say(player, t, axe, bram) == {"state": "unknown"}
        # The GM sees where it is.
        assert (await say(gm, t, axe, bram))["place"]["name"] == "Hold"
        # A hidden entry and a missing one answer alike.
        secret = await place(gm, t, "Vault")
        missing = await player.get(
            f"/tenants/{t}/entities/{uuid.uuid4()}/whereabouts", params={"relative_to": str(bram)}
        )
        hidden = await player.get(
            f"/tenants/{t}/entities/{secret['id']}/whereabouts", params={"relative_to": str(bram)}
        )
        assert hidden.status_code == missing.status_code == 404
        shape = lambda r: {k: v for k, v in r.json().items() if k != "instance"}  # noqa: E731
        assert shape(hidden) == shape(missing)
    finally:
        await w.clean_up()


async def test_who_may_place_and_what_a_deletion_leaves(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        tavern = await place(gm, t, "Tavern", is_public=True)
        sword = await entry(gm, t, "Sword")
        assert (await put_at(player, t, sword, tavern["id"])).status_code == 403
        assert (await player.delete(f"/tenants/{t}/entities/{sword}/at")).status_code == 403
        assert (await put_at(gm, t, sword, str(uuid.uuid4()))).status_code == 404
        assert (await put_at(gm, t, str(uuid.uuid4()), tavern["id"])).status_code == 404
        # Not at itself.
        assert (await put_at(gm, t, tavern["id"], tavern["id"])).status_code == 422
        # A Location may be at another.
        dock = await place(gm, t, "Dock", is_public=True)
        assert (await put_at(gm, t, dock["id"], tavern["id"])).status_code == 200
        assert (await put_at(gm, t, sword, tavern["id"])).status_code == 200
        # Deleting the Location leaves the entries unplaced; deleting the entry removes its row.
        assert (await gm.delete(f"/tenants/{t}/entities/{tavern['id']}")).status_code in (200, 204)
        assert await stored(sword) is None and await stored(dock["id"]) is None
        elsewhere = await place(gm, t, "Elsewhere", is_public=True)
        assert (await put_at(gm, t, sword, elsewhere["id"])).status_code == 200
        assert (await gm.delete(f"/tenants/{t}/entities/{sword}/at")).status_code == 204
        assert await stored(sword) is None
    finally:
        await w.clean_up()


async def test_placement_never_feeds_gm_reach(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        tavern = await place(gm, t, "Tavern", is_public=True)
        thing = await entry(gm, t, "Thing")
        async with admin_session_factory() as session:
            before = (
                await resolve_information_visibility(session, user_id=gm.user_id, tenant_id=t)
            ).gm_reachable_entity_ids
        assert (await put_at(gm, t, thing, tavern["id"])).status_code == 200
        async with admin_session_factory() as session:
            after = (
                await resolve_information_visibility(session, user_id=gm.user_id, tenant_id=t)
            ).gm_reachable_entity_ids
        assert before == after
    finally:
        await w.clean_up()


def test_no_reach_code_reads_a_placement():
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
        text_of = (source / module).read_text()
        for word in ("EntityLocation", "entity_location", "LocationPart", "location_part"):
            assert word not in text_of, (module, word)


async def test_no_position_table_has_a_time_column():
    """RFC 0048 G2: no date, time or period on a place, a part-of row or a Location."""
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT table_name, column_name, data_type FROM information_schema.columns "
                    "WHERE table_name IN ('location', 'location_part', 'entity_location')"
                )
            )
        ).all()
    assert rows
    for table, column, kind in rows:
        assert "time" not in kind and kind not in ("date", "interval"), (table, column, kind)
        assert not any(word in column for word in ("date", "time", "period", "_at")), (
            table,
            column,
        )


async def test_the_inventory_routes_move_the_place_with_the_container(client, test_user_id):
    from conftest import delete_tenant, make_tenant

    from lorenzo_api.models import Entity, ItemInstance

    tenant = await make_tenant(test_user_id)
    try:
        async with admin_session_factory() as session:
            sword = Entity(tenant_id=tenant, name="Sword")
            chest = Entity(tenant_id=tenant, name="Chest")
            session.add_all([sword, chest])
            await session.flush()
            session.add_all(
                [
                    ItemInstance(entity_id=sword.id, tenant_id=tenant),
                    ItemInstance(entity_id=chest.id, tenant_id=tenant),
                ]
            )
            await session.commit()
            sword_id, chest_id = str(sword.id), str(chest.id)
        tavern = await place(client, tenant, "Tavern", is_public=True)
        market = await place(client, tenant, "Market", is_public=True)
        assert (await put_at(client, tenant, sword_id, tavern["id"])).status_code == 200
        assert (await put_at(client, tenant, chest_id, market["id"])).status_code == 200
        into = await client.put(
            f"/tenants/{tenant}/item-instances/{sword_id}/container",
            json={"container_entity_id": chest_id},
        )
        assert into.status_code == 200, into.text
        assert await stored(sword_id) is None
        # The containment response says nothing of places.
        assert "location" not in str(into.json()).lower()
        out = await client.delete(f"/tenants/{tenant}/item-instances/{sword_id}/container")
        assert out.status_code == 200, out.text
        assert await stored(sword_id) == uuid.UUID(market["id"])
    finally:
        await delete_tenant(tenant)


async def test_a_place_travels_through_copy_and_update(raw_client, fake_jwks_server):
    from test_kind_matrix import _scene

    from lorenzo_api.models import Entity

    scene = await _scene(raw_client, fake_jwks_server, ("item",), bridge=False)
    author, repository, alpha = scene.author, scene.repository, scene.ids["Alpha"]

    async def library_place() -> str | None:
        async with admin_session_factory() as session:
            mine = await session.scalar(
                select(Entity.id).where(Entity.tenant_id == scene.table, Entity.name == "Alpha")
            )
            at = await session.scalar(
                select(EntityLocation.location_entity_id).where(EntityLocation.entity_id == mine)
            )
            return (
                None
                if at is None
                else await session.scalar(select(Entity.name).where(Entity.id == at))
            )

    try:
        assert await library_place() is None
        hall = await place(author, repository, "Hall", is_public=True)
        assert (await put_at(author, repository, str(alpha), hall["id"])).status_code == 200
        await scene.publish()
        found = await scene.updates()
        assert [a["name"] for a in found["added"]] == ["Hall"]
        fields = {f["field"] for r in found["changed"] if r["name"] == "Alpha" for f in r["fields"]}
        assert fields == {"place"}
        await scene.apply(
            [
                {"kind": "entity", "source_id": hall["id"], "action": "add"},
                {"kind": "entity", "source_id": str(alpha), "action": "apply"},
            ]
        )
        assert await library_place() == "Hall"
        # Moved to another Location upstream.
        garden = await place(author, repository, "Garden", is_public=True)
        assert (await put_at(author, repository, str(alpha), garden["id"])).status_code == 200
        await scene.publish()
        await scene.apply(
            [
                {"kind": "entity", "source_id": garden["id"], "action": "add"},
                {"kind": "entity", "source_id": str(alpha), "action": "apply"},
            ]
        )
        assert await library_place() == "Garden"
        # And placed nowhere.
        assert (
            await author.delete(f"/tenants/{repository}/entities/{alpha}/at")
        ).status_code == 204
        await scene.publish()
        await scene.apply([{"kind": "entity", "source_id": str(alpha), "action": "apply"}])
        assert await library_place() is None
    finally:
        await cleanup(scene.tenants, [scene.author, scene.gm])
