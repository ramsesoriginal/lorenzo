"""ADR 0119 (copying a repository) and ADR 0120 (bridges), through the
real HTTP API. Repository content is authored straight into the database,
as a repository's own authors would through the ordinary routes; every
copy goes through the API.
"""

import uuid
from decimal import Decimal
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from httpx import AsyncClient
from sqlalchemy import func, select

from lorenzo_api.models import (
    AuditLog,
    ComputedStat,
    ComputedStatLinear,
    ContentReference,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)


async def _share(author: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await author.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200


async def _count(model: Any, tenant_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return (
            await session.execute(
                select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
            )
        ).scalar_one()


async def _entity_ids(tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    async with admin_session_factory() as session:
        return {
            name: entity_id
            for entity_id, name in await session.execute(
                select(Entity.id, Entity.name).where(Entity.tenant_id == tenant_id)
            )
        }


async def test_copying_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, faerun)
        await session.commit()
    try:
        await _share(author, faerun, table)

        plan = (await gm.get(f"/tenants/{table}/repositories/{faerun}/copy-plan")).json()
        assert plan["collisions"] == []
        (step,) = plan["steps"]
        assert (step["entities"], step["stat_groups"], step["stat_definitions"]) == (5, 1, 4)
        assert (step["granted"], step["published"], step["already_copied"]) == (True, True, False)

        copied = await gm.post(f"/tenants/{table}/repositories/{faerun}/copy")
        assert copied.status_code == 201, copied.text
        assert copied.json()["steps"][0]["dropped"] == []

        # The copy is the tenant's own, ordinary data now: every table,
        # fresh ids, nothing pointing at the repository.
        mine = await _entity_ids(table)
        theirs = await _entity_ids(faerun)
        assert set(mine) == set(theirs)
        assert not set(mine.values()) & set(theirs.values())
        for model in (EntityPrototype, EntityStat, StatDefinition, ContentReference):
            assert await _count(model, table) == await _count(model, faerun), model

        # Stats resolve locally, formulas included: floor(16 * 0.5 - 5) = 3.
        sword = (await gm.get(f"/tenants/{table}/entities/{mine['Sword']}")).json()
        stats = {s["name"]: s["value"] for s in sword["stats"]}
        assert stats == {"Strength": 16, "Modifier": 3, "Strong": True}
        blade = (await gm.get(f"/tenants/{table}/entities/{mine['Blade']}")).json()
        assert [p["id"] for p in blade["prototypes"]] == [str(mine["Sword"])]
        assert blade["parent"]["id"] == str(mine["Chest"])

        # What was recorded: one link per copied row, with its origin and a
        # snapshot in origin ids, and the copy itself.
        async with admin_session_factory() as session:
            links = (
                await session.scalars(
                    select(RepositoryCopyLinkEntity).where(
                        RepositoryCopyLinkEntity.tenant_id == table
                    )
                )
            ).all()
            by_source = {link.source_id: link for link in links}
            assert set(by_source) == set(theirs.values())
            blade_link = by_source[theirs["Blade"]]
            assert blade_link.entity_id == mine["Blade"]
            assert blade_link.source_tenant_id == faerun
            assert blade_link.snapshot["prototypes"] == [str(theirs["Sword"])]
            modes = set(
                await session.scalars(
                    select(RepositoryCopyLinkStatDefinition.mode).where(
                        RepositoryCopyLinkStatDefinition.tenant_id == table
                    )
                )
            )
            assert modes == {"copied"}
            copy = await session.get_one(RepositoryCopy, (table, faerun))
            assert copy.copied_by == gm.user_id
            actions = (
                await session.scalars(select(AuditLog.action).where(AuditLog.tenant_id == table))
            ).all()
        assert actions == ["repository.copied"]

        listed = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert listed[0]["copied_at"] is not None

        again = await gm.post(f"/tenants/{table}/repositories/{faerun}/copy")
        assert again.status_code == 409
        assert again.json()["type"] == "repository-already-copied"

        # The copy doesn't depend on the repository any more: not on the
        # grant, and not on the repository existing at all.
        await author.delete(f"/tenants/{faerun}/subscribers/{table}")
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Tenant, faerun))
            await session.commit()
        sword = (await gm.get(f"/tenants/{table}/entities/{mine['Sword']}")).json()
        assert {s["name"]: s["value"] for s in sword["stats"]}["Modifier"] == 3
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_collisions_need_a_choice(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, faerun)
        # The table already has its own Abilities/Strength, and a slug the
        # repository uses.
        repository_slug = (
            await session.scalars(select(EntitySlug.slug).where(EntitySlug.tenant_id == faerun))
        ).one()
        own_group = StatGroup(tenant_id=table, name="Abilities")
        session.add(own_group)
        await session.flush()
        own_strength = StatDefinition(
            tenant_id=table,
            stat_group_id=own_group.id,
            name="Strength",
            value_type=StatValueType.INT,
        )
        own_entity = Entity(tenant_id=table, name="Longsword")
        session.add_all([own_strength, own_entity])
        await session.flush()
        session.add(EntitySlug(entity_id=own_entity.id, tenant_id=table, slug=repository_slug))
        await session.commit()
        own_group_id, own_strength_id = own_group.id, own_strength.id
    try:
        await _share(author, faerun, table)
        plan = (await gm.get(f"/tenants/{table}/repositories/{faerun}/copy-plan")).json()
        collisions = {(c["kind"], c["name"]): c for c in plan["collisions"]}
        assert set(collisions) == {
            ("stat_group", "Abilities"),
            ("stat_definition", "Strength"),
            ("slug", repository_slug),
        }
        assert collisions[("stat_group", "Abilities")]["choices"] == ["rename", "merge", "skip"]
        assert collisions[("stat_definition", "Strength")]["choices"] == ["rename", "merge", "skip"]
        assert collisions[("slug", repository_slug)]["choices"] == ["rename", "skip"]

        refused = await gm.post(f"/tenants/{table}/repositories/{faerun}/copy")
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-needs-choices"
        assert len(refused.json()["collisions"]) == 3

        group = collisions[("stat_group", "Abilities")]["source_id"]
        strength = collisions[("stat_definition", "Strength")]["source_id"]
        slug = collisions[("slug", repository_slug)]["source_id"]
        impossible = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/copy",
            json={
                "resolutions": [
                    {
                        "kind": "stat_group",
                        "source_id": group,
                        "action": "rename",
                        "name": "Abilities",
                    },
                    {"kind": "stat_definition", "source_id": strength, "action": "merge"},
                    {"kind": "slug", "source_id": slug, "action": "skip"},
                ]
            },
        )
        assert impossible.status_code == 422
        assert impossible.json()["type"] == "invalid-repository-copy-choice"

        copied = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/copy",
            json={
                "resolutions": [
                    {"kind": "stat_group", "source_id": group, "action": "merge"},
                    {"kind": "stat_definition", "source_id": strength, "action": "merge"},
                    {"kind": "slug", "source_id": slug, "action": "rename", "name": "faerun-sword"},
                ]
            },
        )
        assert copied.status_code == 201, copied.text

        async with admin_session_factory() as session:
            groups = (
                await session.scalars(select(StatGroup.id).where(StatGroup.tenant_id == table))
            ).all()
            assert groups == [own_group_id]
            definitions = {
                name: (def_id, group_id)
                for def_id, name, group_id in await session.execute(
                    select(
                        StatDefinition.id, StatDefinition.name, StatDefinition.stat_group_id
                    ).where(StatDefinition.tenant_id == table)
                )
            }
            assert definitions["Strength"] == (own_strength_id, own_group_id)
            assert {n for n, (_, g) in definitions.items() if g == own_group_id} == {
                "Strength",
                "Modifier",
                "Strong",
                "Alignment",
            }
            strength_values = (
                await session.scalars(
                    select(EntityStat.value_int).where(
                        EntityStat.tenant_id == table,
                        EntityStat.stat_definition_id == own_strength_id,
                    )
                )
            ).all()
            assert strength_values == [16]
            slugs = set(
                await session.scalars(select(EntitySlug.slug).where(EntitySlug.tenant_id == table))
            )
            assert slugs == {repository_slug, "faerun-sword"}
            group_modes = set(
                await session.scalars(
                    select(RepositoryCopyLinkStatGroup.mode).where(
                        RepositoryCopyLinkStatGroup.tenant_id == table
                    )
                )
            )
            assert group_modes == {"merged"}
            entity_groups = (
                await session.scalars(
                    select(EntityStatGroup.stat_group_id).where(EntityStatGroup.tenant_id == table)
                )
            ).all()
            assert entity_groups == [own_group_id]
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_skipping_drops_what_depends_on_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, faerun)
        group = StatGroup(tenant_id=table, name="Abilities")
        session.add(group)
        await session.commit()
    try:
        await _share(author, faerun, table)
        plan = (await gm.get(f"/tenants/{table}/repositories/{faerun}/copy-plan")).json()
        (collision,) = plan["collisions"]
        copied = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/copy",
            json={
                "resolutions": [
                    {"kind": "stat_group", "source_id": collision["source_id"], "action": "skip"}
                ]
            },
        )
        assert copied.status_code == 201, copied.text
        dropped = {d["kind"] for d in copied.json()["steps"][0]["dropped"]}
        # Skipping the group skips its definitions, and with them every
        # value, formula, and attachment that used them.
        assert dropped == {"stat_definition", "entity_stat", "computed_stat", "entity_stat_group"}
        assert copied.json()["steps"][0]["stat_definitions"] == 0
        assert await _count(StatDefinition, table) == 0
        assert await _count(Entity, table) == 5
    finally:
        await cleanup([table, faerun], [author, gm])


async def _author_bridge_world(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> tuple[Actor, Actor, Actor, uuid.UUID, uuid.UUID, uuid.UUID]:
    """D&D 5e (a system), Faerûn (a setting), and dnd_faerun (a bridge that
    copied both and joins them), each run by its own author."""
    wotc = await make_actor(raw_client, fake_jwks_server, "wotc")
    ed = await make_actor(raw_client, fake_jwks_server, "ed")
    bridger = await make_actor(raw_client, fake_jwks_server, "bridger")
    dnd = await wotc.create_tenant("D&D 5e", kind="repository")
    faerun = await ed.create_tenant("Faerûn", kind="repository")
    bridge = await bridger.create_tenant("dnd_faerun", kind="repository")
    async with admin_session_factory() as session:
        abilities = StatGroup(tenant_id=dnd, name="Abilities")
        staff = Entity(tenant_id=dnd, name="Staff")
        blackstaff = Entity(tenant_id=faerun, name="Blackstaff")
        session.add_all([abilities, staff, blackstaff])
        await session.flush()
        session.add(
            StatDefinition(
                tenant_id=dnd,
                stat_group_id=abilities.id,
                name="Strength",
                value_type=StatValueType.INT,
            )
        )
        session.add(EntityStatGroup(entity_id=staff.id, stat_group_id=abilities.id, tenant_id=dnd))
        await session.commit()
    await _share(wotc, dnd, bridge)
    await _share(ed, faerun, bridge)
    for repository in (dnd, faerun):
        response = await bridger.post(f"/tenants/{bridge}/repositories/{repository}/copy")
        assert response.status_code == 201, response.text
    # The bridge's own work: an entity joining its copies of both, with a
    # stat from the system. And an edit to its copy of Blackstaff, which
    # must not travel downstream.
    bridge_ids = await _entity_ids(bridge)
    async with admin_session_factory() as session:
        strength = (
            await session.scalars(
                select(StatDefinition.id).where(StatDefinition.tenant_id == bridge)
            )
        ).one()
        joined = Entity(tenant_id=bridge, name="Blackstaff (D&D 5e)")
        session.add(joined)
        await session.flush()
        session.add_all(
            [
                EntityPrototype(
                    entity_id=joined.id, prototype_id=bridge_ids["Blackstaff"], tenant_id=bridge
                ),
                EntityPrototype(
                    entity_id=joined.id, prototype_id=bridge_ids["Staff"], tenant_id=bridge
                ),
                EntityStat(
                    entity_id=joined.id, stat_definition_id=strength, tenant_id=bridge, value_int=10
                ),
            ]
        )
        (await session.get_one(Entity, bridge_ids["Blackstaff"])).name = "Blackstaff (edited)"
        await session.commit()
    await bridger.put(f"/tenants/{bridge}/published")
    return wotc, ed, bridger, dnd, faerun, bridge


async def test_copying_a_bridge_brings_its_dependencies(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    wotc, ed, bridger, dnd, faerun, bridge = await _author_bridge_world(
        raw_client, fake_jwks_server
    )
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("My Table")
    try:
        await bridger.put(f"/tenants/{bridge}/subscribers/{table}")
        plan = (await gm.get(f"/tenants/{table}/repositories/{bridge}/copy-plan")).json()
        assert [s["name"] for s in plan["steps"]][-1] == "dnd_faerun"
        assert {s["name"] for s in plan["steps"][:-1]} == {"D&D 5e", "Faerûn"}
        assert [s["granted"] for s in plan["steps"]] == [False, False, True]

        refused = await gm.post(f"/tenants/{table}/repositories/{bridge}/copy")
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-needs-grants"
        assert {m["name"] for m in refused.json()["missing"]} == {"D&D 5e", "Faerûn"}

        await wotc.put(f"/tenants/{dnd}/subscribers/{table}")
        await ed.put(f"/tenants/{faerun}/subscribers/{table}")
        copied = await gm.post(f"/tenants/{table}/repositories/{bridge}/copy")
        assert copied.status_code == 201, copied.text
        assert [s["entities"] for s in copied.json()["steps"]][-1] == 1

        mine = await _entity_ids(table)
        # Blackstaff comes from Faerûn itself, not the bridge's edited copy.
        assert set(mine) == {"Staff", "Blackstaff", "Blackstaff (D&D 5e)"}
        joined = (await gm.get(f"/tenants/{table}/entities/{mine['Blackstaff (D&D 5e)']}")).json()
        assert {p["id"] for p in joined["prototypes"]} == {
            str(mine["Staff"]),
            str(mine["Blackstaff"]),
        }
        assert {s["name"]: s["value"] for s in joined["stats"]} == {"Strength": 10}
        async with admin_session_factory() as session:
            copies = set(
                await session.scalars(
                    select(RepositoryCopy.repository_tenant_id).where(
                        RepositoryCopy.tenant_id == table
                    )
                )
            )
        assert copies == {dnd, faerun, bridge}
    finally:
        await cleanup([table, bridge, faerun, dnd], [wotc, ed, bridger, gm])


async def test_a_bridge_reuses_dependencies_already_copied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    wotc, ed, bridger, dnd, faerun, bridge = await _author_bridge_world(
        raw_client, fake_jwks_server
    )
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("My Table")
    try:
        await wotc.put(f"/tenants/{dnd}/subscribers/{table}")
        await ed.put(f"/tenants/{faerun}/subscribers/{table}")
        await bridger.put(f"/tenants/{bridge}/subscribers/{table}")
        for repository in (dnd, faerun):
            assert (
                await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
            ).status_code == 201
        before = await _entity_ids(table)

        plan = (await gm.get(f"/tenants/{table}/repositories/{bridge}/copy-plan")).json()
        assert [s["already_copied"] for s in plan["steps"]] == [True, True, False]
        copied = await gm.post(f"/tenants/{table}/repositories/{bridge}/copy")
        assert copied.status_code == 201, copied.text
        assert [s["name"] for s in copied.json()["steps"]] == ["dnd_faerun"]

        after = await _entity_ids(table)
        assert {k: v for k, v in after.items() if k in before} == before
        joined = (await gm.get(f"/tenants/{table}/entities/{after['Blackstaff (D&D 5e)']}")).json()
        assert {p["id"] for p in joined["prototypes"]} == {
            str(before["Staff"]),
            str(before["Blackstaff"]),
        }
    finally:
        await cleanup([table, bridge, faerun, dnd], [wotc, ed, bridger, gm])


async def test_a_merge_that_would_loop_formulas_copies_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The table's Alpha reads Beta; the repository's Beta reads Alpha.
    Merging both definitions would close a loop (ADR 0104), so the copy is
    refused whole."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")

    async def formula(tenant: uuid.UUID, target: str, source: str) -> None:
        async with admin_session_factory() as session:
            group = StatGroup(tenant_id=tenant, name="Numbers")
            entity = Entity(tenant_id=tenant, name="Thing")
            session.add_all([group, entity])
            await session.flush()
            defs = {
                name: StatDefinition(
                    tenant_id=tenant,
                    stat_group_id=group.id,
                    name=name,
                    value_type=StatValueType.INT,
                )
                for name in ("Alpha", "Beta")
            }
            session.add_all(defs.values())
            await session.flush()
            key = {
                "entity_id": entity.id,
                "stat_definition_id": defs[target].id,
                "tenant_id": tenant,
            }
            session.add(ComputedStat(**key))
            await session.flush()
            session.add(
                ComputedStatLinear(
                    **key,
                    source_stat_definition_id=defs[source].id,
                    multiplier=Decimal(1),
                    offset=Decimal(0),
                    round_mode="none",
                )
            )
            await session.commit()

    await formula(table, "Alpha", "Beta")
    await formula(faerun, "Beta", "Alpha")
    try:
        await _share(author, faerun, table)
        plan = (await gm.get(f"/tenants/{table}/repositories/{faerun}/copy-plan")).json()
        resolutions = [
            {"kind": c["kind"], "source_id": c["source_id"], "action": "merge"}
            for c in plan["collisions"]
        ]
        refused = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/copy", json={"resolutions": resolutions}
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-formula-cycle"
        assert await _count(Entity, table) == 1
        assert await _count(RepositoryCopy, table) == 0
    finally:
        await cleanup([table, faerun], [author, gm])
