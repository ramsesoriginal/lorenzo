"""ADR 0121: finding and applying a copied repository's updates, through
the real HTTP API. The repository is edited straight in the database, as
its authors would through the ordinary routes.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import delete, select

from lorenzo_api.models import (
    AuditLog,
    ComputedStat,
    ComputedStatLinear,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Item,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)


@dataclass
class _World:
    author: Actor
    gm: Actor
    repository: uuid.UUID
    table: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _world(raw_client: AsyncClient, jwks: FakeJwksServer) -> _World:
    author = await make_actor(raw_client, jwks, "author")
    gm = await make_actor(raw_client, jwks, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=repository, name="Abilities")
        entities = {
            name: Entity(tenant_id=repository, name=name)
            for name in ("Longsword", "Dagger", "Orc", "Goblin")
        }
        session.add_all([group, *entities.values()])
        await session.flush()
        strength = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Strength",
            value_type=StatValueType.INT,
        )
        mood = StatDefinition(
            tenant_id=repository, stat_group_id=group.id, name="Mood", value_type=StatValueType.ENUM
        )
        speed = StatDefinition(
            tenant_id=repository, stat_group_id=group.id, name="Speed", value_type=StatValueType.INT
        )
        session.add_all([strength, mood, speed])
        await session.flush()
        longsword, dagger = entities["Longsword"].id, entities["Dagger"].id
        session.add_all(
            [
                Item(entity_id=longsword, tenant_id=repository),
                Item(entity_id=dagger, tenant_id=repository),
                EntitySlug(entity_id=longsword, tenant_id=repository, slug="longsword"),
                EntityStatGroup(entity_id=longsword, stat_group_id=group.id, tenant_id=repository),
                EntityStat(
                    entity_id=longsword,
                    stat_definition_id=strength.id,
                    tenant_id=repository,
                    value_int=10,
                ),
                EntityPrototype(entity_id=dagger, prototype_id=longsword, tenant_id=repository),
                StatDefinitionEnumValue(
                    tenant_id=repository, stat_definition_id=mood.id, value="calm"
                ),
            ]
        )
        await session.commit()
        ids = {name: e.id for name, e in entities.items()} | {
            "Abilities": group.id,
            "Strength": strength.id,
            "Mood": mood.id,
            "Speed": speed.id,
        }
    assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
    copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
    assert copied.status_code == 201, copied.text
    return _World(author, gm, repository, table, ids)


async def _local(world: _World) -> dict[str, uuid.UUID]:
    """Source id -> the table's copy of it."""
    async with admin_session_factory() as session:
        return {
            source: local
            for source, local in await session.execute(
                select(
                    RepositoryCopyLinkEntity.source_id, RepositoryCopyLinkEntity.entity_id
                ).where(RepositoryCopyLinkEntity.tenant_id == world.table)
            )
            if local is not None
        }


async def _edit(world: _World) -> uuid.UUID:
    """Upstream and local edits covering every kind of change. Returns the
    id of the entity added upstream."""
    ids, r = world.ids, world.repository
    local = await _local(world)
    async with admin_session_factory() as session:
        # Upstream: a stat value (clean), a rename (conflicts below), a
        # prototype swapped for a new entity, a group's priority, a new enum
        # value, a value type (never applied), and a deletion.
        blade = Entity(tenant_id=r, name="Blade")
        session.add(blade)
        await session.flush()
        stat = await session.get_one(EntityStat, (ids["Longsword"], ids["Strength"]))
        stat.value_int = 12
        (await session.get_one(Entity, ids["Longsword"])).name = "Long Sword"
        await session.execute(
            delete(EntityPrototype).where(EntityPrototype.entity_id == ids["Dagger"])
        )
        session.add(EntityPrototype(entity_id=ids["Dagger"], prototype_id=blade.id, tenant_id=r))
        (await session.get_one(StatGroup, ids["Abilities"])).priority = 5
        session.add(
            StatDefinitionEnumValue(tenant_id=r, stat_definition_id=ids["Mood"], value="joyful")
        )
        (await session.get_one(StatDefinition, ids["Speed"])).value_type = StatValueType.FLOAT
        await session.delete(await session.get_one(Entity, ids["Orc"]))
        # Locally: the table renames its Longsword, and deletes its Goblin.
        (await session.get_one(Entity, local[ids["Longsword"]])).name = "My Longsword"
        await session.delete(await session.get_one(Entity, local[ids["Goblin"]]))
        await session.commit()
        return blade.id


def _by_row(updates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["name"]: {f["field"]: f for f in row["fields"]} for row in updates["changed"]}


async def test_finding_and_applying_updates(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids, gm, url = world.ids, world.gm, f"/tenants/{world.table}/repositories/{world.repository}"
    try:
        # Nothing changed yet.
        untouched = (await gm.get(f"{url}/updates")).json()
        assert (untouched["changed"], untouched["removed"], untouched["added"]) == ([], [], [])

        blade = await _edit(world)
        updates = (await gm.get(f"{url}/updates")).json()
        rows = _by_row(updates)

        longsword = rows["My Longsword"]
        assert longsword["name"]["state"] == "conflict"
        assert (longsword["name"]["base"], longsword["name"]["upstream"]) == (
            "Longsword",
            "Long Sword",
        )
        strength = longsword[f"stats:{ids['Strength']}"]
        assert (strength["state"], strength["label"], strength["upstream"]) == (
            "clean",
            "Strength",
            12,
        )

        prototypes = rows["Dagger"]["prototypes"]
        assert prototypes["added"] == [str(blade)]
        assert prototypes["removed"] == [str(ids["Longsword"])]
        assert rows["Abilities"]["priority"]["upstream"] == 5
        assert rows["Mood"]["enum_values"]["added"] == ["joyful"]
        assert rows["Speed"]["value_type"]["state"] == "not_applicable"
        assert [r["name"] for r in updates["removed"]] == ["Orc"]
        assert [r["name"] for r in updates["deleted_locally"]] == ["Goblin"]
        assert [(a["kind"], a["name"]) for a in updates["added"]] == [("entity", "Blade")]

        def action(kind: str, source: uuid.UUID, verb: str, **extra: Any) -> dict[str, Any]:
            return {"kind": kind, "source_id": str(source), "action": verb, **extra}

        actions = [
            action("entity", ids["Longsword"], "apply"),
            action("entity", ids["Dagger"], "apply"),
            action("stat_group", ids["Abilities"], "apply"),
            action("stat_definition", ids["Mood"], "apply"),
            action("stat_definition", ids["Speed"], "apply"),
            action("entity", ids["Orc"], "detach"),
            action("entity", blade, "add"),
        ]
        unnamed = await gm.post(f"{url}/updates", json={"actions": actions})
        assert unnamed.status_code == 409
        assert unnamed.json()["type"] == "repository-update-needs-choices"
        assert unnamed.json()["conflicts"] == [
            {"kind": "entity", "source_id": str(ids["Longsword"]), "field": "name"}
        ]

        actions[0]["keep_local"] = ["name"]
        applied = await gm.post(f"{url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert applied.json() == {
            "dry_run": False,
            "applied": 5,
            "added": 1,
            "detached": 1,
            "not_applied": [],
        }

        local = await _local(world)
        sword = (await gm.get(f"/tenants/{world.table}/entities/{local[ids['Longsword']]}")).json()
        assert sword["name"] == "My Longsword"
        assert {s["name"]: s["value"] for s in sword["stats"]} == {"Strength": 12}
        dagger = (await gm.get(f"/tenants/{world.table}/entities/{local[ids['Dagger']]}")).json()
        assert [p["id"] for p in dagger["prototypes"]] == [str(local[blade])]
        async with admin_session_factory() as session:
            group = (
                await session.scalars(select(StatGroup).where(StatGroup.tenant_id == world.table))
            ).one()
            assert group.priority == 5
            vocabulary = set(
                await session.scalars(
                    select(StatDefinitionEnumValue.value).where(
                        StatDefinitionEnumValue.tenant_id == world.table
                    )
                )
            )
            assert vocabulary == {"calm", "joyful"}
            speed = (
                await session.scalars(
                    select(StatDefinition.value_type).where(
                        StatDefinition.tenant_id == world.table, StatDefinition.name == "Speed"
                    )
                )
            ).one()
            assert speed is StatValueType.INT  # a value type is changed by hand
            orc_copies = (
                await session.scalars(
                    select(Entity.id).where(Entity.tenant_id == world.table, Entity.name == "Orc")
                )
            ).all()
            assert len(orc_copies) == 1  # detached, never deleted
            copy = await session.get_one(RepositoryCopy, (world.table, world.repository))
            assert copy.synced_at > copy.copied_at
            actions_logged = (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.tenant_id == world.table)
                )
            ).all()
            assert "repository.synced" in actions_logged

        # What's left: only the value type, until someone changes it here.
        after = (await gm.get(f"{url}/updates")).json()
        assert [(r["name"], [f["field"] for f in r["fields"]]) for r in after["changed"]] == [
            ("Speed", ["value_type"])
        ]
        assert (after["removed"], after["added"]) == ([], [])
        async with admin_session_factory() as session:
            local_speed = (
                await session.scalars(
                    select(StatDefinition).where(
                        StatDefinition.tenant_id == world.table, StatDefinition.name == "Speed"
                    )
                )
            ).one()
            local_speed.value_type = StatValueType.FLOAT
            await session.commit()
        assert (await gm.get(f"{url}/updates")).json()["changed"] == []
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])


async def test_updates_need_a_copy_and_a_grant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    other = await world.gm.create_tenant("Another Table")
    try:
        await world.author.put(f"/tenants/{world.repository}/subscribers/{other}")
        not_copied = await world.gm.get(f"/tenants/{other}/repositories/{world.repository}/updates")
        assert not_copied.status_code == 409
        assert not_copied.json()["type"] == "repository-not-copied"

        await world.author.delete(f"/tenants/{world.repository}/subscribers/{world.table}")
        ungranted = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/updates"
        )
        assert ungranted.status_code == 404

        bogus = await world.gm.post(
            f"/tenants/{other}/repositories/{world.repository}/updates",
            json={
                "actions": [{"kind": "entity", "source_id": str(uuid.uuid4()), "action": "apply"}]
            },
        )
        assert bogus.status_code == 409  # not copied there
    finally:
        await cleanup([other, world.table, world.repository], [world.author, world.gm])


async def test_formulas_and_taking_upstream(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A changed formula applies like any other field, and a conflict
    named in take_upstream overwrites the table's own edit."""
    world = await _world(raw_client, fake_jwks_server)
    ids, gm, url = world.ids, world.gm, f"/tenants/{world.table}/repositories/{world.repository}"
    local = await _local(world)
    try:
        async with admin_session_factory() as session:
            # Upstream: Longsword's Speed becomes a formula over Strength,
            # and its Strength a new value the table also changed.
            session.add(
                ComputedStat(
                    entity_id=ids["Longsword"],
                    stat_definition_id=ids["Speed"],
                    tenant_id=world.repository,
                )
            )
            await session.flush()
            session.add(
                ComputedStatLinear(
                    entity_id=ids["Longsword"],
                    stat_definition_id=ids["Speed"],
                    tenant_id=world.repository,
                    source_stat_definition_id=ids["Strength"],
                    multiplier=Decimal(2),
                    offset=Decimal(0),
                    round_mode="none",
                )
            )
            (await session.get_one(EntityStat, (ids["Longsword"], ids["Strength"]))).value_int = 14
            local_strength = (
                await session.scalars(
                    select(EntityStat).where(
                        EntityStat.tenant_id == world.table,
                        EntityStat.entity_id == local[ids["Longsword"]],
                    )
                )
            ).one()
            local_strength.value_int = 11
            await session.commit()

        fields = _by_row((await gm.get(f"{url}/updates")).json())["Longsword"]
        strength = f"stats:{ids['Strength']}"
        assert fields[strength]["state"] == "conflict"
        assert fields[f"formulas:{ids['Speed']}"]["upstream"]["multiplier"] == "2"

        applied = await gm.post(
            f"{url}/updates",
            json={
                "actions": [
                    {
                        "kind": "entity",
                        "source_id": str(ids["Longsword"]),
                        "action": "apply",
                        "take_upstream": [strength],
                    }
                ]
            },
        )
        assert applied.status_code == 200, applied.text
        sword = (await gm.get(f"/tenants/{world.table}/entities/{local[ids['Longsword']]}")).json()
        assert {s["name"]: s["value"] for s in sword["stats"]} == {"Strength": 14, "Speed": 28}
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])


async def test_an_update_that_would_loop_prototypes_is_reported_not_applied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Upstream, Orc starts inheriting from Longsword; locally, the table's
    Longsword already inherits from its Orc. Applying it would close a
    loop: the edge is reported, not stored, and stays on offer."""
    world = await _world(raw_client, fake_jwks_server)
    ids, gm, url = world.ids, world.gm, f"/tenants/{world.table}/repositories/{world.repository}"
    local = await _local(world)
    try:
        async with admin_session_factory() as session:
            session.add(
                EntityPrototype(
                    entity_id=ids["Orc"], prototype_id=ids["Longsword"], tenant_id=world.repository
                )
            )
            session.add(
                EntityPrototype(
                    entity_id=local[ids["Longsword"]],
                    prototype_id=local[ids["Orc"]],
                    tenant_id=world.table,
                )
            )
            await session.commit()
        applied = await gm.post(
            f"{url}/updates",
            json={"actions": [{"kind": "entity", "source_id": str(ids["Orc"]), "action": "apply"}]},
        )
        assert applied.status_code == 200, applied.text
        assert [(n["field"], n["reason"]) for n in applied.json()["not_applied"]] == [
            ("prototypes", "it would make a prototype loop here")
        ]
        still = _by_row((await gm.get(f"{url}/updates")).json())
        assert "prototypes" in still["Orc"]
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])
