"""ADR 0172: a parent a bridge adds to a copy travels with it, through the real
HTTP API. Repository content is authored straight into the database, as its
authors would through the ordinary routes; every copy and update goes through the
API.

The stack is RFC 0033's, small: an equipment repository (Weapon, Longsword,
Dagger), a rules repository (a system root, D&D 5e), and a bridge that copied both
and attached its prototypes to the equipment's items. Three attachments: Longsword
gets the bridge's own Longsword 5e, Weapon its own Economic Object, and Weapon
the rules repository's D&D 5e, which is another repository's copy.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import aliased

from lorenzo_api.db import engine
from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    Item,
    RepositoryCopyLinkAttachment,
)

LOOP = "it would make a prototype loop here"
NO_CHILD = "the item it attaches to isn't here"
NO_PARENT = "the prototype it attaches isn't here"


@dataclass
class _Stack:
    author: Actor
    equipment: uuid.UUID
    rules: uuid.UUID
    bridge: uuid.UUID
    # Origin ids: the equipment's and the rules' own rows, and the bridge's own.
    ids: dict[str, uuid.UUID]
    tenants: list[uuid.UUID]
    actors: list[Actor]


async def _share(author: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await author.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    # These stacks add attachments between publishes, which a release calls breaking (ADR 0208).
    published = await author.put(
        f"/tenants/{repository}/published", json={"acknowledge_breaking": True}
    )
    assert published.status_code == 200, published.text


async def _by_name(tenant: uuid.UUID) -> dict[str, uuid.UUID]:
    async with admin_session_factory() as session:
        return {
            name: entity_id
            for entity_id, name in await session.execute(
                select(Entity.id, Entity.name).where(Entity.tenant_id == tenant)
            )
        }


async def _parents(tenant: uuid.UUID) -> dict[str, list[str]]:
    """Each entity's parents, by name: names are unique in these tests."""
    child, parent = aliased(Entity), aliased(Entity)
    async with admin_session_factory() as session:
        rows = await session.execute(
            select(child.name, parent.name)
            .select_from(EntityPrototype)
            .join(child, child.id == EntityPrototype.entity_id)
            .join(parent, parent.id == EntityPrototype.prototype_id)
            .where(EntityPrototype.tenant_id == tenant)
        )
    found: dict[str, list[str]] = defaultdict(list)
    for name, parent_name in rows:
        found[name].append(parent_name)
    return {name: sorted(parents) for name, parents in found.items()}


async def _links(tenant: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(RepositoryCopyLinkAttachment)
                .where(RepositoryCopyLinkAttachment.tenant_id == tenant)
            )
        ).scalar_one()


async def _stack(raw_client: AsyncClient, jwks: FakeJwksServer) -> _Stack:
    author = await make_actor(raw_client, jwks, "author")
    equipment = await author.create_tenant("Common Equipment", kind="repository")
    rules = await author.create_tenant("D&D 5e", kind="repository")
    bridge = await author.create_tenant("D&D Equipment", kind="repository")
    async with admin_session_factory() as session:
        names = ("Weapon", "Longsword", "Dagger")
        items = {name: Entity(tenant_id=equipment, name=name) for name in names}
        root = Entity(tenant_id=rules, name="D&D 5e")
        session.add_all([*items.values(), root])
        await session.flush()
        session.add_all(
            [Item(entity_id=e.id, tenant_id=equipment) for e in items.values()]
            + [Item(entity_id=root.id, tenant_id=rules)]
            + [
                EntityPrototype(
                    entity_id=items[name].id, prototype_id=items["Weapon"].id, tenant_id=equipment
                )
                for name in ("Longsword", "Dagger")
            ]
        )
        await session.commit()
        ids = {name: e.id for name, e in items.items()} | {"D&D 5e": root.id}
    for repository in (equipment, rules):
        await _share(author, repository, bridge)
        copied = await author.post(f"/tenants/{bridge}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
    # The bridge's own work: two prototypes, and the three attachments.
    copies = await _by_name(bridge)
    async with admin_session_factory() as session:
        longsword_5e = Entity(tenant_id=bridge, name="Longsword 5e")
        economic = Entity(tenant_id=bridge, name="Economic Object")
        session.add_all([longsword_5e, economic])
        await session.flush()
        session.add_all(
            [
                Item(entity_id=longsword_5e.id, tenant_id=bridge),
                Item(entity_id=economic.id, tenant_id=bridge),
                # A parent of the bridge's own entity, which is an ordinary edge
                # and arrives as part of the entity.
                EntityPrototype(
                    entity_id=longsword_5e.id, prototype_id=copies["D&D 5e"], tenant_id=bridge
                ),
                EntityPrototype(
                    entity_id=copies["Longsword"], prototype_id=longsword_5e.id, tenant_id=bridge
                ),
                EntityPrototype(
                    entity_id=copies["Weapon"], prototype_id=economic.id, tenant_id=bridge
                ),
                EntityPrototype(
                    entity_id=copies["Weapon"], prototype_id=copies["D&D 5e"], tenant_id=bridge
                ),
            ]
        )
        await session.commit()
        ids |= {"Longsword 5e": longsword_5e.id, "Economic Object": economic.id}
    assert (await author.put(f"/tenants/{bridge}/published")).status_code == 200
    return _Stack(author, equipment, rules, bridge, ids, [equipment, rules, bridge], [author])


async def _table(
    raw_client: AsyncClient, jwks: FakeJwksServer, stack: _Stack, name: str
) -> tuple[Actor, uuid.UUID]:
    """A table with every repository of the stack granted, and its GM."""
    gm = await make_actor(raw_client, jwks, name)
    table = await gm.create_tenant(f"{name}'s table")
    stack.tenants.append(table)
    stack.actors.append(gm)
    for repository in (stack.equipment, stack.rules, stack.bridge):
        await _share(stack.author, repository, table)
    return gm, table


async def _copy(gm: Actor, table: uuid.UUID, repository: uuid.UUID, **body: Any) -> dict[str, Any]:
    response = await gm.post(f"/tenants/{table}/repositories/{repository}/copy", json=body or None)
    assert response.status_code in (200, 201), response.text
    return response.json()  # type: ignore[no-any-return]


SYSTEM = {
    "Longsword": ["Longsword 5e", "Weapon"],
    "Weapon": ["D&D 5e", "Economic Object"],
}


def _attached(parents: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: parents.get(name, []) for name in ("Longsword", "Weapon", "Dagger")}


async def test_a_table_that_held_the_equipment_gets_the_rules_added_to_its_items(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.equipment)
        assert _attached(await _parents(table)) == {
            "Longsword": ["Weapon"],
            "Weapon": [],
            "Dagger": ["Weapon"],
        }

        # The plan shows the attachments, writing nothing.
        plan = (await gm.get(f"/tenants/{table}/repositories/{stack.bridge}/copy-plan")).json()
        assert [(s["name"], s["attachments"]) for s in plan["steps"]] == [
            ("Common Equipment", 0),
            ("D&D 5e", 0),
            ("D&D Equipment", 3),
        ]
        assert _attached(await _parents(table))["Weapon"] == []

        # So does a dry run, which rolls everything back.
        dry = await gm.post(
            f"/tenants/{table}/repositories/{stack.bridge}/copy", json={"dry_run": True}
        )
        assert dry.status_code == 200, dry.text
        assert [s["attachments"] for s in dry.json()["steps"]] == [0, 3]
        assert _attached(await _parents(table))["Weapon"] == []
        assert await _links(table) == 0

        copied = await _copy(gm, table, stack.bridge)
        assert [(s["name"], s["attachments"], s["dropped"]) for s in copied["steps"]] == [
            ("D&D 5e", 0, []),
            ("D&D Equipment", 3, []),
        ]
        parents = await _parents(table)
        # Both of the table's own items, which it had before the bridge, have
        # the bridge's prototypes now: one the bridge's own, one another
        # repository's copy.
        assert _attached(parents) == {**SYSTEM, "Dagger": ["Weapon"]}
        assert parents["Longsword 5e"] == ["D&D 5e"]
        # And it is counted as what the bridge contributed.
        listing = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        contributed = {e["repository"]["name"]: e["contributed"] for e in listing}
        assert contributed["D&D Equipment"]["attachments"] == 3
        assert contributed["Common Equipment"]["attachments"] == 0
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_taking_the_bridge_first_gives_the_same_table(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The manifest copies the equipment and the rules before the bridge, and the
    attachments find the rows of the same call."""
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        copied = await _copy(gm, table, stack.bridge)
        assert [s["attachments"] for s in copied["steps"]] == [0, 0, 3]
        assert _attached(await _parents(table)) == {**SYSTEM, "Dagger": ["Weapon"]}
        assert await _links(table) == 3
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_a_table_that_holds_the_equipment_and_the_rules_takes_the_bridge_alone(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.equipment)
        await _copy(gm, table, stack.rules)
        copied = await _copy(gm, table, stack.bridge)
        assert [(s["name"], s["attachments"]) for s in copied["steps"]] == [("D&D Equipment", 3)]
        assert _attached(await _parents(table)) == {**SYSTEM, "Dagger": ["Weapon"]}
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_attachment_whose_end_is_missing_is_dropped_and_the_rest_goes_ahead(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.equipment)
        await _copy(gm, table, stack.rules)
        local = await _by_name(table)
        async with admin_session_factory() as session:
            # The table's Longsword is gone, and so is its copy of the system root.
            await session.execute(delete(Entity).where(Entity.id == local["Longsword"]))
            await session.execute(delete(Entity).where(Entity.id == local["D&D 5e"]))
            await session.commit()

        copied = await _copy(gm, table, stack.bridge)
        step = copied["steps"][-1]
        assert step["attachments"] == 1
        # (The bridge's own prototype, whose parent is the missing system root, is
        # dropped too, as an ordinary edge always was.)
        assert sorted(
            (d["kind"], d["source_id"], d["reason"])
            for d in step["dropped"]
            if d["kind"] == "attachment"
        ) == sorted(
            [
                ("attachment", str(stack.ids["Longsword"]), NO_CHILD),
                ("attachment", str(stack.ids["Weapon"]), NO_PARENT),
            ]
        )
        parents = await _parents(table)
        assert parents["Weapon"] == ["Economic Object"]
        # The bridge's own Longsword 5e still came, with its own edge to a
        # parent that isn't here.
        assert "Longsword 5e" in await _by_name(table)
        assert await _links(table) == 1
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_attachment_that_would_loop_is_dropped_and_the_rest_goes_ahead(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.equipment)
        await _copy(gm, table, stack.rules)
        local = await _by_name(table)
        async with admin_session_factory() as session:
            # The table made the system root a kind of Weapon itself, so Weapon
            # can't take it as a parent.
            session.add(
                EntityPrototype(
                    entity_id=local["D&D 5e"], prototype_id=local["Weapon"], tenant_id=table
                )
            )
            await session.commit()

        dry = await gm.post(
            f"/tenants/{table}/repositories/{stack.bridge}/copy", json={"dry_run": True}
        )
        assert dry.json()["steps"][-1]["attachments"] == 2
        copied = await _copy(gm, table, stack.bridge)
        step = copied["steps"][-1]
        assert step["attachments"] == 2
        assert [(d["kind"], d["source_id"], d["reason"]) for d in step["dropped"]] == [
            ("attachment", str(stack.ids["Weapon"]), LOOP)
        ]
        parents = await _parents(table)
        assert parents["Longsword"] == ["Longsword 5e", "Weapon"]
        assert parents["Weapon"] == ["Economic Object"]
        assert await _links(table) == 2
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_edge_the_table_already_has_is_recorded_not_written_twice(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.equipment)
        await _copy(gm, table, stack.rules)
        local = await _by_name(table)
        async with admin_session_factory() as session:
            session.add(
                EntityPrototype(
                    entity_id=local["Weapon"], prototype_id=local["D&D 5e"], tenant_id=table
                )
            )
            await session.commit()
        copied = await _copy(gm, table, stack.bridge)
        assert copied["steps"][-1]["attachments"] == 2
        assert _attached(await _parents(table))["Weapon"] == ["D&D 5e", "Economic Object"]
        # Taken all the same, so removing it later can be told from the table's own.
        assert await _links(table) == 3
    finally:
        await cleanup(stack.tenants, stack.actors)


def _pair(stack: _Stack, child: str, parent: str, action: str) -> dict[str, str]:
    return {
        "child_source_id": str(stack.ids[child]),
        "parent_source_id": str(stack.ids[parent]),
        "action": action,
    }


async def _taken(
    raw_client: AsyncClient, jwks: FakeJwksServer
) -> tuple[_Stack, Actor, uuid.UUID, str]:
    """A table that took the equipment, the rules and the bridge, with the URL of
    the bridge's updates."""
    stack = await _stack(raw_client, jwks)
    gm, table = await _table(raw_client, jwks, stack, "gm")
    await _copy(gm, table, stack.bridge)
    return stack, gm, table, f"/tenants/{table}/repositories/{stack.bridge}/updates"


async def test_nothing_is_offered_when_nothing_changed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, _, url = await _taken(raw_client, fake_jwks_server)
    try:
        updates = (await gm.get(url)).json()
        assert updates["attachments_added"] == []
        assert updates["attachments_removed"] == []
        assert updates["attachments_deleted_locally"] == []
        assert updates["changed"] == []
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_attachment_the_bridge_adds_later_is_offered_and_applied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, url = await _taken(raw_client, fake_jwks_server)
    try:
        bridge = await _by_name(stack.bridge)
        async with admin_session_factory() as session:
            session.add(
                EntityPrototype(
                    entity_id=bridge["Dagger"],
                    prototype_id=stack.ids["Economic Object"],
                    tenant_id=stack.bridge,
                )
            )
            await session.commit()

        local = await _by_name(table)
        updates = (await gm.get(url)).json()
        assert updates["attachments_removed"] == []
        assert updates["attachments_added"] == [
            {
                "child_source_id": str(stack.ids["Dagger"]),
                "child_local_id": str(local["Dagger"]),
                "child_name": "Dagger",
                "parent_source_id": str(stack.ids["Economic Object"]),
                "parent_local_id": str(local["Economic Object"]),
                "parent_name": "Economic Object",
                "applicable": True,
                "reason": None,
                # Added after the bridge's release: edited since it.
                "state": "edited",
                "breaking": [],
            }
        ]
        # Nothing about the bridge's entities changed, only its parents.
        assert updates["changed"] == []

        applied = await gm.post(
            url,
            json={"actions": [], "attachments": [_pair(stack, "Dagger", "Economic Object", "add")]},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json() == {
            "dry_run": False,
            "applied": 0,
            "added": 0,
            "detached": 0,
            "attachments_added": 1,
            "attachments_detached": 0,
            "not_applied": [],
        }
        assert (await _parents(table))["Dagger"] == ["Economic Object", "Weapon"]
        assert (await gm.get(url)).json()["attachments_added"] == []
        assert await _links(table) == 4

        # Nothing is left to add, so asking again is refused and changes nothing.
        again = await gm.post(
            url,
            json={"actions": [], "attachments": [_pair(stack, "Dagger", "Economic Object", "add")]},
        )
        assert again.status_code == 422, again.text
        assert (await _parents(table))["Dagger"] == ["Economic Object", "Weapon"]
        assert await _links(table) == 4
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_attachment_the_bridge_removes_is_offered_for_detaching_only(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, url = await _taken(raw_client, fake_jwks_server)
    try:
        bridge = await _by_name(stack.bridge)
        async with admin_session_factory() as session:
            await session.execute(
                delete(EntityPrototype).where(
                    EntityPrototype.entity_id == bridge["Longsword"],
                    EntityPrototype.prototype_id == stack.ids["Longsword 5e"],
                )
            )
            await session.commit()

        updates = (await gm.get(url)).json()
        assert [(a["child_name"], a["parent_name"]) for a in updates["attachments_removed"]] == [
            ("Longsword", "Longsword 5e")
        ]
        assert updates["attachments_added"] == []
        # It can't be taken, and detaching is the only thing it is offered.
        refused = await gm.post(
            url,
            json={
                "actions": [],
                "attachments": [_pair(stack, "Longsword", "Longsword 5e", "add")],
            },
        )
        assert refused.status_code == 422

        detached = await gm.post(
            url,
            json={
                "actions": [],
                "attachments": [_pair(stack, "Longsword", "Longsword 5e", "detach")],
            },
        )
        assert detached.status_code == 200, detached.text
        assert detached.json()["attachments_detached"] == 1
        # The parent stays: taking D&D off a table is not what updating does.
        assert (await _parents(table))["Longsword"] == ["Longsword 5e", "Weapon"]
        assert await _links(table) == 2
        assert (await gm.get(url)).json()["attachments_removed"] == []
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_attachment_whose_edge_the_table_removed_is_shown_not_offered(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, url = await _taken(raw_client, fake_jwks_server)
    try:
        local = await _by_name(table)
        async with admin_session_factory() as session:
            await session.execute(
                delete(EntityPrototype).where(
                    EntityPrototype.entity_id == local["Weapon"],
                    EntityPrototype.prototype_id == local["Economic Object"],
                )
            )
            await session.commit()
        updates = (await gm.get(url)).json()
        assert [
            (a["child_name"], a["parent_name"]) for a in updates["attachments_deleted_locally"]
        ] == [("Weapon", "Economic Object")]
        assert updates["attachments_added"] == []
        assert updates["attachments_removed"] == []
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_entity_and_an_attachment_to_it_are_added_in_one_call(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, url = await _taken(raw_client, fake_jwks_server)
    try:
        bridge = await _by_name(stack.bridge)
        async with admin_session_factory() as session:
            greatsword = Entity(tenant_id=stack.bridge, name="Greatsword 5e")
            session.add(greatsword)
            await session.flush()
            session.add_all(
                [
                    Item(entity_id=greatsword.id, tenant_id=stack.bridge),
                    EntityPrototype(
                        entity_id=bridge["Longsword"],
                        prototype_id=greatsword.id,
                        tenant_id=stack.bridge,
                    ),
                ]
            )
            await session.commit()
            stack.ids["Greatsword 5e"] = greatsword.id

        updates = (await gm.get(url)).json()
        assert [(a["kind"], a["name"]) for a in updates["added"]] == [("entity", "Greatsword 5e")]
        (waiting,) = updates["attachments_added"]
        assert (waiting["applicable"], waiting["reason"], waiting["parent_local_id"]) == (
            False,
            NO_PARENT,
            None,
        )

        # On its own it is not applied, and it keeps being offered.
        alone = await gm.post(
            url,
            json={
                "actions": [],
                "attachments": [_pair(stack, "Longsword", "Greatsword 5e", "add")],
            },
        )
        assert alone.status_code == 200, alone.text
        assert alone.json()["attachments_added"] == 0
        assert alone.json()["not_applied"] == [
            {
                "kind": "attachment",
                "source_id": str(stack.ids["Longsword"]),
                "field": "prototypes",
                "reason": NO_PARENT,
                "name": "Longsword",
                "label": "Greatsword 5e",
            }
        ]
        assert len((await gm.get(url)).json()["attachments_added"]) == 1

        together = await gm.post(
            url,
            json={
                "actions": [
                    {
                        "kind": "entity",
                        "source_id": str(stack.ids["Greatsword 5e"]),
                        "action": "add",
                    }
                ],
                "attachments": [_pair(stack, "Longsword", "Greatsword 5e", "add")],
            },
        )
        assert together.status_code == 200, together.text
        assert (together.json()["added"], together.json()["attachments_added"]) == (1, 1)
        assert together.json()["not_applied"] == []
        assert (await _parents(table))["Longsword"] == ["Greatsword 5e", "Longsword 5e", "Weapon"]
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_an_update_attachment_that_would_loop_is_not_applied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, url = await _taken(raw_client, fake_jwks_server)
    try:
        bridge = await _by_name(stack.bridge)
        local = await _by_name(table)
        async with admin_session_factory() as session:
            # The bridge gives its Dagger Longsword 5e as a parent...
            session.add(
                EntityPrototype(
                    entity_id=bridge["Dagger"],
                    prototype_id=stack.ids["Longsword 5e"],
                    tenant_id=stack.bridge,
                )
            )
            # ...while the table has made its Longsword 5e a kind of Dagger.
            session.add(
                EntityPrototype(
                    entity_id=local["Longsword 5e"], prototype_id=local["Dagger"], tenant_id=table
                )
            )
            await session.commit()
        response = await gm.post(
            url,
            json={
                "actions": [],
                "attachments": [_pair(stack, "Dagger", "Longsword 5e", "add")],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["attachments_added"] == 0
        assert [(n["kind"], n["reason"]) for n in response.json()["not_applied"]] == [
            ("attachment", LOOP)
        ]
        assert (await _parents(table))["Dagger"] == ["Weapon"]
        assert len((await gm.get(url)).json()["attachments_added"]) == 1
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_keeping_a_copy_drops_its_links_and_leaves_the_parents(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, _ = await _taken(raw_client, fake_jwks_server)
    try:
        assert await _links(table) == 3
        copied = await _copy(gm, table, stack.bridge, again="keep")
        assert copied["previous"]["mode"] == "keep"
        assert copied["previous"]["also_removed"] == {}
        # The edge to the system root was already there, so only two were written.
        assert copied["steps"][-1]["attachments"] == 2
        # Copied afresh: the edges the first copy wrote are still there, and the
        # second copy took its own.
        assert await _links(table) == 3
        assert (await _parents(table))["Weapon"].count("Economic Object") == 2
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_purging_a_copy_takes_its_attachments_with_it_and_counts_them(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack, gm, table, _ = await _taken(raw_client, fake_jwks_server)
    try:
        response = await gm.post(
            f"/tenants/{table}/repositories/{stack.bridge}/copy", json={"again": "purge"}
        )
        assert response.status_code == 201, response.text
        # Two edges went with the parents the purge deleted, as they always did;
        # the third, to the rules' own copy, is the one the attachment counts.
        assert response.json()["previous"]["also_removed"] == {
            "entity_prototype": 2,
            "attachment": 1,
        }
        # The copy that follows put all three back, the edge to the rules' own copy
        # included, which the purge took off the table's own row.
        assert response.json()["steps"][-1]["attachments"] == 3
        assert _attached(await _parents(table)) == {**SYSTEM, "Dagger": ["Weapon"]}
        assert await _links(table) == 3
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_the_other_repositorys_link_for_a_purged_pair_goes_too(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Two repositories can attach the same pair: one edge, two links. Purging one
    removes the edge, and the other's next update offers it again."""
    stack, gm, table, _ = await _taken(raw_client, fake_jwks_server)
    elsewhere = uuid.uuid4()
    try:
        async with admin_session_factory() as session:
            session.add(
                RepositoryCopyLinkAttachment(
                    tenant_id=table,
                    source_tenant_id=elsewhere,
                    child_source_id=stack.ids["Weapon"],
                    parent_source_id=stack.ids["D&D 5e"],
                )
            )
            await session.commit()
        assert await _links(table) == 4
        response = await gm.post(
            f"/tenants/{table}/repositories/{stack.bridge}/copy", json={"again": "purge"}
        )
        assert response.status_code == 201, response.text
        async with admin_session_factory() as session:
            others = (
                await session.execute(
                    select(func.count())
                    .select_from(RepositoryCopyLinkAttachment)
                    .where(
                        RepositoryCopyLinkAttachment.tenant_id == table,
                        RepositoryCopyLinkAttachment.source_tenant_id == elsewhere,
                    )
                )
            ).scalar_one()
        assert others == 0
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_the_attachment_table_is_the_copying_tenants_alone(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Tenant isolation, and no gated read of it: a tenant reading a repository
    sees the repository's entities, never what the repository itself took."""
    stack, gm, table, _ = await _taken(raw_client, fake_jwks_server)
    try:
        # The bridge, itself a copying tenant, holds no attachment links of its own,
        # so give it one to hide.
        async with admin_session_factory() as session:
            session.add(
                RepositoryCopyLinkAttachment(
                    tenant_id=stack.bridge,
                    source_tenant_id=stack.equipment,
                    child_source_id=uuid.uuid4(),
                    parent_source_id=uuid.uuid4(),
                )
            )
            await session.commit()

        async def visible(*, tenant: uuid.UUID, reading: uuid.UUID | None, of: uuid.UUID) -> int:
            async with engine.connect() as conn, conn.begin():
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
                )
                await conn.execute(
                    text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                    {"r": str(reading) if reading else ""},
                )
                return int(
                    (
                        await conn.execute(
                            text(
                                "SELECT count(*) FROM repository_copy_link_attachment "
                                "WHERE tenant_id = :t"
                            ),
                            {"t": of},
                        )
                    ).scalar_one()
                )

        assert await visible(tenant=table, reading=None, of=table) == 3
        assert await visible(tenant=table, reading=None, of=stack.bridge) == 0
        assert await visible(tenant=table, reading=stack.bridge, of=stack.bridge) == 0
        assert await visible(tenant=stack.bridge, reading=None, of=stack.bridge) == 1
        assert await visible(tenant=stack.bridge, reading=None, of=table) == 0
    finally:
        await cleanup(stack.tenants, stack.actors)


# --- RFC 0033's stack: core, equipment over it, rules over it, the bridge over both ---


@dataclass
class _Levels:
    author: Actor
    core: uuid.UUID
    equipment: uuid.UUID
    rules: uuid.UUID
    bridge: uuid.UUID
    ids: dict[str, uuid.UUID]
    tenants: list[uuid.UUID]
    actors: list[Actor]


async def _item(session: Any, tenant: uuid.UUID, name: str, *parents: uuid.UUID) -> uuid.UUID:
    entity = Entity(tenant_id=tenant, name=name)
    session.add(entity)
    await session.flush()
    session.add(Item(entity_id=entity.id, tenant_id=tenant))
    await session.flush()
    session.add_all(
        EntityPrototype(entity_id=entity.id, prototype_id=p, tenant_id=tenant) for p in parents
    )
    await session.flush()
    return entity.id


async def _levels(raw_client: AsyncClient, jwks: FakeJwksServer) -> _Levels:
    author = await make_actor(raw_client, jwks, "author")
    core, equipment, rules, bridge = [
        await author.create_tenant(name, kind="repository")
        for name in ("Core", "Common Equipment", "D&D 5e", "D&D Equipment")
    ]
    ids: dict[str, uuid.UUID] = {}

    async def copy(into: uuid.UUID, *repositories: uuid.UUID) -> None:
        for repository in repositories:
            await _share(author, repository, into)
            copied = await author.post(f"/tenants/{into}/repositories/{repository}/copy")
            assert copied.status_code == 201, copied.text

    async with admin_session_factory() as session:
        ids["Physical Object"] = await _item(session, core, "Physical Object")
        await session.commit()
    await copy(equipment, core)
    await copy(rules, core)
    copies = await _by_name(equipment)
    async with admin_session_factory() as session:
        ids["Weapon"] = await _item(session, equipment, "Weapon", copies["Physical Object"])
        ids["Longsword"] = await _item(session, equipment, "Longsword", ids["Weapon"])
        ids["D&D 5e"] = await _item(session, rules, "D&D 5e")
        ids["Martial Weapon"] = await _item(session, rules, "Martial Weapon", ids["D&D 5e"])
        await session.commit()
    # The bridge takes what its dependencies built on too.
    await _share(author, core, bridge)
    await copy(bridge, equipment, rules)
    copies = await _by_name(bridge)
    async with admin_session_factory() as session:
        ids["Economic Object"] = await _item(session, bridge, "Economic Object", copies["D&D 5e"])
        ids["Longsword 5e"] = await _item(session, bridge, "Longsword 5e", copies["Martial Weapon"])
        # The economic prototype goes on a form, the system prototype on an item.
        session.add_all(
            [
                EntityPrototype(
                    entity_id=copies["Weapon"],
                    prototype_id=ids["Economic Object"],
                    tenant_id=bridge,
                ),
                EntityPrototype(
                    entity_id=copies["Longsword"],
                    prototype_id=ids["Longsword 5e"],
                    tenant_id=bridge,
                ),
            ]
        )
        await session.commit()
    for repository in (core, equipment, rules, bridge):
        assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
    return _Levels(
        author, core, equipment, rules, bridge, ids, [core, equipment, rules, bridge], [author]
    )


async def test_the_whole_stack_reaches_a_table_that_held_the_equipment_first(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    levels = await _levels(raw_client, fake_jwks_server)
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("My Table")
    levels.tenants.append(table)
    levels.actors.append(gm)
    try:
        for repository in (levels.core, levels.equipment, levels.rules, levels.bridge):
            await _share(levels.author, repository, table)
        first = await gm.post(f"/tenants/{table}/repositories/{levels.equipment}/copy")
        assert first.status_code == 201, first.text
        assert [s["name"] for s in first.json()["steps"]] == ["Core", "Common Equipment"]
        assert (await _parents(table))["Longsword"] == ["Weapon"]

        later = await gm.post(f"/tenants/{table}/repositories/{levels.bridge}/copy")
        assert later.status_code == 201, later.text
        assert [(s["name"], s["attachments"]) for s in later.json()["steps"]] == [
            ("D&D 5e", 0),
            ("D&D Equipment", 2),
        ]
        assert await _parents(table) == {
            "Weapon": ["Economic Object", "Physical Object"],
            "Longsword": ["Longsword 5e", "Weapon"],
            "Longsword 5e": ["Martial Weapon"],
            "Martial Weapon": ["D&D 5e"],
            "Economic Object": ["D&D 5e"],
        }
        # One Longsword, not two: the item the table had is the one with D&D on it.
        assert (await _names(table)).count("Longsword") == 1
    finally:
        await cleanup(levels.tenants, levels.actors)


async def _names(tenant: uuid.UUID) -> list[str]:
    async with admin_session_factory() as session:
        return list(await session.scalars(select(Entity.name).where(Entity.tenant_id == tenant)))


async def test_a_correction_to_the_equipment_reaches_a_table_without_losing_the_attachments(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    levels = await _levels(raw_client, fake_jwks_server)
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("My Table")
    levels.tenants.append(table)
    levels.actors.append(gm)
    try:
        for repository in (levels.core, levels.equipment, levels.rules, levels.bridge):
            await _share(levels.author, repository, table)
        assert (
            await gm.post(f"/tenants/{table}/repositories/{levels.bridge}/copy")
        ).status_code == 201
        before = await _parents(table)

        async with admin_session_factory() as session:
            (await session.get_one(Entity, levels.ids["Longsword"])).name = "Long Sword"
            await session.commit()
        equipment_updates = (
            await gm.get(f"/tenants/{table}/repositories/{levels.equipment}/updates")
        ).json()
        assert [
            (c["name"], [f["field"] for f in c["fields"]]) for c in equipment_updates["changed"]
        ] == [("Longsword", ["name"])]
        applied = await gm.post(
            f"/tenants/{table}/repositories/{levels.equipment}/updates",
            json={
                "actions": [
                    {
                        "kind": "entity",
                        "source_id": str(levels.ids["Longsword"]),
                        "action": "apply",
                    }
                ]
            },
        )
        assert applied.status_code == 200, applied.text

        # The same edges on the renamed item, and nothing for the bridge to offer.
        after = await _parents(table)
        assert after.pop("Long Sword") == before.pop("Longsword")
        assert after == before
        bridge_updates = (
            await gm.get(f"/tenants/{table}/repositories/{levels.bridge}/updates")
        ).json()
        assert bridge_updates["attachments_added"] == []
        assert bridge_updates["attachments_removed"] == []
        assert bridge_updates["attachments_deleted_locally"] == []
    finally:
        await cleanup(levels.tenants, levels.actors)


async def test_a_parent_the_dependency_adds_to_what_the_bridge_attached_changes_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The bridge attached Physical Object to Longsword, then the equipment gave
    Longsword it too. The bridge already has it, so there is nothing to take
    (ADR 0121: a set's change the local copy already has), the pair stays the
    bridge's attachment, and a table has one edge."""
    levels = await _levels(raw_client, fake_jwks_server)
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("My Table")
    levels.tenants.append(table)
    levels.actors.append(gm)
    try:
        copies = await _by_name(levels.bridge)
        async with admin_session_factory() as session:
            session.add(
                EntityPrototype(
                    entity_id=copies["Longsword"],
                    prototype_id=copies["Physical Object"],
                    tenant_id=levels.bridge,
                )
            )
            session.add(
                EntityPrototype(
                    entity_id=levels.ids["Longsword"],
                    prototype_id=(await _by_name(levels.equipment))["Physical Object"],
                    tenant_id=levels.equipment,
                )
            )
            await session.commit()
        for repository in (levels.core, levels.equipment, levels.rules, levels.bridge):
            await _share(levels.author, repository, table)
        copied = await gm.post(f"/tenants/{table}/repositories/{levels.bridge}/copy")
        assert copied.status_code == 201, copied.text
        assert (await _parents(table))["Longsword"] == [
            "Longsword 5e",
            "Physical Object",
            "Weapon",
        ]
        # The equipment's own edge arrived with it, so the bridge's twin of it was
        # already there: recorded, not written again.
        assert [s["attachments"] for s in copied.json()["steps"]] == [0, 0, 0, 2]
    finally:
        await cleanup(levels.tenants, levels.actors)


# --- GET /tenants/{id}/attachments: what a repository's authors can't see otherwise (ADR 0174) ---


async def test_a_repositorys_authors_list_the_parents_it_attaches(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        copies = await _by_name(stack.bridge)
        listed = await stack.author.get(f"/tenants/{stack.bridge}/attachments")
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"] == [
            {
                "child_source_id": str(stack.ids["Longsword"]),
                "child_local_id": str(copies["Longsword"]),
                "child_name": "Longsword",
                "parent_source_id": str(stack.ids["Longsword 5e"]),
                "parent_local_id": str(copies["Longsword 5e"]),
                "parent_name": "Longsword 5e",
            },
            {
                "child_source_id": str(stack.ids["Weapon"]),
                "child_local_id": str(copies["Weapon"]),
                "child_name": "Weapon",
                "parent_source_id": str(stack.ids["D&D 5e"]),
                "parent_local_id": str(copies["D&D 5e"]),
                "parent_name": "D&D 5e",
            },
            {
                "child_source_id": str(stack.ids["Weapon"]),
                "child_local_id": str(copies["Weapon"]),
                "child_name": "Weapon",
                "parent_source_id": str(stack.ids["Economic Object"]),
                "parent_local_id": str(copies["Economic Object"]),
                "parent_name": "Economic Object",
            },
        ]
        # What arrived with a copy is not one, and a repository with none lists none.
        assert (await stack.author.get(f"/tenants/{stack.equipment}/attachments")).json()[
            "items"
        ] == []

        # An edge the author removes is gone from it.
        async with admin_session_factory() as session:
            await session.execute(
                delete(EntityPrototype).where(
                    EntityPrototype.entity_id == copies["Weapon"],
                    EntityPrototype.prototype_id == copies["Economic Object"],
                )
            )
            await session.commit()
        after = (await stack.author.get(f"/tenants/{stack.bridge}/attachments")).json()
        assert [(i["child_name"], i["parent_name"]) for i in after["items"]] == [
            ("Longsword", "Longsword 5e"),
            ("Weapon", "D&D 5e"),
        ]
        assert after["total"] == 2
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_the_attachments_of_a_play_tenant_or_a_stranger_are_refused(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    stack.actors.append(stranger)
    try:
        play = await gm.get(f"/tenants/{table}/attachments")
        assert play.status_code == 409
        assert play.json()["type"] == "not-a-repository"
        # Nobody but a member reads a repository's own attachments, a table that
        # copied it included.
        assert (await stranger.get(f"/tenants/{stack.bridge}/attachments")).status_code in (
            403,
            404,
        )
        assert (await gm.get(f"/tenants/{stack.bridge}/attachments")).status_code in (403, 404)
    finally:
        await cleanup(stack.tenants, stack.actors)
