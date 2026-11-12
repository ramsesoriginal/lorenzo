"""ADR 0453: a repository carries game systems, templates and the system of a stat group; a copy
joins a system by slug, re-points a template, leaves out what it cannot show, and reports a merge
that keeps the library's unit; a profile and Discover list the systems a release carries.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from httpx import AsyncClient
from sqlalchemy import select, update
from test_discover import _Shelf, _visitor

from lorenzo_api.models import (
    Entity,
    RepositoryProfile,
    StatDefinition,
    StatGroup,
    StatValueType,
    System,
    Template,
    TemplateSlot,
    TemplateSlotExclusion,
    TemplateSlotStat,
)


async def _share(author: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await author.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200


async def _repository_with_a_system(author: Actor, name: str = "Draw Steel Core") -> uuid.UUID:
    """A repository holding everything, whose one stat group belongs to the system `fx`, which is
    rooted at the Sword."""
    repository = await author.create_tenant(name, kind="repository")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, repository)
        system = await session.scalar(select(System).where(System.tenant_id == repository))
        sword = await session.scalar(
            select(Entity.id).where(Entity.tenant_id == repository, Entity.name == "Sword")
        )
        assert system is not None
        system.root_entry_id = sword
        await session.execute(
            update(StatGroup).where(StatGroup.tenant_id == repository).values(system_id=system.id)
        )
        await session.commit()
    return repository


async def _rows(model: Any, tenant_id: uuid.UUID) -> list[Any]:
    async with admin_session_factory() as session:
        return list(await session.scalars(select(model).where(model.tenant_id == tenant_id)))


async def test_a_copy_brings_the_system_the_groups_and_the_template(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        await _share(author, repository, table)

        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
        (step,) = copied.json()["steps"]
        assert (step["systems"], step["templates"], step["dropped"]) == (1, 1, [])

        (system,) = await _rows(System, table)
        (group,) = await _rows(StatGroup, table)
        (template,) = await _rows(Template, table)
        names = {e.id: e.name for e in await _rows(Entity, table)}
        assert (system.slug, system.name) == ("fx", "Fixture system")
        assert names[system.root_entry_id] == "Sword"
        assert group.system_id == system.id
        assert (template.name, template.required_kind) == ("Fixture template", "item")
        assert names[template.required_ancestor_entry_id] == "Sword"
        slots = sorted(await _rows(TemplateSlot, table), key=lambda s: s.position)
        assert [s.kind for s in slots] == ["stats", "held"]
        assert slots[0].stat_group_id == group.id and slots[1].held_order == "name"
        stats = {d.id: d.name for d in await _rows(StatDefinition, table)}
        (listed,) = await _rows(TemplateSlotStat, table)
        (left_out,) = await _rows(TemplateSlotExclusion, table)
        assert (stats[listed.stat_definition_id], listed.label) == ("Strength", "Str")
        assert stats[left_out.stat_definition_id] == "Modifier"
        # The library's own authoring read has it, and its system by slug.
        read = await gm.get(f"/tenants/{table}/templates/{template.id}")
        assert read.status_code == 200, read.text
        assert [s["kind"] for s in read.json()["slots"]] == ["stats", "held"]
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_system_the_library_has_is_joined_by_slug_and_keeps_its_name(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        own = await gm.post(f"/tenants/{table}/systems", json={"slug": "fx", "name": "Mine"})
        assert own.status_code == 201, own.text
        await _share(author, repository, table)

        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")

        assert copied.status_code == 201, copied.text
        assert copied.json()["steps"][0]["systems"] == 0
        (system,) = await _rows(System, table)
        (group,) = await _rows(StatGroup, table)
        assert (str(system.id), system.name, system.root_entry_id) == (
            own.json()["id"],
            "Mine",
            None,
        )
        assert group.system_id == system.id
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_template_of_a_name_the_library_has_is_left_out_and_said(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        mine = await gm.post(f"/tenants/{table}/templates", json={"name": "Fixture template"})
        assert mine.status_code == 201, mine.text
        await _share(author, repository, table)

        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")

        assert copied.status_code == 201, copied.text
        (step,) = copied.json()["steps"]
        assert step["templates"] == 0
        (dropped,) = step["dropped"]
        assert dropped["kind"] == "template"
        assert "already has a template" in dropped["reason"]
        assert [t.id for t in await _rows(Template, table)] == [uuid.UUID(mine.json()["id"])]
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_template_whose_group_was_skipped_is_left_out(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        group = await gm.post(f"/tenants/{table}/stat-groups", json={"name": "Abilities"})
        assert group.status_code == 201, group.text
        await _share(author, repository, table)
        plan = (await gm.get(f"/tenants/{table}/repositories/{repository}/copy-plan")).json()
        resolutions = [
            {"kind": c["kind"], "source_id": c["source_id"], "action": "skip"}
            for c in plan["collisions"]
        ]

        copied = await gm.post(
            f"/tenants/{table}/repositories/{repository}/copy", json={"resolutions": resolutions}
        )

        assert copied.status_code == 201, copied.text
        (step,) = copied.json()["steps"]
        assert step["templates"] == 0
        assert any(
            d["kind"] == "template" and "wasn't copied" in d["reason"] for d in step["dropped"]
        )
        assert await _rows(Template, table) == []
    finally:
        await cleanup([repository, table], [author, gm])


# --- units and bounds ---------------------------------------------------------------------------


async def _library_with_a_strength_in_kilograms(gm: Actor, table: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=table, name="Abilities")
        session.add(group)
        await session.flush()
        session.add(
            StatDefinition(
                tenant_id=table,
                stat_group_id=group.id,
                name="Strength",
                value_type=StatValueType.INT,
                unit="kg",
            )
        )
        await session.commit()


def _merging(plan: dict) -> list[dict]:
    return [
        {"kind": c["kind"], "source_id": c["source_id"], "action": "merge"}
        for c in plan["collisions"]
    ]


async def test_a_merge_that_keeps_the_librarys_unit_is_reported(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        async with admin_session_factory() as session:
            await session.execute(
                update(StatDefinition)
                .where(StatDefinition.tenant_id == repository, StatDefinition.name == "Strength")
                .values(unit="lb", min_value=0)
            )
            await session.commit()
        await _library_with_a_strength_in_kilograms(gm, table)
        await _share(author, repository, table)
        base = f"/tenants/{table}/repositories/{repository}"
        plan = (await gm.get(f"{base}/copy-plan")).json()

        copied = await gm.post(f"{base}/copy", json={"resolutions": _merging(plan)})

        assert copied.status_code == 201, copied.text
        (warning,) = copied.json()["warnings"]
        assert warning["kind"] == "scale" and warning["name"] == "Strength"
        assert warning["library"] == {"unit": "kg", "min_value": None, "max_value": None}
        assert warning["incoming"] == {"unit": "lb", "min_value": 0.0, "max_value": None}
        assert (await gm.get(f"{base}/copy-plan")).status_code == 200
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_plan_with_strict_units_does_not_offer_to_merge_what_differs(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        await _library_with_a_strength_in_kilograms(gm, table)
        await _share(author, repository, table)
        base = f"/tenants/{table}/repositories/{repository}"

        loose = (await gm.get(f"{base}/copy-plan")).json()
        strict = (await gm.get(f"{base}/copy-plan", params={"strict_units": "true"})).json()
        refused = await gm.post(
            f"{base}/copy",
            json={"resolutions": _merging(loose), "strict_units": True},
        )

        def choices(plan: dict) -> list[str]:
            (collision,) = (c for c in plan["collisions"] if c["kind"] == "stat_definition")
            return collision["choices"]

        assert "merge" in choices(loose)
        assert choices(strict) == ["rename", "skip"]
        assert refused.status_code == 422, refused.text
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_merge_of_the_same_unit_is_not_a_warning(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await _repository_with_a_system(author)
    table = await gm.create_tenant("My Table")
    try:
        async with admin_session_factory() as session:
            await session.execute(
                update(StatDefinition)
                .where(StatDefinition.tenant_id == repository, StatDefinition.name == "Strength")
                .values(unit="kg")
            )
            await session.commit()
        await _library_with_a_strength_in_kilograms(gm, table)
        await _share(author, repository, table)
        base = f"/tenants/{table}/repositories/{repository}"
        plan = (await gm.get(f"{base}/copy-plan", params={"strict_units": "true"})).json()

        copied = await gm.post(
            f"{base}/copy", json={"resolutions": _merging(plan), "strict_units": True}
        )

        assert copied.status_code == 201, copied.text
        assert copied.json()["warnings"] == []
    finally:
        await cleanup([repository, table], [author, gm])


# --- what a listing says ---


async def test_a_published_release_lists_its_systems_on_the_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    repository = await _repository_with_a_system(author)
    try:
        assert (await author.put(f"/tenants/{repository}/published")).status_code == 200

        profile = (await author.get(f"/tenants/{repository}/profile")).json()

        assert profile["systems"] == ["fx"]
        async with admin_session_factory() as session:
            stored = await session.get(RepositoryProfile, repository)
            assert stored is not None and stored.systems == ["fx"]
    finally:
        await cleanup([repository], [author])


async def test_discover_filters_and_counts_by_the_systems_a_release_carries(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        both = await shelf.add("Bundle", system="Bundle label")
        steel = await shelf.add("Steel", system="DS")
        await shelf.add("Plain")
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryProfile)
                .where(RepositoryProfile.tenant_id == both)
                .values(systems=["ds", "pf"])
            )
            await session.execute(
                update(RepositoryProfile)
                .where(RepositoryProfile.tenant_id == steel)
                .values(systems=["ds"])
            )
            await session.commit()

        def names(body: dict) -> list[str]:
            return sorted(i["name"].removesuffix(f" {shelf.word}") for i in body["items"])

        params = {"q": shelf.word}
        ds = (await visitor.get("/discover/repositories", params=params | {"system": "ds"})).json()
        pf = (await visitor.get("/discover/repositories", params=params | {"system": "PF"})).json()
        label = (
            await visitor.get("/discover/repositories", params=params | {"system": "bundle label"})
        ).json()
        facets = (await visitor.get("/discover/facets")).json()
        item = next(i for i in ds["items"] if i["name"].startswith("Bundle"))

        assert names(ds) == ["Bundle", "Steel"]
        assert names(pf) == ["Bundle"]
        assert names(label) == ["Bundle"]
        assert item["systems"] == ["ds", "pf"]
        counted = {f["value"]: f["count"] for f in facets["systems"]}
        assert counted["ds"] >= 2 and counted["pf"] >= 1
    finally:
        await shelf.done()
        await cleanup([], [visitor])
