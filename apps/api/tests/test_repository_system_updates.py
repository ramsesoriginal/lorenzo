"""ADR 0469: the update engine tracks the game systems and the templates of a repository as it does
its stat groups: what changed upstream, what is added and removed, a conflict named, a name that
clashes asked about, and a copy made before there were links offered what it already has.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import delete, select

from lorenzo_api.models import (
    Entity,
    RepositoryCopyLinkSystem,
    RepositoryCopyLinkTemplate,
    StatDefinition,
    StatGroup,
    StatValueType,
    System,
    Template,
    TemplateSlot,
    TemplateSlotStat,
)


@dataclass
class _World:
    author: Actor
    gm: Actor
    repository: uuid.UUID
    table: uuid.UUID
    ids: dict[str, uuid.UUID]

    @property
    def url(self) -> str:
        return f"/tenants/{self.table}/repositories/{self.repository}"


async def _world(raw_client: AsyncClient, jwks: FakeJwksServer) -> _World:
    author = await make_actor(raw_client, jwks, "author")
    gm = await make_actor(raw_client, jwks, "gm")
    repository = await author.create_tenant("Rules", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=repository, name="Abilities")
        sword = Entity(tenant_id=repository, name="Sword")
        hero = Entity(tenant_id=repository, name="Hero")
        system = System(tenant_id=repository, slug="fx", name="Fixture system")
        session.add_all([group, sword, hero, system])
        await session.flush()
        strength = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Strength",
            value_type=StatValueType.INT,
        )
        dexterity = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Dexterity",
            value_type=StatValueType.INT,
        )
        session.add_all([strength, dexterity])
        group.system_id = system.id
        system.root_entry_id = sword.id
        template = Template(
            tenant_id=repository, name="Sheet", system_id=system.id, required_kind=None
        )
        session.add(template)
        await session.flush()
        slot = TemplateSlot(
            tenant_id=repository, template_id=template.id, position=0, kind="stats", label="Core"
        )
        session.add(slot)
        await session.flush()
        session.add(
            TemplateSlotStat(
                slot_id=slot.id,
                position=0,
                tenant_id=repository,
                stat_definition_id=strength.id,
                label="Str",
            )
        )
        await session.commit()
        ids = {
            "group": group.id,
            "sword": sword.id,
            "hero": hero.id,
            "system": system.id,
            "strength": strength.id,
            "dexterity": dexterity.id,
            "template": template.id,
            "slot": slot.id,
        }
    assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
    copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
    assert copied.status_code == 201, copied.text
    return _World(author, gm, repository, table, ids)


async def _rows(model: Any, tenant_id: uuid.UUID) -> list[Any]:
    async with admin_session_factory() as session:
        return list(await session.scalars(select(model).where(model.tenant_id == tenant_id)))


def _by_row(updates: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (r["kind"], r["name"]): {f["field"]: f for f in r["fields"]} for r in updates["changed"]
    }


def _act(kind: str, source: uuid.UUID, verb: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "source_id": str(source), "action": verb, **extra}


async def test_a_copy_links_its_system_and_its_template_and_nothing_is_changed_yet(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    try:
        (system_link,) = await _rows(RepositoryCopyLinkSystem, world.table)
        (template_link,) = await _rows(RepositoryCopyLinkTemplate, world.table)
        assert (system_link.source_id, system_link.mode) == (world.ids["system"], "copied")
        assert template_link.source_id == world.ids["template"]
        assert system_link.snapshot == {"name": "Fixture system", "root": str(world.ids["sword"])}
        assert template_link.snapshot["name"] == "Sheet"
        assert template_link.snapshot["system"] == "fx"
        (slot,) = template_link.snapshot["slots"]
        assert slot["stats"] == [[str(world.ids["strength"]), "Str"]]
        assert slot["group"] is None
        updates = (await world.gm.get(f"{world.url}/updates")).json()
        assert (updates["changed"], updates["removed"], updates["added"]) == ([], [], [])
        # Both are listed among what the copy contributed.
        listed = (await world.gm.get(f"{world.url}/contributions")).json()["items"]
        assert {(r["kind"], r["name"]) for r in listed} >= {
            ("system", "Fixture system"),
            ("template", "Sheet"),
        }
    finally:
        await cleanup([world.repository, world.table], [world.author, world.gm])


async def test_what_changed_in_a_system_and_a_template_is_offered_and_applied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids = world.ids
    try:
        async with admin_session_factory() as session:
            (await session.get_one(System, ids["system"])).name = "Fixture rules"
            (await session.get_one(System, ids["system"])).root_entry_id = ids["hero"]
            template = await session.get_one(Template, ids["template"])
            template.name = "Character sheet"
            template.required_ancestor_entry_id = ids["sword"]
            session.add(
                TemplateSlotStat(
                    slot_id=ids["slot"],
                    position=1,
                    tenant_id=world.repository,
                    stat_definition_id=ids["dexterity"],
                    label="Dex",
                )
            )
            await session.commit()

        rows = _by_row((await world.gm.get(f"{world.url}/updates")).json())
        system = rows[("system", "Fixture system")]
        assert (system["name"]["state"], system["name"]["upstream"]) == ("clean", "Fixture rules")
        assert system["root"]["upstream"] == str(ids["hero"])
        sheet = rows[("template", "Sheet")]
        assert sheet["name"]["upstream"] == "Character sheet"
        assert sheet["ancestor"]["upstream"] == str(ids["sword"])
        (upstream_slot,) = sheet["slots"]["upstream"]
        assert [label for _, label in upstream_slot["stats"]] == ["Str", "Dex"]
        # No digest says anything of a system or a template.
        listed = (await world.gm.get(f"{world.url}/updates")).json()["changed"]
        assert {r["state"] for r in listed if r["kind"] in ("system", "template")} == {None}

        actions = [
            _act("system", ids["system"], "apply"),
            _act("template", ids["template"], "apply"),
        ]
        applied = await world.gm.post(f"{world.url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert applied.json()["applied"] == 2 and applied.json()["not_applied"] == []

        (local_system,) = await _rows(System, world.table)
        assert local_system.name == "Fixture rules"
        async with admin_session_factory() as session:
            entity_names = {
                e.id: e.name
                for e in await session.scalars(
                    select(Entity).where(Entity.tenant_id == world.table)
                )
            }
            (local_template,) = await _rows(Template, world.table)
            assert local_template.name == "Character sheet"
            assert entity_names[local_system.root_entry_id] == "Hero"
            assert entity_names[local_template.required_ancestor_entry_id] == "Sword"
            slot_ids = list(
                await session.scalars(
                    select(TemplateSlot.id).where(TemplateSlot.template_id == local_template.id)
                )
            )
            labels = list(
                await session.scalars(
                    select(TemplateSlotStat.label)
                    .where(TemplateSlotStat.slot_id.in_(slot_ids))
                    .order_by(TemplateSlotStat.position)
                )
            )
        assert labels == ["Str", "Dex"]
        assert (await world.gm.get(f"{world.url}/updates")).json()["changed"] == []
    finally:
        await cleanup([world.repository, world.table], [world.author, world.gm])


async def test_a_conflict_in_a_template_is_named_and_a_group_follows_its_system(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids = world.ids
    try:
        # The library renamed its template, and so did the repository.
        async with admin_session_factory() as session:
            local = (await _rows(Template, world.table))[0]
            (await session.get_one(Template, local.id)).name = "My sheet"
            (await session.get_one(Template, ids["template"])).name = "Their sheet"
            # The repository adds a second system and moves its group there.
            other = System(tenant_id=world.repository, slug="gx", name="Other system")
            session.add(other)
            await session.flush()
            (await session.get_one(StatGroup, ids["group"])).system_id = other.id
            await session.commit()
            other_id = other.id

        updates = (await world.gm.get(f"{world.url}/updates")).json()
        rows = _by_row(updates)
        assert rows[("template", "My sheet")]["name"]["state"] == "conflict"
        assert rows[("stat_group", "Abilities")]["system"]["upstream"] == "gx"
        assert [(a["kind"], a["name"], a["collision"]) for a in updates["added"]] == [
            ("system", "Other system", None)
        ]

        unnamed = await world.gm.post(
            f"{world.url}/updates", json={"actions": [_act("template", ids["template"], "apply")]}
        )
        assert unnamed.status_code == 409
        assert unnamed.json()["conflicts"] == [
            {"kind": "template", "source_id": str(ids["template"]), "field": "name"}
        ]

        actions = [
            _act("system", other_id, "add"),
            _act("stat_group", ids["group"], "apply"),
            _act("template", ids["template"], "apply", keep_local=["name"]),
        ]
        applied = await world.gm.post(f"{world.url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []

        systems = {s.slug: s for s in await _rows(System, world.table)}
        assert set(systems) == {"fx", "gx"}
        (group,) = await _rows(StatGroup, world.table)
        assert group.system_id == systems["gx"].id
        assert (await _rows(Template, world.table))[0].name == "My sheet"
        # What was added is linked, so it is tracked from now on.
        links = {
            link.source_id: link.mode for link in await _rows(RepositoryCopyLinkSystem, world.table)
        }
        assert links[other_id] == "copied"
    finally:
        await cleanup([world.repository, world.table], [world.author, world.gm])


async def test_a_template_added_upstream_asks_when_its_name_is_taken_and_one_removed_is_detached(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids = world.ids
    try:
        async with admin_session_factory() as session:
            session.add_all(
                [
                    Template(tenant_id=world.table, name="Extras"),
                    Template(tenant_id=world.repository, name="Extras"),
                    Template(tenant_id=world.repository, name="Spells"),
                ]
            )
            await session.execute(delete(Template).where(Template.id == ids["template"]))
            await session.commit()
        updates = (await world.gm.get(f"{world.url}/updates")).json()
        assert [(r["kind"], r["name"]) for r in updates["removed"]] == [("template", "Sheet")]
        added = {a["name"]: a for a in updates["added"]}
        assert set(added) == {"Extras", "Spells"}
        assert added["Spells"]["collision"] is None
        assert added["Extras"]["collision"]["kind"] == "template"
        assert added["Extras"]["collision"]["choices"] == ["rename", "skip"]

        extras, spells = (uuid.UUID(added[n]["source_id"]) for n in ("Extras", "Spells"))
        refused = await world.gm.post(
            f"{world.url}/updates", json={"actions": [_act("template", extras, "add")]}
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-needs-choices"

        actions = [
            _act(
                "template", extras, "add", resolution={"action": "rename", "name": "Their extras"}
            ),
            _act("template", spells, "add"),
            _act("template", ids["template"], "detach"),
        ]
        applied = await world.gm.post(f"{world.url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert (applied.json()["added"], applied.json()["detached"]) == (2, 1)
        names = sorted(t.name for t in await _rows(Template, world.table))
        assert names == ["Extras", "Sheet", "Spells", "Their extras"]
        assert (await world.gm.get(f"{world.url}/updates")).json()["added"] == []
    finally:
        await cleanup([world.repository, world.table], [world.author, world.gm])


async def test_a_copy_made_before_the_links_is_offered_what_it_already_has(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids = world.ids
    try:
        async with admin_session_factory() as session:
            await session.execute(
                delete(RepositoryCopyLinkSystem).where(
                    RepositoryCopyLinkSystem.tenant_id == world.table
                )
            )
            await session.execute(
                delete(RepositoryCopyLinkTemplate).where(
                    RepositoryCopyLinkTemplate.tenant_id == world.table
                )
            )
            await session.commit()
        updates = (await world.gm.get(f"{world.url}/updates")).json()
        added = {(a["kind"], a["name"]): a for a in updates["added"]}
        assert set(added) == {("system", "Fixture system"), ("template", "Sheet")}
        # The system joins by slug, with nothing to choose; the template's name is taken.
        assert added[("system", "Fixture system")]["collision"] is None
        assert added[("template", "Sheet")]["collision"]["choices"] == ["rename", "skip"]

        actions = [
            _act("system", ids["system"], "add"),
            _act("template", ids["template"], "add", resolution={"action": "skip"}),
        ]
        applied = await world.gm.post(f"{world.url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        # Joined: the library keeps its own system, and the link says it is not a copy.
        (link,) = await _rows(RepositoryCopyLinkSystem, world.table)
        assert (link.source_id, link.mode) == (ids["system"], "merged")
        assert len(await _rows(System, world.table)) == 1
        assert len(await _rows(Template, world.table)) == 1
        # Merged is never offered again, nor is a skipped template... until it is asked for.
        later = (await world.gm.get(f"{world.url}/updates")).json()
        assert [a["name"] for a in later["added"]] == ["Sheet"]
        assert later["changed"] == []
    finally:
        await cleanup([world.repository, world.table], [world.author, world.gm])
