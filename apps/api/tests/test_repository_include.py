"""ADR 0431, RFC 0051 H1: a repository includes one it is built on in its release.

The repository authored here is the one of the release tests (Armoury: Longsword, Dagger, Orc,
a stat group, stats and a formula), as the source A. B is a bridge that copied A, put an item of
its own on top of A's Longsword, changed A's Strength in its copy and deleted its Orc. Everything
is authored straight into the database, as its authors would through the ordinary routes; every
flip, release, copy and update goes through the HTTP API.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _author_world import add_member
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    EntityStat,
    Item,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryProfile,
    RepositoryRelease,
    RepositoryReleasedRow,
)
from lorenzo_api.release_document import FORMAT
from lorenzo_api.release_document_store import read_release_content
from lorenzo_api.repository_content import Content

LICENCE = {"label": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


@dataclass
class W:
    """A is `base.repository`, private, with `base.author` its Owner. `b` is a bridge that
    copied it; `ids` are b's ids by name, its copies of A's rows and its own."""

    base: ReleaseWorld
    b: uuid.UUID
    ids: dict[str, uuid.UUID]
    tenants: list[uuid.UUID] = field(default_factory=list)
    actors: list[Actor] = field(default_factory=list)

    @property
    def a(self) -> uuid.UUID:
        return self.base.repository

    @property
    def author(self) -> Actor:
        return self.base.author

    async def done(self) -> None:
        await cleanup(
            [self.base.table, self.base.repository, self.b, *self.tenants],
            [self.base.author, self.base.gm, *self.actors],
        )


async def _names(tenant: uuid.UUID) -> dict[str, uuid.UUID]:
    async with admin_session_factory() as session:
        return {
            name: entity_id
            for entity_id, name in await session.execute(
                select(Entity.id, Entity.name).where(Entity.tenant_id == tenant)
            )
        }


async def _bridge(
    base: ReleaseWorld,
    name: str,
    *,
    owner: Actor | None = None,
    invite: bool = True,
    own: str | None = None,
) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    """A repository `owner` owns, built on A: it copied A, then added an item of its own on top of
    A's Longsword (`own`, "Bridge Blade" by default), changed Strength in its copy to 12 and
    deleted its copy of the Orc. `invite` has A's Owner invite it first."""
    owner = owner or base.author
    b = await owner.create_tenant(name, kind="repository")
    if invite:
        invited = await base.author.put(f"/tenants/{base.repository}/subscribers/{b}")
        assert invited.status_code in (200, 201), invited.text
    copied = await owner.post(f"/tenants/{b}/repositories/{base.repository}/copy", json={})
    assert copied.status_code == 201, copied.text
    ids = await _names(b)
    async with admin_session_factory() as session:
        blade = Entity(tenant_id=b, name=own or "Bridge Blade")
        session.add(blade)
        await session.flush()
        session.add_all(
            [
                Item(entity_id=blade.id, tenant_id=b),
                EntityPrototype(entity_id=blade.id, prototype_id=ids["Longsword"], tenant_id=b),
            ]
        )
        await session.execute(
            update(EntityStat)
            .where(EntityStat.tenant_id == b, EntityStat.entity_id == ids["Longsword"])
            .values(value_int=12)
        )
        await session.execute(delete(Entity).where(Entity.id == ids["Orc"]))
        await session.commit()
        ids[own or "Bridge Blade"] = blade.id
    del ids["Orc"]
    return b, ids


async def _world(raw_client: AsyncClient, jwks: FakeJwksServer) -> W:
    base = await release_world(raw_client, jwks)
    b, ids = await _bridge(base, "Bridge")
    return W(base, b, ids)


async def _include(actor: Actor, b: uuid.UUID, source: uuid.UUID, choice: str = "include") -> Any:
    return await actor.put(
        f"/tenants/{b}/repositories/{source}/inclusion", json={"inclusion": choice}
    )


async def _make_public(actor: Actor, repository: uuid.UUID, **body: Any) -> Any:
    return await actor.put(
        f"/tenants/{repository}/public",
        json={"accept_terms": True, "summary": f"{repository} is public", **body},
    )


async def _document(repository: uuid.UUID, number: int | None = None) -> Content:
    """The content of one of its releases, the newest unless a number is given."""
    async with admin_session_factory() as session:
        stmt = select(RepositoryRelease).where(RepositoryRelease.tenant_id == repository)
        stmt = stmt.where(RepositoryRelease.number == number) if number else stmt
        release = await session.scalar(stmt.order_by(RepositoryRelease.number.desc()).limit(1))
        assert release is not None
        return await read_release_content(session, tenant_id=repository, release_id=release.id)


async def _library(
    raw_client: AsyncClient, jwks: FakeJwksServer, w: W, name: str = "Library"
) -> tuple[Actor, uuid.UUID]:
    """A user with a library and no access to anything."""
    actor = await make_actor(raw_client, jwks, name)
    library = await actor.create_tenant(f"{name}'s table")
    w.actors.append(actor)
    w.tenants.append(library)
    return actor, library


async def _copy(actor: Actor, library: uuid.UUID, repository: uuid.UUID, **body: Any) -> Any:
    return await actor.post(f"/tenants/{library}/repositories/{repository}/copy", json=body or {})


async def _entries(actor: Actor, library: uuid.UUID) -> list[str]:
    response = await actor.get(f"/tenants/{library}/entities", params={"size": 100})
    assert response.status_code == 200, response.text
    return sorted(e["name"] for e in response.json()["items"])


async def _release_notes(w: W) -> list[dict[str, Any]]:
    response = await w.author.get(f"/tenants/{w.b}/releases")
    return response.json()["items"]  # type: ignore[no-any-return]


# --- The release document -----------------------------------------------------------------------


async def test_an_included_source_is_the_repositorys_own_in_its_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        profile = await w.author.patch(f"/tenants/{w.a}/profile", json={"licence": LICENCE})
        assert profile.status_code == 200, profile.text
        async with admin_session_factory() as session:
            links_before = await session.scalar(
                select(func.count())
                .select_from(RepositoryCopyLinkEntity)
                .where(RepositoryCopyLinkEntity.tenant_id == w.b)
            )
        assert links_before and links_before >= 2

        assert (await _include(w.author, w.b, w.a)).status_code == 200
        made = await _make_public(w.author, w.b)
        assert made.status_code == 200, made.text

        document = await _document(w.b)
        # A is not among what it is built on, and not one of its rows is a copy.
        assert document.links.copies == set()
        assert document.links.entity == {} and document.links.origin_tenant == {}
        assert document.links.snapshots == {} and document.links.deleted == {}
        assert sorted(document.entities.values()) == ["Bridge Blade", "Dagger", "Longsword"]
        assert all(document.own("entity", e) for e in document.entities)
        assert all(document.own("stat_group", g) for g in document.groups)
        assert all(document.own("stat_definition", d) for d in document.definitions)
        # B's edit travels: its Longsword, not A's, with Strength 12.
        strengths = {
            document.entities[entity]: value.value_int
            for (entity, definition), value in document.stats.items()
            if document.definitions[definition]["name"] == "Strength"
        }
        assert strengths == {"Longsword": 12}
        # The document says how it carried A, with a snapshot of its name and its licence.
        assert document.sources == {
            w.a: {"inclusion": "include", "name": "Armoury", "licence": LICENCE}
        }
        async with admin_session_factory() as session:
            stored = await session.scalar(
                select(RepositoryRelease.id).where(RepositoryRelease.tenant_id == w.b)
            )
            assert stored is not None
            # B itself is not changed: its copy record and every copy link are still there, and
            # it goes on authoring on top of A.
            copy = await session.get_one(RepositoryCopy, (w.b, w.a))
            assert copy.inclusion == "include"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RepositoryCopyLinkEntity)
                    .where(RepositoryCopyLinkEntity.tenant_id == w.b)
                )
                == links_before
            )
            names = {
                row.name
                for row in await session.scalars(
                    select(RepositoryReleasedRow).where(RepositoryReleasedRow.tenant_id == w.b)
                )
            }
            # The released rows are the flat ones, hashed as B's own and named by B's ids.
            assert {"Longsword", "Dagger", "Abilities", "Strength", "Bridge Blade"} <= names
            released = {
                r.name: r.row_id
                for r in await session.scalars(
                    select(RepositoryReleasedRow).where(
                        RepositoryReleasedRow.tenant_id == w.b,
                        RepositoryReleasedRow.kind == "entity",
                    )
                )
            }
            assert released == {n: w.ids[n] for n in ("Longsword", "Dagger", "Bridge Blade")}

        # The digest is the flat content's: nothing differs from the release just made, and an
        # edit afterwards is seen as a change to one of the rows that came from A.
        preview = await w.author.get(f"/tenants/{w.b}/release-preview")
        assert preview.json()["matches"] is True and preview.json()["differing_rows"] == 0
        async with admin_session_factory() as session:
            await session.execute(
                update(EntityStat)
                .where(EntityStat.tenant_id == w.b, EntityStat.entity_id == w.ids["Longsword"])
                .values(value_int=13)
            )
            await session.commit()
        preview = (await w.author.get(f"/tenants/{w.b}/release-preview")).json()
        assert preview["matches"] is False
        assert [r["name"] for r in preview["changed"]] == ["Longsword"]
        assert preview["breaking"] == []
    finally:
        await w.done()


async def test_the_release_format_is_the_new_one_and_a_private_release_carries_no_sources(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        # A private repository is read live, whole: its release holds no document, its rows are
        # not flattened and the profile has no record of how it carried A.
        assert (await w.author.put(f"/tenants/{w.b}/published")).status_code == 200
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, w.b)
            assert profile.release_sources is None
        assert (await _make_public(w.author, w.b)).status_code == 200
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, w.b)
            assert profile.release_sources == [
                {
                    "id": str(w.a),
                    "name": "Armoury",
                    "inclusion": "include",
                    "licence_label": None,
                    "licence_url": None,
                }
            ]
        assert FORMAT == 48
    finally:
        await w.done()


# --- What a library reads -----------------------------------------------------------------------


async def test_a_library_copying_a_flattened_repository_never_reads_the_source(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        assert (await _make_public(w.author, w.b)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)

        plan = (await reader.get(f"/tenants/{library}/repositories/{w.b}/copy-plan")).json()
        assert [s["name"] for s in plan["steps"]] == ["Bridge"]
        assert plan["collisions"] == []
        dependencies = await reader.get(f"/tenants/{library}/repositories/{w.b}/dependencies")
        assert dependencies.json() == []
        assert (await reader.get(f"/repositories/{w.b}/dependencies")).json() == []

        copied = await _copy(reader, library, w.b)
        assert copied.status_code == 201, copied.text
        assert [s["name"] for s in copied.json()["steps"]] == ["Bridge"]
        # A's rows arrive as the bridge's: B's edit, B's deletion, B's own item.
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword"]
        sword = next(
            e
            for e in (await reader.get(f"/tenants/{library}/entities")).json()["items"]
            if e["name"] == "Longsword"
        )
        detail = (await reader.get(f"/tenants/{library}/entities/{sword['id']}")).json()
        # Strength is B's 12, and the formula that reads it (Damage) came with it.
        assert {s["name"]: s["value"] for s in detail["stats"]} == {"Strength": 12, "Damage": 7}
        held = (await reader.get(f"/tenants/{library}/repositories")).json()["items"]
        assert [r["repository"]["name"] for r in held] == ["Bridge"]
        async with admin_session_factory() as session:
            assert set(
                await session.scalars(
                    select(RepositoryCopy.repository_tenant_id).where(
                        RepositoryCopy.tenant_id == library
                    )
                )
            ) == {w.b}

        # Nothing of A is readable: not by the library, not by a visitor.
        assert (
            await reader.get(f"/tenants/{library}/repositories/{w.a}/entities")
        ).status_code == 404
        assert (
            await reader.get(f"/tenants/{library}/repositories/{w.a}/updates")
        ).status_code == 409
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        w.actors.append(visitor)
        assert (await visitor.get(f"/repositories/{w.a}/entities")).status_code == 404
        assert (await visitor.get(f"/repositories/{w.a}/profile")).status_code == 404
        assert (await visitor.get(f"/discover/repositories/{w.a}")).status_code == 404
        assert (await visitor.get(f"/repositories/{w.b}/entities")).status_code == 200
    finally:
        await w.done()


async def test_a_library_updates_a_flattened_repository_through_the_bridge(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A's changes reach the library by way of B: B takes A's release in its own tenant, releases
    again, and the library, which never saw A, takes the rows as B's."""
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        assert (await _make_public(w.author, w.b)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201

        # A adds a Spear and releases; B (public, including A) cannot release until it takes it.
        async with admin_session_factory() as session:
            spear = Entity(tenant_id=w.a, name="Spear")
            session.add(spear)
            await session.flush()
            session.add(Item(entity_id=spear.id, tenant_id=w.a))
            await session.commit()
            spear_id = spear.id
        await w.base.publish(label="2.0")
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "built-on-behind"
        assert [r["name"] for r in refused.json()["repositories"]] == ["Armoury"]
        taken = await w.author.post(
            f"/tenants/{w.b}/repositories/{w.a}/updates",
            json={"actions": [{"kind": "entity", "source_id": str(spear_id), "action": "add"}]},
        )
        assert taken.status_code == 200, taken.text

        # B also edits an A row of its own in the meantime.
        async with admin_session_factory() as session:
            await session.execute(
                update(EntityStat)
                .where(EntityStat.tenant_id == w.b, EntityStat.entity_id == w.ids["Longsword"])
                .values(value_int=15)
            )
            await session.commit()
        assert (
            await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        ).status_code == 200

        url = f"/tenants/{library}/repositories/{w.b}"
        updates = (await reader.get(f"{url}/updates")).json()
        assert [(a["kind"], a["name"]) for a in updates["added"]] == [("entity", "Spear")]
        assert [r["name"] for r in updates["changed"]] == ["Longsword"]
        assert updates["removed"] == []
        document = await _document(w.b)
        spear_in_b = next(e for e, n in document.entities.items() if n == "Spear")
        applied = await reader.post(
            f"{url}/updates",
            json={
                "actions": [
                    {"kind": "entity", "source_id": str(spear_in_b), "action": "add"},
                    {"kind": "entity", "source_id": str(w.ids["Longsword"]), "action": "apply"},
                ]
            },
        )
        assert applied.status_code == 200, applied.text
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword", "Spear"]
        assert (await reader.get(f"{url}/updates")).json()["changed"] == []
    finally:
        await w.done()


async def test_two_repositories_that_include_the_same_source_give_a_library_two_sets_of_its_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The diamond: B and C each include A, so each carries A's rows as its own, with its own ids.
    A library that takes both gets both sets, and the collision list resolves the overlap."""
    w = await _world(raw_client, fake_jwks_server)
    try:
        c, _ = await _bridge(w.base, "Crossbow Co", own="Crossbow")
        w.tenants.append(c)
        for repository in (w.b, c):
            assert (await _include(w.author, repository, w.a)).status_code == 200
            assert (await _make_public(w.author, repository)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201

        plan = (await reader.get(f"/tenants/{library}/repositories/{c}/copy-plan")).json()
        assert [s["name"] for s in plan["steps"]] == ["Crossbow Co"]
        collided = {(x["kind"], x["name"]) for x in plan["collisions"]}
        assert ("stat_group", "Abilities") in collided
        assert ("stat_definition", "Strength") in collided
        assert ("slug", "longsword") in collided

        refused = await _copy(reader, library, c)
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-needs-choices"
        resolutions = []
        for x in plan["collisions"]:
            if x["kind"] == "slug":
                resolutions.append(
                    {
                        "kind": "slug",
                        "source_id": x["source_id"],
                        "action": "rename",
                        "name": "c-sword",
                    }
                )
            else:
                resolutions.append(
                    {"kind": x["kind"], "source_id": x["source_id"], "action": "merge"}
                )
        copied = await _copy(reader, library, c, resolutions=resolutions)
        assert copied.status_code == 201, copied.text
        assert await _entries(reader, library) == [
            "Bridge Blade",
            "Crossbow",
            "Dagger",
            "Dagger",
            "Longsword",
            "Longsword",
        ]
        held = (await reader.get(f"/tenants/{library}/repositories")).json()["items"]
        assert sorted(r["repository"]["name"] for r in held) == ["Bridge", "Crossbow Co"]
    finally:
        await w.done()


async def test_one_repository_includes_a_public_source_while_another_shows_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """B includes the public A, C keeps it separate and visible: a library that took C holds A's
    rows from A, and B's flat copies of them collide with those, by name and link name."""
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Includer", invite=False)
    c, _ = await _bridge(base, "Shower", invite=False, own="Showcase")
    w = W(base, b, {}, [c])
    try:
        assert (await _include(base.author, b, base.repository)).status_code == 200
        for repository in (b, c):
            assert (await _make_public(base.author, repository)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        plan = (await reader.get(f"/tenants/{library}/repositories/{c}/copy-plan")).json()
        assert [s["name"] for s in plan["steps"]] == ["Armoury", "Shower"]
        assert (await _copy(reader, library, c)).status_code == 201
        assert (await reader.get(f"/tenants/{library}/repositories/{b}/dependencies")).json() == []
        plan = (await reader.get(f"/tenants/{library}/repositories/{b}/copy-plan")).json()
        assert [s["name"] for s in plan["steps"]] == ["Includer"]
        assert ("slug", "longsword") in {(x["kind"], x["name"]) for x in plan["collisions"]}
    finally:
        await w.done()


# --- The choice ---------------------------------------------------------------------------------


async def test_the_choice_is_on_the_copy_record_and_listed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        listed = (await w.author.get(f"/tenants/{w.b}/repositories")).json()["items"]
        assert len(listed) == 1
        assert listed[0]["inclusion"] == "show"
        assert listed[0]["includable"] == {"allowed": True, "by": "owner"}
        assert listed[0]["inclusion_in_release"] is None

        response = await _include(w.author, w.b, w.a)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "repository_id": str(w.a),
            "name": "Armoury",
            "inclusion": "include",
            "includable": {"allowed": True, "by": "owner"},
            "inclusion_in_release": None,
            "breaking_next_release": False,
            "showable": {"allowed": True, "by": "owner"},
            "hidable": {"allowed": True, "by": "owner"},
        }
        listed = (await w.author.get(f"/tenants/{w.b}/repositories")).json()["items"]
        assert listed[0]["inclusion"] == "include"
        # A's Owner reads who chose what, as it reads who copied.
        subscribers = (await w.author.get(f"/tenants/{w.a}/subscribers")).json()["items"]
        assert {s["name"]: s["inclusion"] for s in subscribers}["Bridge"] == "include"
        # The library the repository invited has not copied it.
        assert {s["name"]: s["inclusion"] for s in subscribers}["My Table"] is None
        # Back again, and again: the same word changes nothing and is not logged twice.
        assert (await _include(w.author, w.b, w.a, "show")).json()["inclusion"] == "show"
        assert (await _include(w.author, w.b, w.a, "show")).status_code == 200
        log = (await w.author.get(f"/tenants/{w.b}/activity-log")).json()["items"]
        assert [e["action"] for e in log].count("repository.inclusion_set") == 2
    finally:
        await w.done()


async def test_only_an_owner_of_the_repository_chooses_and_only_for_what_it_copied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
        w.actors.append(organizer)
        await add_member(w.author, w.b, organizer, "orga")
        refused = await _include(organizer, w.b, w.a)
        assert refused.status_code == 403
        stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
        w.actors.append(stranger)
        assert (await _include(stranger, w.b, w.a)).status_code == 404
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryCopy, (w.b, w.a))).inclusion == "show"

        # Not for a repository it has not copied, not a word that is not one, not on a library.
        other = uuid.uuid4()
        assert (await _include(w.author, w.b, other)).status_code == 409
        assert (await _include(w.author, w.b, w.a, "seal")).status_code == 422
        library = await w.author.create_tenant("A table")
        w.tenants.append(library)
        assert (await _include(w.author, library, w.a)).status_code == 409
    finally:
        await w.done()


async def test_the_database_allows_only_show_include_and_hide(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(RepositoryCopy)
                    .where(RepositoryCopy.tenant_id == w.b)
                    .values(inclusion="seal")
                )
            await session.rollback()
    finally:
        await w.done()


# --- Consent ------------------------------------------------------------------------------------


async def test_another_owners_repository_is_included_only_with_its_terms(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    owner_b = await make_actor(raw_client, fake_jwks_server, "owner-b")
    b, _ = await _bridge(base, "Other Bridge", owner=owner_b)
    w = W(base, b, {}, [], [owner_b])
    try:
        # A grant to read it is not a yes.
        refused = await _include(owner_b, b, base.repository)
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-not-includable"
        assert refused.json()["repositories"] == [{"id": str(base.repository), "name": "Armoury"}]
        listed = (await owner_b.get(f"/tenants/{b}/repositories")).json()["items"]
        assert listed[0]["includable"] == {"allowed": False, "by": None}
        check = (await owner_b.get(f"/tenants/{b}/flip-check")).json()
        assert [
            (s["name"], s["inclusion"], s["includable"]["allowed"]) for s in check["built_on"]
        ] == [("Armoury", "show", False)]
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryCopy, (b, base.repository))).inclusion == "show"

        # A's terms: its Owner's to say, members read them, nobody else does.
        terms = (await base.author.get(f"/tenants/{base.repository}/profile")).json()["terms"]
        assert terms == {
            "may_be_included": False,
            "is_default": True,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        assert (
            "terms"
            not in (
                await owner_b.get(f"/tenants/{b}/repositories/{base.repository}/profile")
            ).json()
        )
        assert (
            await owner_b.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_included": True}}
            )
        ).status_code == 404
        said = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_included": True}}
        )
        assert said.status_code == 200 and said.json()["terms"] == {
            "may_be_included": True,
            "is_default": False,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }

        allowed = await _include(owner_b, b, base.repository)
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["includable"] == {"allowed": True, "by": "terms"}
        assert (await _make_public(owner_b, b)).status_code == 200

        # Consent is asked once, when the choice is set. The terms change afterwards: the
        # choice stands and the next release is made, without a word of A's terms (ADR 0431).
        assert (
            await base.author.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_included": False}}
            )
        ).status_code == 200
        made = await owner_b.put(f"/tenants/{b}/published", json={"label": "1.1"})
        assert made.status_code == 200, made.text
        listed = (await owner_b.get(f"/tenants/{b}/repositories")).json()["items"]
        assert [(r["inclusion"], r["includable"]["allowed"]) for r in listed] == [
            ("include", False)
        ]
        # The choice made afterwards is a different matter: it is refused, for a change back too.
        shown = await _include(owner_b, b, base.repository, "show")
        assert shown.status_code == 200
        refused_again = await _include(owner_b, b, base.repository)
        assert refused_again.status_code == 409
        assert refused_again.json()["type"] == "repository-not-includable"
    finally:
        await w.done()


async def test_the_terms_follow_the_visibility_until_an_owner_says_otherwise(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    w = W(base, base.repository, {}, [])  # nothing but A
    w.b = base.repository
    try:
        url = f"/tenants/{base.repository}/profile"
        assert (await base.author.get(url)).json()["terms"] == {
            "may_be_included": False,
            "is_default": True,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        assert (await _make_public(base.author, base.repository)).status_code == 200
        assert (await base.author.get(url)).json()["terms"] == {
            "may_be_included": True,
            "is_default": True,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        # An Owner's value wins, in both directions, and null is the default again.
        off = await base.author.patch(url, json={"terms": {"may_be_included": False}})
        assert off.json()["terms"] == {
            "may_be_included": False,
            "is_default": False,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        # An empty `terms` says nothing; nothing but a boolean or null is a value.
        same = await base.author.patch(url, json={"terms": {}})
        assert same.json()["terms"] == {
            "may_be_included": False,
            "is_default": False,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        assert (await base.author.patch(url, json={"terms": None})).status_code == 422
        assert (
            await base.author.patch(url, json={"terms": {"may_be_included": "maybe"}})
        ).status_code == 422
        assert (
            await base.author.patch(url, json={"terms": {"may_be_sealed": True}})
        ).status_code == 422
        back = await base.author.patch(url, json={"terms": {"may_be_included": None}})
        assert back.json()["terms"] == {
            "may_be_included": True,
            "is_default": True,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
        private = await base.author.delete(
            f"/tenants/{base.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert private.status_code == 200, private.text
        assert (await base.author.get(url)).json()["terms"] == {
            "may_be_included": False,
            "is_default": True,
            "may_be_shown": True,
            "may_be_shown_is_default": True,
            "may_be_hidden": True,
            "may_be_hidden_is_default": True,
        }
    finally:
        await cleanup([base.table, base.repository], [base.author, base.gm])


# --- The gates ----------------------------------------------------------------------------------


async def test_an_included_source_is_not_a_dependency_for_the_stack_rule(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        check = (await w.author.get(f"/tenants/{w.b}/flip-check")).json()
        assert [(r["name"], r["owned"]) for r in check["built_on_not_public"]] == [
            ("Armoury", True)
        ]
        refused = await _make_public(w.author, w.b)
        assert refused.status_code == 409
        assert refused.json()["type"] == "built-on-not-public"

        assert (await _include(w.author, w.b, w.a)).status_code == 200
        check = (await w.author.get(f"/tenants/{w.b}/flip-check")).json()
        assert check["built_on_not_public"] == []
        assert [
            (s["name"], s["public"], s["owned"], s["inclusion"], s["includable"], s["in_release"])
            for s in check["built_on"]
        ] == [("Armoury", False, True, "include", {"allowed": True, "by": "owner"}, None)]
        assert (await _make_public(w.author, w.b)).status_code == 200
        check = (await w.author.get(f"/tenants/{w.b}/flip-check")).json()
        assert check["built_on"][0]["in_release"] == "include"
    finally:
        await w.done()


async def test_making_a_source_private_is_not_refused_for_a_dependent_that_includes_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Includer", invite=False)
    c, _ = await _bridge(base, "Shower", invite=False, own="Showcase")
    w = W(base, b, {}, [c])
    try:
        assert (await _include(base.author, b, base.repository)).status_code == 200
        for repository in (b, c):
            assert (await _make_public(base.author, repository)).status_code == 200

        # While B has only chosen, and C shows it, A's dependents are both: nothing carries it
        # included yet in a release a library reads... B's release did, so only C stops it.
        check = (await base.author.get(f"/tenants/{base.repository}/flip-check")).json()
        assert [d["name"] for d in check["public_dependents"]] == ["Shower"]
        refused = await base.author.delete(
            f"/tenants/{base.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "public-repositories-built-on-it"
        assert [d["name"] for d in refused.json()["repositories"]] == ["Shower"]

        assert (
            await base.author.delete(f"/tenants/{c}/public", params={"acknowledge_revokes": "true"})
        ).status_code == 200
        made = await base.author.delete(
            f"/tenants/{base.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert made.status_code == 200, made.text

        # B stays public and a library still copies it, never needing A.
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, b)).status_code == 201
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword"]
    finally:
        await w.done()


async def test_a_choice_not_yet_released_does_not_let_a_source_go_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """What a library reads is the release, so what counts for A going private is how B's
    current release carries A, not what B's Owner has chosen since."""
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Shower", invite=False)
    w = W(base, b, {}, [])
    try:
        assert (await _make_public(base.author, b)).status_code == 200  # shows A
        assert (await _include(base.author, b, base.repository)).status_code == 200  # not released
        refused = await base.author.delete(
            f"/tenants/{base.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert refused.status_code == 409
        assert [d["name"] for d in refused.json()["repositories"]] == ["Shower"]
    finally:
        await w.done()


# --- Changing the choice ------------------------------------------------------------------------


async def test_changing_the_choice_is_free_before_the_first_public_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (await w.author.put(f"/tenants/{w.b}/published")).status_code == 200
        for choice in ("include", "show", "include"):
            response = await _include(w.author, w.b, w.a, choice)
            assert response.json()["breaking_next_release"] is False
            preview = (await w.author.get(f"/tenants/{w.b}/release-preview")).json()
            assert preview["inclusion_changes"] == []
        made = await _make_public(w.author, w.b)  # no acknowledgement asked
        assert made.status_code == 200, made.text
        assert made.json()["release"]["breaking"] is False
    finally:
        await w.done()


async def test_changing_the_choice_after_the_first_public_release_makes_a_breaking_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        assert (await _make_public(w.author, w.b)).status_code == 200

        # Include to show: A's rows leave B's own, which the detector reads as removals too.
        response = await _include(w.author, w.b, w.a, "show")
        assert response.json()["inclusion_in_release"] == "include"
        assert response.json()["breaking_next_release"] is True
        listed = (await w.author.get(f"/tenants/{w.b}/repositories")).json()["items"]
        assert (listed[0]["inclusion"], listed[0]["inclusion_in_release"]) == ("show", "include")
        preview = (await w.author.get(f"/tenants/{w.b}/release-preview")).json()
        assert preview["inclusion_changes"] == [
            {"repository_id": str(w.a), "name": "Armoury", "before": "include", "after": "show"}
        ]
        assert preview["breaking"]
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        assert refused.json()["inclusion_changes"][0]["name"] == "Armoury"
        # (A is private, so B cannot be public over it as a separate repository.)
        assert (await _include(w.author, w.b, w.a)).json()["breaking_next_release"] is False
        assert (await w.author.get(f"/tenants/{w.b}/release-preview")).json()[
            "inclusion_changes"
        ] == []
    finally:
        await w.done()


async def test_a_change_with_no_removed_row_is_still_breaking(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Show to include only adds rows, which the detector does not call breaking: the choice is
    what makes the release breaking, and it is acknowledged the same way."""
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Shower", invite=False)
    w = W(base, b, {}, [])
    try:
        assert (await _make_public(base.author, b)).status_code == 200  # shows A
        assert (await _include(base.author, b, base.repository)).status_code == 200
        preview = (await base.author.get(f"/tenants/{b}/release-preview")).json()
        assert preview["breaking"] == []
        assert [c["after"] for c in preview["inclusion_changes"]] == ["include"]
        refused = await base.author.put(f"/tenants/{b}/published", json={"label": "2.0"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        assert refused.json()["breaking_rows"] == []
        assert "1 of the changes" in refused.json()["detail"]
        released = await base.author.put(
            f"/tenants/{b}/published", json={"label": "2.0", "acknowledge_breaking": True}
        )
        assert released.status_code == 200, released.text
        assert released.json()["release"]["breaking"] is True
        document = await _document(b)
        assert (
            document.links.copies == set()
            and document.sources[base.repository]["inclusion"] == "include"
        )
        assert (await base.author.get(f"/tenants/{b}/release-preview")).json()[
            "inclusion_changes"
        ] == []
    finally:
        await w.done()


async def test_making_an_earlier_release_current_is_breaking_when_it_carried_a_source_differently(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Shower", invite=False)
    w = W(base, b, {}, [])
    try:
        assert (await _make_public(base.author, b, label="1.0")).status_code == 200  # shows A
        assert (await _include(base.author, b, base.repository)).status_code == 200
        released = await base.author.put(
            f"/tenants/{b}/published", json={"label": "2.0", "acknowledge_breaking": True}
        )
        assert released.status_code == 200, released.text
        first = next(r for r in await _release_notes(w) if r["label"] == "1.0")

        url = f"/tenants/{b}/releases/{first['id']}/current"
        refused = await base.author.put(url)
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        assert [c["after"] for c in refused.json()["inclusion_changes"]] == ["show"]
        moved = await base.author.put(url, json={"acknowledge_breaking": True})
        assert moved.status_code == 200, moved.text
        # The profile says what the release libraries read now carries: A, not included.
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, b)
            assert [(s["name"], s["inclusion"]) for s in profile.release_sources or []] == [
                ("Armoury", "show")
            ]
    finally:
        await w.done()


async def test_terms_taken_back_do_not_stop_an_earlier_release_being_made_current(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Consent is asked once, when the choice is set: moving to a release that carried A included
    is not refused because A's Owner has since turned the terms off (ADR 0431)."""
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    owner_b = await make_actor(raw_client, fake_jwks_server, "owner-b")
    b, _ = await _bridge(base, "Other Bridge", owner=owner_b, invite=False)
    w = W(base, b, {}, [], [owner_b])
    try:
        assert (await _include(owner_b, b, base.repository)).status_code == 200
        assert (await _make_public(owner_b, b, label="1.0")).status_code == 200  # includes A
        assert (await _include(owner_b, b, base.repository, "show")).status_code == 200
        shown = await owner_b.put(
            f"/tenants/{b}/published", json={"label": "2.0", "acknowledge_breaking": True}
        )
        assert shown.status_code == 200, shown.text
        assert (
            await base.author.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_included": False}}
            )
        ).status_code == 200
        notes = (await owner_b.get(f"/tenants/{b}/releases")).json()["items"]
        first = next(r for r in notes if r["label"] == "1.0")
        moved = await owner_b.put(
            f"/tenants/{b}/releases/{first['id']}/current", json={"acknowledge_breaking": True}
        )
        assert moved.status_code == 200, moved.text
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, b)
            assert [(s["name"], s["inclusion"]) for s in profile.release_sources or []] == [
                ("Armoury", "include")
            ]
    finally:
        await w.done()


# --- Attribution --------------------------------------------------------------------------------


async def test_the_storefront_names_what_is_included_with_its_licence_from_the_snapshot(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        assert (
            await w.author.patch(f"/tenants/{w.a}/profile", json={"licence": LICENCE})
        ).status_code == 200
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        assert (await _make_public(w.author, w.b)).status_code == 200
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        w.actors.append(visitor)

        expected = [{"name": "Armoury", "licence": LICENCE}]
        storefront = (await visitor.get(f"/discover/repositories/{w.b}")).json()
        assert storefront["profile"]["includes"] == expected
        assert (await visitor.get(f"/repositories/{w.b}/profile")).json()["includes"] == expected
        member = (await w.author.get(f"/tenants/{w.b}/profile")).json()
        assert member["includes"] == expected
        # Nothing of A that would let a visitor reach it: its name and licence, no id.
        assert str(w.a) not in str(storefront)

        # A's licence is read when the release is made: changing it afterwards does not change
        # what this release says, and neither does A going away from view.
        await w.author.patch(
            f"/tenants/{w.a}/profile", json={"licence": {"label": "All rights reserved"}}
        )
        assert (await visitor.get(f"/discover/repositories/{w.b}")).json()["profile"][
            "includes"
        ] == expected
        released = await w.author.put(f"/tenants/{w.b}/published", json={"label": "1.1"})
        assert released.status_code == 200, released.text
        assert (await visitor.get(f"/discover/repositories/{w.b}")).json()["profile"][
            "includes"
        ] == [{"name": "Armoury", "licence": {"label": "All rights reserved", "url": None}}]
    finally:
        await w.done()


async def test_a_source_that_is_shown_is_not_named_as_included_and_a_licence_may_be_none(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    b, _ = await _bridge(base, "Shower", invite=False)
    c, _ = await _bridge(base, "Includer", invite=False, own="Includes")
    w = W(base, b, {}, [c])
    try:
        assert (await _include(base.author, c, base.repository)).status_code == 200
        for repository in (b, c):
            assert (await _make_public(base.author, repository)).status_code == 200
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        w.actors.append(visitor)
        assert (await visitor.get(f"/discover/repositories/{b}")).json()["profile"][
            "includes"
        ] == []
        assert (await visitor.get(f"/discover/repositories/{c}")).json()["profile"]["includes"] == [
            {"name": "Armoury", "licence": None}
        ]
    finally:
        await w.done()


async def test_a_public_repository_of_another_owner_is_included_by_default_and_made_private_after(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A is public and not B's Owner's. Nobody said anything about its terms, so they are the
    default of a public repository: it may be included. B's release carries it, so A's Owner makes
    A private without B in the way, a library that took B keeps reading it, and B releases again
    after: its choice was made once, with A's yes, and A's terms are not asked again."""
    base = await release_world(raw_client, fake_jwks_server)
    assert (await _make_public(base.author, base.repository)).status_code == 200
    owner_b = await make_actor(raw_client, fake_jwks_server, "owner-b")
    b, _ = await _bridge(base, "Other Bridge", owner=owner_b, invite=False)
    w = W(base, b, {}, [], [owner_b])
    try:
        allowed = await _include(owner_b, b, base.repository)
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["includable"] == {"allowed": True, "by": "terms"}
        assert (await _make_public(owner_b, b)).status_code == 200

        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, b)).status_code == 201
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword"]

        # A's Owner makes A private: B's release carries A as its own, so nothing is built on it.
        check = (await base.author.get(f"/tenants/{base.repository}/flip-check")).json()
        assert check["public_dependents"] == []
        made = await base.author.delete(
            f"/tenants/{base.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert made.status_code == 200, made.text
        # The library that took the flat B reads on: it never read A, and still does not.
        assert (await reader.get(f"/tenants/{library}/repositories/{b}/updates")).status_code == 200
        late, late_library = await _library(raw_client, fake_jwks_server, w, "Latecomer")
        assert (await _copy(late, late_library, b)).status_code == 201
        assert await _entries(late, late_library) == ["Bridge Blade", "Dagger", "Longsword"]
        assert (
            await late.get(f"/tenants/{late_library}/repositories/{base.repository}/entities")
        ).status_code == 404

        # B copied the public A by itself, so going private took its grant away: B cannot read A,
        # and cannot release a flattened copy of what it cannot read, until A's Owner invites it.
        unreadable = await owner_b.put(f"/tenants/{b}/published", json={"label": "1.1"})
        assert unreadable.status_code == 409
        assert unreadable.json()["type"] == "built-on-behind"
        assert [r["readable"] for r in unreadable.json()["repositories"]] == [False]
        invited = await base.author.put(f"/tenants/{base.repository}/subscribers/{b}")
        assert invited.status_code == 201, invited.text
        # A is private now, so its terms are the default of a private repository again, and B's
        # Owner is not one of A's: the choice B made while A was public stands, and the release
        # is made without asking A's terms again.
        again = await owner_b.put(f"/tenants/{b}/published", json={"label": "1.1"})
        assert again.status_code == 200, again.text
    finally:
        await w.done()
