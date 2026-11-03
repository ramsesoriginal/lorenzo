"""ADR 0384: an Owner retires (deprecates) a repository (RFC 0038 section 7).

A retired repository keeps its updates for the libraries that hold it, blocks every new copy, leaves
Discover and its storefront, and stops being open to visitors and to libraries with no grant; its
members read it and are told; the libraries that hold it read the Owner's message and are told when
it is retired and when it is brought back. Every reader against every state, the new copies, the
dependencies, the routes, the notices, the log and the flips.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _fanout_world import fanouts_of
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import set_preview, set_visibility
from httpx import AsyncClient
from sqlalchemy import select
from test_repository_attachments import _share, _stack

from lorenzo_api.config import get_settings
from lorenzo_api.models import Entity, Membership, MembershipRole, RepositoryCopy
from lorenzo_api.release_fanout import drain

OPERATORS = ("platform-operator",)
MESSAGE = "Use Armoury 2 instead"


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


@dataclass
class Scene:
    """Armoury with one release, public or not: its Owner (`world.author`); a library that holds an
    invitation and has copied it (`world.table`, run by `world.gm`); a library that holds an
    invitation and has not copied (`invitee`); a library that copied it by itself while it was
    public (`copier`, public states only); a visitor with no library; an operator."""

    world: ReleaseWorld
    visitor: Actor
    operator: Actor
    invitee: Actor
    invitee_library: uuid.UUID
    copier: Actor | None
    copier_library: uuid.UUID | None
    word: str

    @property
    def repository(self) -> uuid.UUID:
        return self.world.repository

    @property
    def owner(self) -> Actor:
        return self.world.author

    async def retire(self, message: str | None = MESSAGE) -> Any:
        body = {} if message is None else {"message": message}
        response = await self.owner.put(f"/tenants/{self.repository}/deprecation", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    async def bring_back(self) -> Any:
        response = await self.owner.delete(f"/tenants/{self.repository}/deprecation")
        assert response.status_code == 200, response.text
        return response.json()

    async def delist(self) -> None:
        response = await self.operator.put(
            f"/admin/repositories/{self.repository}/delist", json={"reason": "It breaks the rules"}
        )
        assert response.status_code == 200, response.text

    async def done(self) -> None:
        tenants = [self.invitee_library] + ([self.copier_library] if self.copier_library else [])
        await self.world.done()
        actors = [self.visitor, self.operator, self.invitee] + (
            [self.copier] if self.copier else []
        )
        await cleanup(tenants, actors)


async def _scene(raw_client: AsyncClient, jwks: FakeJwksServer, *, public: bool = True) -> Scene:
    world = await release_world(raw_client, jwks, published=False)
    word = uuid.uuid4().hex[:10]
    renamed = await world.author.patch(
        f"/tenants/{world.repository}", json={"name": f"Armoury {word}"}
    )
    assert renamed.status_code == 200, renamed.text
    if public:
        await set_visibility([world.repository], "public")
        await set_preview([world.repository], "public")
    await world.publish(label="2.0")
    await world.copy()
    invitee = await make_actor(raw_client, jwks, "invitee")
    invitee_library = await invitee.create_tenant("The invitee's table")
    invited = await world.author.put(f"/tenants/{world.repository}/subscribers/{invitee_library}")
    assert invited.status_code == 201, invited.text
    copier = copier_library = None
    if public:
        copier = await make_actor(raw_client, jwks, "copier")
        copier_library = await copier.create_tenant("The copier's table")
        copied = await copier.post(
            f"/tenants/{copier_library}/repositories/{world.repository}/copy", json={}
        )
        assert copied.status_code == 201, copied.text
    visitor = await make_actor(raw_client, jwks, "visitor", roles=())
    operator = await make_actor(raw_client, jwks, "operator", roles=OPERATORS)
    return Scene(world, visitor, operator, invitee, invitee_library, copier, copier_library, word)


async def _entity_names(tenant_id: uuid.UUID) -> list[str]:
    async with admin_session_factory() as session:
        return sorted(
            await session.scalars(select(Entity.name).where(Entity.tenant_id == tenant_id))
        )


async def _notices(actor: Actor, type: str | None = None) -> list[dict[str, Any]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return [n for n in items if type is None or n["type"] == type]


async def _add_member(tenant: uuid.UUID, actor: Actor, role: MembershipRole) -> None:
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant, user_id=actor.user_id, role=role))
        await session.commit()


# --- Every reader, in every state -------------------------------------------------------------


async def _visitor_reads(scene: Scene) -> dict[str, int]:
    v, r = scene.visitor, scene.repository
    listing = await v.get("/discover/repositories", params={"q": scene.word})
    assert listing.status_code == 200
    return {
        "listed": len(listing.json()["items"]),
        "storefront": (await v.get(f"/discover/repositories/{r}")).status_code,
        "profile": (await v.get(f"/repositories/{r}/profile")).status_code,
        "cover": (await v.get(f"/repositories/{r}/profile/cover")).status_code,
        "releases": (await v.get(f"/repositories/{r}/releases")).status_code,
        "preview": (await v.get(f"/repositories/{r}/preview")).status_code,
        "browse": (await v.get(f"/repositories/{r}/entities")).status_code,
        "groups": (await v.get(f"/repositories/{r}/stat-groups")).status_code,
        "dependencies": (await v.get(f"/repositories/{r}/dependencies")).status_code,
    }


async def _library_reads(
    actor: Actor, library: uuid.UUID, repository: uuid.UUID
) -> dict[str, tuple[int, str | None]]:
    """What a library gets through its own routes: the status and, for a refusal, its type."""
    base = f"/tenants/{library}/repositories/{repository}"

    def seen(response: Any) -> tuple[int, str | None]:
        body = response.json() if response.status_code >= 400 else {}
        return response.status_code, body.get("type")

    return {
        "profile": seen(await actor.get(f"{base}/profile")),
        "releases": seen(await actor.get(f"{base}/releases")),
        "preview": seen(await actor.get(f"{base}/preview")),
        "browse": seen(await actor.get(f"{base}/entities")),
        "groups": seen(await actor.get(f"{base}/stat-groups")),
        "dependencies": seen(await actor.get(f"{base}/dependencies")),
        "plan": seen(await actor.get(f"{base}/copy-plan")),
        "copy": seen(await actor.post(f"{base}/copy", json={"dry_run": True})),
        "updates": seen(await actor.get(f"{base}/updates")),
        "apply": seen(await actor.post(f"{base}/updates", json={"actions": []})),
    }


NOT_FOUND = (404, "repository-not-found")
OK = (200, None)


def _expected(*, readable: bool, deprecated: bool, copied: bool) -> dict[str, Any]:
    """What a library that holds a grant gets, by whether the repository is closed to it (delisted),
    retired, and whether it has copied it. A holder reads whatever is not delisted; a retired
    repository refuses every new copy, and an already copied one is told so as before."""
    # What a library that has not copied it is told by the update routes comes before the gate.
    not_copied = (409, "repository-not-copied")
    if not readable:
        closed = dict.fromkeys(
            ("profile", "releases", "preview", "browse", "groups", "dependencies", "plan", "copy"),
            NOT_FOUND,
        )
        updates = NOT_FOUND if copied else not_copied
        return closed | {"updates": updates, "apply": updates}
    refused = (409, "repository-deprecated")
    return {
        "profile": OK,
        "releases": OK,
        "preview": OK,
        "browse": OK,
        "groups": OK,
        "dependencies": OK,
        "plan": refused if deprecated else OK,
        "copy": refused if deprecated else ((409, "repository-already-copied") if copied else OK),
        # What a library that copied it checks and applies; one that has not, is told so.
        "updates": OK if copied else not_copied,
        "apply": OK if copied else not_copied,
    }


@pytest.mark.parametrize(
    "state",
    [
        "public",
        "private",
        "deprecated public",
        "deprecated private",
        "deprecated and delisted",
    ],
)
async def test_every_reader_by_state(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, state: str
) -> None:
    public = state in ("public", "deprecated public", "deprecated and delisted")
    scene = await _scene(raw_client, fake_jwks_server, public=public)
    try:
        deprecated = state.startswith("deprecated")
        delisted = state.endswith("delisted")
        if deprecated:
            await scene.retire()
        if delisted:
            await scene.delist()

        # A visitor reads a public repository, unless it is retired or delisted.
        visitor = await _visitor_reads(scene)
        seen = {k: v for k, v in visitor.items() if k != "listed"}
        if public and not deprecated:
            assert visitor["listed"] == 1
            assert seen == dict.fromkeys(seen, 200) | {"cover": 404}, state
        else:
            assert visitor["listed"] == 0
            assert seen == dict.fromkeys(seen, 404), state

        # A library that holds a grant, as an invitation or from a copy it made of a public
        # repository, reads what it read: only a delist closes it.
        readers = [
            (scene.world.gm, scene.world.table, True),
            (scene.invitee, scene.invitee_library, False),
        ]
        if scene.copier and scene.copier_library:
            readers.append((scene.copier, scene.copier_library, True))
        for actor, library, copied in readers:
            reads = await _library_reads(actor, library, scene.repository)
            expected = _expected(readable=not delisted, deprecated=deprecated, copied=copied)
            assert reads == expected, (state, library)

        # A library with no grant reads what a visitor does, nothing, as it is retired.
        stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
        stranger_library = await stranger.create_tenant("A stranger's table")
        try:
            reads = await _library_reads(stranger, stranger_library, scene.repository)
            if public and not deprecated:
                assert reads["profile"] == OK and reads["plan"] == OK
            else:
                assert reads == _expected(readable=False, deprecated=False, copied=False), state
        finally:
            await cleanup([stranger_library], [stranger])

        # The Owner reads all of its own, whatever it is.
        member = {
            "profile": (await scene.owner.get(f"/tenants/{scene.repository}/profile")).status_code,
            "entities": (
                await scene.owner.get(f"/tenants/{scene.repository}/entities")
            ).status_code,
            "releases": (
                await scene.owner.get(f"/tenants/{scene.repository}/releases")
            ).status_code,
        }
        assert member == dict.fromkeys(member, 200), state
        # An operator is no member and reads nothing of it.
        operator = (await scene.operator.get(f"/tenants/{scene.repository}/profile")).status_code
        assert operator == 404
    finally:
        await scene.done()


# --- Updates go on, for the libraries that hold it --------------------------------------------


async def test_a_library_that_holds_a_retired_repository_keeps_its_updates(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        before = await _entity_names(scene.world.table)
        await scene.retire()

        # The Owner goes on working: an entry changes, and a release is made, as before.
        async with admin_session_factory() as session:
            (await session.get_one(Entity, scene.world.ids["Orc"])).name = "Ogre"
            await session.commit()
        assert (await scene.world.publish(label="3.0"))["label"] == "3.0"

        assert scene.copier and scene.copier_library
        for actor, library in (
            (scene.world.gm, scene.world.table),
            (scene.copier, scene.copier_library),
        ):
            base = f"/tenants/{library}/repositories/{scene.repository}"
            checked = await actor.get(f"{base}/updates")
            assert checked.status_code == 200, checked.text
            assert checked.json()["release"]["label"] == "3.0"
            assert [c["name"] for c in checked.json()["changed"]] == ["Orc"]
            orc = checked.json()["changed"][0]["source_id"]
            applied = await actor.post(
                f"{base}/updates",
                json={"actions": [{"kind": "entity", "source_id": orc, "action": "apply"}]},
            )
            assert applied.status_code == 200, applied.text
        # The libraries that hold it were told of the release, as for any other.
        assert len(await _notices(scene.world.gm, "repository_updated")) >= 1
        assert before == ["Dagger", "Longsword", "Orc"]
        assert "Ogre" in await _entity_names(scene.world.table)
        assert "Ogre" in await _entity_names(scene.copier_library)

        # Their list says it is retired and says the Owner's words; nobody else's list does.
        listing = await scene.world.gm.get(f"/tenants/{scene.world.table}/repositories")
        [row] = [
            i for i in listing.json()["items"] if i["repository"]["id"] == str(scene.repository)
        ]
        assert row["deprecated"] == {"message": MESSAGE}
        assert row["repository"]["published_at"] is not None
        assert row["current_release"]["label"] == "3.0"
    finally:
        await scene.done()


# --- New copies are blocked --------------------------------------------------------------------


async def test_a_retired_repository_blocks_new_copies_by_every_library_that_can_read_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, public=False)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    library = await stranger.create_tenant("A stranger's table")
    try:
        await scene.retire(MESSAGE)
        base = f"/tenants/{scene.invitee_library}/repositories/{scene.repository}"

        # The library that holds only an invitation: refused, in words, with the Owner's message.
        plan = await scene.invitee.get(f"{base}/copy-plan")
        refused = await scene.invitee.post(f"{base}/copy", json={})
        for response in (plan, refused):
            assert response.status_code == 409, response.text
            problem = response.json()
            assert problem["type"] == "repository-deprecated"
            assert f"Armoury {scene.word}" in problem["detail"]
            assert MESSAGE in problem["detail"]
            assert "tenant" not in (problem["title"] + problem["detail"]).lower()
        assert await _entity_names(scene.invitee_library) == []

        # A library with no invitation reads nothing of it: not found, and no message.
        other = f"/tenants/{library}/repositories/{scene.repository}"
        for response in (
            await stranger.get(f"{other}/copy-plan"),
            await stranger.post(other + "/copy", json={}),
        ):
            assert response.status_code == 404
            assert MESSAGE not in response.text

        # A library that has copied it cannot copy it again, with or without `again`: it keeps
        # what it has, nothing is forgotten.
        held = f"/tenants/{scene.world.table}/repositories/{scene.repository}"
        before = await _entity_names(scene.world.table)
        for body in ({}, {"again": "keep"}, {"again": "purge"}):
            response = await scene.world.gm.post(f"{held}/copy", json=body)
            assert response.status_code == 409
            assert response.json()["type"] == "repository-deprecated"
        assert await _entity_names(scene.world.table) == before
        async with admin_session_factory() as session:
            copy = await session.get(RepositoryCopy, (scene.world.table, scene.repository))
        assert copy is not None

        # Brought back, the invited library copies it.
        await scene.bring_back()
        copied = await scene.invitee.post(f"{base}/copy", json={})
        assert copied.status_code == 201, copied.text
    finally:
        await scene.done()
        await cleanup([library], [stranger])


async def test_a_retired_repository_is_not_taken_in_as_a_new_dependency(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    reader = await make_actor(raw_client, fake_jwks_server, "library")
    library = await reader.create_tenant("A library")
    try:
        # Invited to all three; it has copied Common Equipment and D&D 5e already... not yet.
        for repository in (stack.equipment, stack.rules, stack.bridge):
            await _share(stack.author, repository, library)
        retired = await stack.author.put(
            f"/tenants/{stack.equipment}/deprecation", json={"message": "Superseded"}
        )
        assert retired.status_code == 200, retired.text

        base = f"/tenants/{library}/repositories"
        # The bridge would bring Common Equipment in, which has been retired: refused, naming it.
        plan = await reader.get(f"{base}/{stack.bridge}/copy-plan")
        assert plan.status_code == 409, plan.text
        assert plan.json()["type"] == "repository-deprecated"
        assert "Common Equipment" in plan.json()["detail"]
        assert "Superseded" in plan.json()["detail"]
        refused = await reader.post(f"{base}/{stack.bridge}/copy", json={})
        assert refused.status_code == 409
        assert await _entity_names(library) == []

        # D&D 5e, not retired, copies as ever.
        assert (await reader.post(f"{base}/{stack.rules}/copy", json={})).status_code == 201

        # Brought back, the bridge copies with everything it is built on.
        brought = await stack.author.delete(f"/tenants/{stack.equipment}/deprecation")
        assert brought.json()["undeprecated"] is True
        assert (await reader.post(f"{base}/{stack.bridge}/copy", json={})).status_code == 201
    finally:
        await cleanup([*stack.tenants, library], [*stack.actors, reader])


async def test_a_library_that_copied_the_dependency_before_it_was_retired_still_copies_the_bridge(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    reader = await make_actor(raw_client, fake_jwks_server, "library")
    library = await reader.create_tenant("A library")
    try:
        for repository in (stack.equipment, stack.rules, stack.bridge):
            await _share(stack.author, repository, library)
        base = f"/tenants/{library}/repositories"
        assert (await reader.post(f"{base}/{stack.equipment}/copy", json={})).status_code == 201
        retired = await stack.author.put(f"/tenants/{stack.equipment}/deprecation", json={})
        assert retired.status_code == 200

        # It has Common Equipment already: the bridge brings in D&D 5e and itself.
        assert (await reader.get(f"{base}/{stack.bridge}/copy-plan")).status_code == 200
        assert (await reader.post(f"{base}/{stack.bridge}/copy", json={})).status_code == 201
    finally:
        await cleanup([*stack.tenants, library], [*stack.actors, reader])


# --- The routes ---------------------------------------------------------------------------------


async def test_retiring_is_idempotent_a_new_message_replaces_the_old_and_the_time_is_kept(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        first = await scene.retire("Superseded by Armoury 2")
        assert first["message"] == "Superseded by Armoury 2"
        assert set(first) == {"message", "at"}

        again = await scene.retire("  Use Armoury 3  ")
        assert again["message"] == "Use Armoury 3"
        assert again["at"] == first["at"]

        # No message at all is a state too, and replaces the old one.
        bare = await scene.retire(None)
        assert bare == {"message": None, "at": first["at"]}
        none = await scene.owner.put(f"/tenants/{scene.repository}/deprecation")
        assert none.status_code == 200 and none.json()["message"] is None

        profile = (await scene.owner.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["deprecated"] == {"message": None, "at": first["at"]}
    finally:
        await scene.done()


@pytest.mark.parametrize("message", ["", "   ", "x" * 501])
async def test_a_message_of_one_to_five_hundred_characters_when_given(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, message: str
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        url = f"/tenants/{scene.repository}/deprecation"
        assert (await scene.owner.put(url, json={"message": message})).status_code == 422
        assert (await scene.owner.put(url, json={"note": "x"})).status_code == 422
        profile = (await scene.owner.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["deprecated"] is None
        # Five hundred is the most, and line breaks are kept.
        ok = await scene.owner.put(url, json={"message": "x" * 499 + "\n"})
        assert ok.status_code == 200 and len(ok.json()["message"]) == 499
        assert (await scene.owner.put(url, json={"message": "x" * 500})).status_code == 200
        assert (await scene.owner.put(url, json={"message": "Two\nlines"})).json()["message"] == (
            "Two\nlines"
        )
    finally:
        await scene.done()


async def test_bringing_it_back_restores_everything_and_is_a_no_op_for_one_that_is_not_retired(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        listed = await _visitor_reads(scene)
        assert listed["listed"] == 1
        libraries = [
            (scene.world.gm, scene.world.table),
            (scene.invitee, scene.invitee_library),
        ]
        holds = [await _library_reads(a, lib, scene.repository) for a, lib in libraries]

        # Not retired: nothing to do, nothing is logged or sent.
        nothing = await scene.bring_back()
        assert nothing == {"undeprecated": False}
        assert await _notices(scene.world.gm, "repository_undeprecated") == []

        await scene.retire()
        assert (await _visitor_reads(scene))["listed"] == 0
        done = await scene.bring_back()
        assert done == {"undeprecated": True}
        assert await _visitor_reads(scene) == listed
        assert [await _library_reads(a, lib, scene.repository) for a, lib in libraries] == holds
        profile = (await scene.owner.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["deprecated"] is None
        assert (await scene.bring_back()) == {"undeprecated": False}
    finally:
        await scene.done()


async def test_only_an_owner_retires_a_repository_and_only_a_repository_is_retired(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
    author = await make_actor(raw_client, fake_jwks_server, "author")
    try:
        await _add_member(scene.repository, organizer, MembershipRole.ORGA)
        await _add_member(scene.repository, author, MembershipRole.AUTHOR)
        url = f"/tenants/{scene.repository}/deprecation"
        for actor in (organizer, author):
            put = await actor.put(url, json={"message": "x"})
            assert put.status_code == 403, put.text
            assert (await actor.delete(url)).status_code == 403
        # A library's Owner is no member of the repository: not found, as any of its routes.
        for actor in (scene.world.gm, scene.visitor):
            assert (await actor.put(url, json={})).status_code in (403, 404)
        profile = (await scene.owner.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["deprecated"] is None

        # A library is not a repository.
        library_url = f"/tenants/{scene.world.table}/deprecation"
        refused = await scene.world.gm.put(library_url, json={})
        assert refused.status_code == 409 or refused.status_code == 422
        assert refused.json()["type"] == "not-a-repository"
        assert (await scene.world.gm.delete(library_url)).json()["type"] == "not-a-repository"
    finally:
        await scene.done()
        await cleanup([], [organizer, author])


# --- What members and libraries read of it -----------------------------------------------------


async def test_members_read_that_it_is_retired_and_nobody_else_but_a_holder_does(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
    author = await make_actor(raw_client, fake_jwks_server, "author")
    try:
        await _add_member(scene.repository, organizer, MembershipRole.ORGA)
        await _add_member(scene.repository, author, MembershipRole.AUTHOR)
        profile_url = f"/tenants/{scene.repository}/profile"
        for member in (scene.owner, organizer, author):
            assert (await member.get(profile_url)).json()["deprecated"] is None
        first = await scene.retire(MESSAGE)

        for member in (scene.owner, organizer, author):
            profile = (await member.get(profile_url)).json()
            # The message and the time, and no name: not who retired it.
            assert profile["deprecated"] == {"message": MESSAGE, "at": first["at"]}
            assert (await member.get(f"/tenants/{scene.repository}/entities")).status_code == 200
        # The Owner edits and releases as ever; the edit answers with the state too.
        edited = await scene.owner.patch(profile_url, json={"summary": "Still the best"})
        assert edited.status_code == 200
        assert edited.json()["deprecated"]["message"] == MESSAGE
        assert (await scene.world.publish(label="3.0"))["label"] == "3.0"
        # The Owner's flip check says so too.
        check = (await scene.owner.get(f"/tenants/{scene.repository}/flip-check")).json()
        assert check["deprecated"] == {"message": MESSAGE, "at": first["at"]}

        # A library that holds it reads the message in its list; one that holds nothing has no row.
        listing = (await scene.invitee.get(f"/tenants/{scene.invitee_library}/repositories")).json()
        [row] = [i for i in listing["items"] if i["repository"]["id"] == str(scene.repository)]
        assert row["deprecated"] == {"message": MESSAGE}
        # Never the Owner's identity, anywhere a library or a visitor reads.
        assert str(scene.owner.user_id) not in str(listing)

        # Brought back, no reader carries it.
        await scene.bring_back()
        assert (await scene.owner.get(profile_url)).json()["deprecated"] is None
        listing = (await scene.invitee.get(f"/tenants/{scene.invitee_library}/repositories")).json()
        [row] = [i for i in listing["items"] if i["repository"]["id"] == str(scene.repository)]
        assert row["deprecated"] is None
        for reader in (
            await scene.visitor.get(f"/repositories/{scene.repository}/profile"),
            await scene.visitor.get(f"/discover/repositories/{scene.repository}"),
        ):
            assert reader.status_code == 200
            assert "deprecated" not in str(reader.json())
    finally:
        await scene.done()
        await cleanup([], [organizer, author])


async def test_a_retired_repository_leaves_discover_and_its_facets(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.owner.patch(
            f"/tenants/{scene.repository}/profile", json={"tags": [f"t{scene.word}"]}
        )

        def counts(body: dict[str, Any]) -> dict[str, int]:
            return {t["value"]: t["count"] for t in body["tags"]}

        facets = (await scene.visitor.get("/discover/facets")).json()
        assert counts(facets)[f"t{scene.word}"] == 1
        await scene.retire()
        facets = (await scene.visitor.get("/discover/facets")).json()
        assert f"t{scene.word}" not in counts(facets)
        found = await scene.visitor.get("/discover/repositories", params={"tag": f"t{scene.word}"})
        assert found.json()["total"] == 0
        assert (
            await scene.visitor.get(f"/discover/repositories/{scene.repository}")
        ).status_code == 404

        await scene.bring_back()
        facets = (await scene.visitor.get("/discover/facets")).json()
        assert counts(facets)[f"t{scene.word}"] == 1
    finally:
        await scene.done()


# --- The flips ----------------------------------------------------------------------------------


async def test_a_retired_repository_cannot_be_made_public_and_the_check_says_so(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, public=False)
    try:
        owner, r = scene.owner, scene.repository
        assert (await owner.get(f"/tenants/{r}/flip-check")).json()["deprecated"] is None
        await scene.retire(MESSAGE)

        refused = await owner.put(
            f"/tenants/{r}/public", json={"summary": "Every blade", "accept_terms": True}
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-deprecated"
        assert "tenant" not in (refused.json()["title"] + refused.json()["detail"]).lower()
        # Nothing was kept, not even the summary beside it.
        profile = (await owner.get(f"/tenants/{r}/profile")).json()
        assert (profile["visibility"], profile["summary"]) == ("private", "")

        await scene.bring_back()
        made = await owner.put(
            f"/tenants/{r}/public", json={"summary": "Every blade", "accept_terms": True}
        )
        assert made.status_code == 200, made.text
    finally:
        await scene.done()


async def test_a_deprecated_and_delisted_repository_says_it_is_delisted_when_made_public(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, public=False)
    try:
        await scene.retire()
        await scene.delist()
        refused = await scene.owner.put(
            f"/tenants/{scene.repository}/public",
            json={"summary": "Every blade", "accept_terms": True},
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-delisted"
    finally:
        await scene.done()


async def test_a_retired_public_repository_is_made_private_and_stays_retired(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.retire()
        made = await scene.owner.delete(
            f"/tenants/{scene.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert made.status_code == 200, made.text
        profile = (await scene.owner.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["visibility"] == "private"
        assert profile["deprecated"]["message"] == MESSAGE
        # The library invited keeps reading it; the visitor reads nothing.
        reads = await _library_reads(scene.world.gm, scene.world.table, scene.repository)
        assert reads["profile"] == OK and reads["updates"] == OK
        assert (await _visitor_reads(scene))["listed"] == 0
    finally:
        await scene.done()


# --- The libraries are told ---------------------------------------------------------------------


async def test_the_libraries_that_hold_it_are_told_once_and_again_when_it_is_back(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
    member = await make_actor(raw_client, fake_jwks_server, "repository organizer")
    try:
        await _add_member(scene.world.table, organizer, MembershipRole.ORGA)
        await _add_member(scene.repository, member, MembershipRole.ORGA)
        name = f"Armoury {scene.word}"

        await scene.retire(MESSAGE)
        await scene.retire("A second message")  # a new message does not tell them again
        await scene.retire("A second message")  # nor does the same one

        assert scene.copier
        # The Owners and Organizers of a library that copied it: you keep your copy and its updates.
        for actor in (scene.world.gm, organizer, scene.copier):
            [told] = await _notices(actor, "repository_deprecated")
            assert told["title"] == f"{name} was retired by its Owner"
            assert told["body"] == (
                "You keep your copy and its updates; it can no longer be copied.\n"
                f"Message: {MESSAGE}"
            )
            assert "tenant" not in (told["title"] + told["body"]).lower()
        # A library that holds only an invitation is told it cannot be copied, not that it keeps
        # a copy it has not made.
        [invited] = await _notices(scene.invitee, "repository_deprecated")
        assert invited["body"] == f"It can no longer be copied.\nMessage: {MESSAGE}"
        # Not the repository's own members: they did it. Not a visitor.
        assert await _notices(scene.owner, "repository_deprecated") == []
        assert await _notices(member, "repository_deprecated") == []
        assert await _notices(scene.visitor, "repository_deprecated") == []

        await scene.bring_back()
        await scene.bring_back()  # a no-op tells nobody
        for actor in (scene.world.gm, organizer, scene.copier, scene.invitee):
            [back] = await _notices(actor, "repository_undeprecated")
            assert back["title"] == f"{name} is available again"
        assert await _notices(scene.owner, "repository_undeprecated") == []

        # Retired again, they are told again: it is a new state.
        await scene.retire(None)
        told = await _notices(scene.world.gm, "repository_deprecated")
        assert len(told) == 2
        assert [n["body"] for n in told if "Message" not in n["body"]] == [
            "You keep your copy and its updates; it can no longer be copied."
        ]
    finally:
        await scene.done()
        await cleanup([], [organizer, member])


async def test_a_delisted_repository_tells_no_library_that_it_was_retired(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.delist()
        await scene.retire()
        assert await _notices(scene.world.gm, "repository_deprecated") == []
        await scene.bring_back()
        assert await _notices(scene.world.gm, "repository_undeprecated") == []
    finally:
        await scene.done()


async def test_the_log_records_both_ways_with_the_owner_and_none_of_the_words(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.retire("Secret words nobody should log")
        await scene.retire("Secret words nobody should log")  # nothing changed: not logged again
        await scene.retire("Other secret words")  # a new message is
        await scene.bring_back()
        await scene.bring_back()  # a no-op is not logged

        log = await scene.owner.get(f"/tenants/{scene.repository}/activity-log")
        entries = [e for e in log.json()["items"] if e["action"].startswith("repository.")]
        retired = [e for e in entries if e["action"] == "repository.deprecated"]
        back = [e for e in entries if e["action"] == "repository.undeprecated"]
        assert (len(retired), len(back)) == (2, 1)
        assert {e["actor_id"] for e in retired + back} == {str(scene.owner.user_id)}
        assert "secret" not in str(log.json()).lower()
    finally:
        await scene.done()


@pytest.fixture
def held_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is drained after a response: the announcement waits for what the test does."""
    monkeypatch.setattr(
        "lorenzo_api.routers.repository_deprecation.drain_after_response",
        lambda *args, **kwargs: None,
    )


async def _rows(scene: Scene, type: str) -> list[tuple[int, int, bool, str]]:
    """The repository's announcements of one type, the smaller first."""
    return sorted(r for r in await fanouts_of(scene.repository) if r[3] == type)


async def test_the_announcement_is_a_row_for_the_libraries_as_they_were_and_the_drain_tells_them(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.retire()
        # Two rows, written with the change and telling nobody yet: the two libraries that copied
        # it by an invitation and by themselves, and the one that holds an invitation only.
        assert await _rows(scene, "repository_deprecated") == [
            (1, 0, False, "repository_deprecated"),
            (2, 0, False, "repository_deprecated"),
        ]
        assert await _notices(scene.world.gm, "repository_deprecated") == []

        await scene.retire("A new message")  # no new row
        assert len(await _rows(scene, "repository_deprecated")) == 2

        await drain()
        assert len(await _notices(scene.world.gm, "repository_deprecated")) == 1
        assert len(await _notices(scene.invitee, "repository_deprecated")) == 1

        await scene.bring_back()
        assert await _rows(scene, "repository_undeprecated") == [
            (3, 0, False, "repository_undeprecated")
        ]
        await drain()
        assert len(await _notices(scene.invitee, "repository_undeprecated")) == 1
    finally:
        await scene.done()


async def test_a_repository_built_on_a_retired_one_keeps_its_updates_from_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        retired = await stack.author.put(f"/tenants/{stack.equipment}/deprecation", json={})
        assert retired.status_code == 200, retired.text

        # The bridge holds a copy of Common Equipment: it checks and takes its updates as ever, and
        # its own Owner reads that it is retired in the list of what it is built on.
        base = f"/tenants/{stack.bridge}/repositories"
        checked = await stack.author.get(f"{base}/{stack.equipment}/updates")
        assert checked.status_code == 200, checked.text
        applied = await stack.author.post(f"{base}/{stack.equipment}/updates", json={"actions": []})
        assert applied.status_code == 200, applied.text
        listing = (await stack.author.get(base)).json()
        [row] = [i for i in listing["items"] if i["repository"]["id"] == str(stack.equipment)]
        assert row["deprecated"] == {"message": None}
        # Copying it into the bridge again is refused, with or without `again`.
        again = await stack.author.post(
            f"{base}/{stack.equipment}/copy", json={"again": "keep", "dry_run": True}
        )
        assert again.status_code == 409
        assert again.json()["type"] == "repository-deprecated"
    finally:
        await cleanup(stack.tenants, stack.actors)
