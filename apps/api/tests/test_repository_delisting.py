"""ADR 0297: the platform's operators delist a repository (RFC 0038 section 6).

A delisted repository leaves Discover and its storefront, closes its preview and its browse, blocks
new copies, and stops update checks and reads for every library and visitor, which read it as
unpublished; libraries keep what they copied; its own members read and edit it and are told. The
operators' routes, the log, the notices to the Owners, the flip rules, and suspending an account.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import set_preview, set_visibility
from httpx import AsyncClient
from sqlalchemy import func, select
from test_author_route_audit import _calls, _routes

from lorenzo_api.config import get_settings
from lorenzo_api.dependencies import require_platform_operator_role
from lorenzo_api.main import app
from lorenzo_api.models import (
    Entity,
    Membership,
    MembershipRole,
    Notification,
    RepositoryCopy,
    RepositorySubscription,
)
from lorenzo_api.repository_delisting import SUSPENSION_REASON

OPERATORS = ("platform-operator",)


@dataclass
class Scene:
    """Armoury with one release (public or private), its Owner (`world.author`), a library holding
    an invitation to it (`world.table`, run by `world.gm`), a visitor with no library and an
    operator."""

    world: ReleaseWorld
    visitor: Actor
    operator: Actor
    word: str

    @property
    def repository(self) -> uuid.UUID:
        return self.world.repository

    @property
    def table(self) -> uuid.UUID:
        return self.world.table

    async def delist(self, reason: str = "It breaks the rules") -> Any:
        response = await self.operator.put(
            f"/admin/repositories/{self.repository}/delist", json={"reason": reason}
        )
        assert response.status_code == 200, response.text
        return response.json()

    async def relist(self) -> Any:
        response = await self.operator.delete(f"/admin/repositories/{self.repository}/delist")
        assert response.status_code == 200, response.text
        return response.json()

    async def done(self) -> None:
        await self.world.done()
        await cleanup([], [self.visitor, self.operator])


async def _scene(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, public: bool = True, copied: bool = False
) -> Scene:
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
    if copied:
        await world.copy()
    visitor = await make_actor(raw_client, jwks, "visitor", roles=())
    operator = await make_actor(raw_client, jwks, "operator", roles=OPERATORS)
    return Scene(world, visitor, operator, word)


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


# --- Every reader, in every state ------------------------------------------------------------


async def _visitor_reads(scene: Scene) -> dict[str, int]:
    """What a signed-in user with no library gets, as a status for each thing to read."""
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


async def _holder_reads(scene: Scene) -> dict[str, int]:
    """What the library the repository invited gets, through its own routes."""
    g, t, r = scene.world.gm, scene.table, scene.repository
    base = f"/tenants/{t}/repositories/{r}"
    return {
        "profile": (await g.get(f"{base}/profile")).status_code,
        "releases": (await g.get(f"{base}/releases")).status_code,
        "preview": (await g.get(f"{base}/preview")).status_code,
        "browse": (await g.get(f"{base}/entities")).status_code,
        "groups": (await g.get(f"{base}/stat-groups")).status_code,
        "dependencies": (await g.get(f"{base}/dependencies")).status_code,
        "plan": (await g.get(f"{base}/copy-plan")).status_code,
        "copy": (await g.post(f"{base}/copy", json={"dry_run": True})).status_code,
    }


async def _member_reads(scene: Scene) -> dict[str, int]:
    """What the repository's own Owner gets, through its own routes."""
    a, r = scene.world.author, scene.repository
    return {
        "profile": (await a.get(f"/tenants/{r}/profile")).status_code,
        "entities": (await a.get(f"/tenants/{r}/entities")).status_code,
        "releases": (await a.get(f"/tenants/{r}/releases")).status_code,
        "release_preview": (await a.get(f"/tenants/{r}/release-preview")).status_code,
    }


@pytest.mark.parametrize("state", ["public", "private", "delisted public", "delisted private"])
async def test_every_reader_by_state(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, state: str
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, public="public" in state)
    try:
        if state.startswith("delisted"):
            await scene.delist()
        delisted = state.startswith("delisted")
        public = state.endswith("public")

        visitor = await _visitor_reads(scene)
        seen = {k: v for k, v in visitor.items() if k != "listed"}
        if public and not delisted:
            assert visitor["listed"] == 1
            # No cover was set: the repository is there and the picture is not.
            assert seen == dict.fromkeys(seen, 200) | {"cover": 404}
        else:
            assert visitor["listed"] == 0
            assert seen == dict.fromkeys(seen, 404), state

        holder = await _holder_reads(scene)
        # The library the repository invited reads it, public or not, until it is delisted.
        assert holder == dict.fromkeys(holder, 404 if delisted else 200), state

        # Its own members read it, whatever it is.
        member = await _member_reads(scene)
        assert member == dict.fromkeys(member, 200), state
    finally:
        await scene.done()


async def test_an_operator_is_no_member_and_finds_a_delisted_repository_in_the_admin_list(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.delist("Plagiarised")
        # The operators' own page of it, and nothing else of its content.
        page = await scene.operator.get("/admin/repositories/delisted")
        assert page.status_code == 200
        assert str(scene.repository) in [r["id"] for r in page.json()["items"]]
        assert (await scene.operator.get(f"/tenants/{scene.repository}/profile")).status_code == 404
    finally:
        await scene.done()


# --- A delisted repository blocks new copies and keeps the copies that were made ---------------


async def test_a_delisted_repository_blocks_new_copies_by_any_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    library = await stranger.create_tenant("A stranger's table")
    try:
        base = f"/tenants/{library}/repositories/{scene.repository}"
        await scene.delist()
        # A library with no invitation, for which the repository is public, and the invited one.
        for lib in (stranger, scene.world.gm):
            where = (
                base
                if lib is stranger
                else f"/tenants/{scene.table}/repositories/{scene.repository}"
            )
            assert (await lib.get(f"{where}/copy-plan")).status_code == 404
            refused = await lib.post(f"{where}/copy", json={})
            assert refused.status_code == 404
            assert refused.json()["type"] == "repository-not-found"
        assert await _entity_names(library) == []
        assert await _entity_names(scene.table) == []
        async with admin_session_factory() as session:
            grants = await session.scalar(
                select(func.count())
                .select_from(RepositorySubscription)
                .where(RepositorySubscription.repository_tenant_id == scene.repository)
            )
        assert grants == 1  # the invitation, and no grant of the stranger's own

        # Listed again, the same copy is made.
        await scene.relist()
        copied = await stranger.post(f"{base}/copy", json={})
        assert copied.status_code == 201, copied.text
    finally:
        await scene.done()
        await cleanup([library], [stranger])


async def test_libraries_keep_their_copies_and_update_checks_stop_until_it_is_listed_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, copied=True)
    # A library that copied it by itself, with no invitation, is the same.
    copier = await make_actor(raw_client, fake_jwks_server, "copier")
    library = await copier.create_tenant("A copier's table")
    try:
        copied = await copier.post(
            f"/tenants/{library}/repositories/{scene.repository}/copy", json={}
        )
        assert copied.status_code == 201, copied.text
        before = await _entity_names(scene.table)
        assert before == ["Dagger", "Longsword", "Orc"]

        # The Owner releases once more, then the repository is delisted.
        async with admin_session_factory() as session:
            (await session.get_one(Entity, scene.world.ids["Orc"])).name = "Ogre"
            await session.commit()
        await scene.world.publish(label="3.0")
        await scene.delist()

        for lib, actor in ((scene.table, scene.world.gm), (library, copier)):
            base = f"/tenants/{lib}/repositories/{scene.repository}"
            checked = await actor.get(f"{base}/updates")
            assert checked.status_code == 404, checked.text
            assert checked.json()["type"] == "repository-not-found"
            applied = await actor.post(f"{base}/updates", json={"actions": []})
            assert applied.status_code == 404
            # What they copied is theirs, and stays.
            assert await _entity_names(lib) == before
            # In the library's list it reads as unpublished, with no release to take.
            listing = await actor.get(f"/tenants/{lib}/repositories")
            [row] = [
                i for i in listing.json()["items"] if i["repository"]["id"] == str(scene.repository)
            ]
            assert row["repository"]["published_at"] is None
            assert row["copied_at"] is not None
            assert row["current_release"] is None
        async with admin_session_factory() as session:
            records = await session.scalar(
                select(func.count())
                .select_from(RepositoryCopy)
                .where(RepositoryCopy.repository_tenant_id == scene.repository)
            )
        assert records == 2

        # Listed again, the update check serves the content again.
        await scene.relist()
        for lib, actor in ((scene.table, scene.world.gm), (library, copier)):
            checked = await actor.get(f"/tenants/{lib}/repositories/{scene.repository}/updates")
            assert checked.status_code == 200, checked.text
            assert checked.json()["release"]["label"] == "3.0"
            assert [c["name"] for c in checked.json()["changed"]] == ["Orc"]
    finally:
        await scene.done()
        await cleanup([library], [copier])


async def test_a_release_of_a_delisted_repository_tells_no_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, copied=True)
    try:
        before = len(await _notices(scene.world.gm, "repository_updated"))
        await scene.delist()
        await scene.world.publish(label="3.0")
        assert len(await _notices(scene.world.gm, "repository_updated")) == before
        # Listed again, a release is announced as before.
        await scene.relist()
        await scene.world.publish(label="4.0")
        assert len(await _notices(scene.world.gm, "repository_updated")) == before + 1
    finally:
        await scene.done()


# --- Members -----------------------------------------------------------------------------------


async def test_members_read_and_edit_a_delisted_repository_and_see_that_it_is(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
    author = await make_actor(raw_client, fake_jwks_server, "author")
    try:
        async with admin_session_factory() as session:
            session.add_all(
                [
                    Membership(
                        tenant_id=scene.repository,
                        user_id=organizer.user_id,
                        role=MembershipRole.ORGA,
                    ),
                    Membership(
                        tenant_id=scene.repository,
                        user_id=author.user_id,
                        role=MembershipRole.AUTHOR,
                    ),
                ]
            )
            await session.commit()
        profile_url = f"/tenants/{scene.repository}/profile"
        for member in (scene.world.author, organizer, author):
            assert (await member.get(profile_url)).json()["delisted"] is None
        await scene.delist("It breaks the rules")

        for member in (scene.world.author, organizer, author):
            profile = (await member.get(profile_url)).json()
            assert profile["delisted"]["reason"] == "It breaks the rules"
            assert profile["delisted"]["at"]
            # What the repository's members read says nobody's name: the platform's operators.
            assert set(profile["delisted"]) == {"reason", "at"}
            assert (await member.get(f"/tenants/{scene.repository}/entities")).status_code == 200

        # They fix it: the Owner edits the profile and releases, an Author changes entries.
        edited = await scene.world.author.patch(profile_url, json={"summary": "Cleaned up"})
        assert edited.status_code == 200
        assert edited.json()["summary"] == "Cleaned up"
        assert edited.json()["delisted"]["reason"] == "It breaks the rules"
        made = await author.post(
            f"/tenants/{scene.repository}/entities", json={"name": "Spear", "kinds": ["item"]}
        )
        assert made.status_code == 201, made.text
        assert (await scene.world.publish(label="3.0"))["label"] == "3.0"

        # Nobody else is told, and a visitor's and a holder's profile never carry it.
        v = await scene.visitor.get(f"/repositories/{scene.repository}/profile")
        h = await scene.world.gm.get(
            f"/tenants/{scene.table}/repositories/{scene.repository}/profile"
        )
        assert (v.status_code, h.status_code) == (404, 404)
        await scene.relist()
        for reader in (
            await scene.visitor.get(f"/repositories/{scene.repository}/profile"),
            await scene.world.gm.get(
                f"/tenants/{scene.table}/repositories/{scene.repository}/profile"
            ),
            await scene.visitor.get(f"/discover/repositories/{scene.repository}"),
        ):
            assert reader.status_code == 200
            # Nothing in what a visitor or a library reads says the word, delisted or not.
            assert "delisted" not in str(reader.json())
        assert (await scene.world.author.get(profile_url)).json()["delisted"] is None
    finally:
        await scene.done()
        await cleanup([], [organizer, author])


# --- The operators' routes ---------------------------------------------------------------------


async def test_delist_is_idempotent_and_a_second_delist_updates_the_reason(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    second = await make_actor(raw_client, fake_jwks_server, "second", roles=OPERATORS)
    try:
        first = await scene.delist("Reported twice")
        assert first["id"] == str(scene.repository)
        assert first["name"] == f"Armoury {scene.word}"
        assert first["reason"] == "Reported twice"
        assert first["delisted_by"] == str(scene.operator.user_id)

        again = await second.put(
            f"/admin/repositories/{scene.repository}/delist", json={"reason": "  Verified  "}
        )
        assert again.status_code == 200
        assert again.json()["reason"] == "Verified"
        assert again.json()["delisted_by"] == str(second.user_id)
        # Still delisted since the first time.
        assert again.json()["delisted_at"] == first["delisted_at"]

        page = (await scene.operator.get("/admin/repositories/delisted")).json()
        [row] = [r for r in page["items"] if r["id"] == str(scene.repository)]
        assert row["reason"] == "Verified"
        assert set(row) == {
            "id",
            "name",
            "slug",
            "reason",
            "delisted_at",
            "delisted_by",
            "delisted_by_nickname",
        }
    finally:
        await scene.done()
        await cleanup([], [second])


@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
async def test_a_reason_of_one_to_five_hundred_characters_is_required(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, reason: str
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        url = f"/admin/repositories/{scene.repository}/delist"
        assert (await scene.operator.put(url, json={"reason": reason})).status_code == 422
        assert (await scene.operator.put(url, json={})).status_code == 422
        page = (await scene.operator.get("/admin/repositories/delisted")).json()
        assert str(scene.repository) not in [r["id"] for r in page["items"]]
        # Five hundred is the most.
        assert (await scene.operator.put(url, json={"reason": "x" * 500})).status_code == 200
    finally:
        await scene.done()


async def test_relisting_restores_everything_and_is_a_no_op_for_a_listed_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        listed = await _visitor_reads(scene)
        holds = await _holder_reads(scene)
        assert listed["listed"] == 1

        # Not delisted: nothing to do, and nothing happens.
        nothing = await scene.relist()
        assert nothing["relisted"] is False
        assert len(await _notices(scene.world.author, "repository_relisted")) == 0

        await scene.delist()
        assert (await _visitor_reads(scene))["listed"] == 0
        done = await scene.relist()
        assert (done["id"], done["relisted"]) == (str(scene.repository), True)
        assert await _visitor_reads(scene) == listed
        assert await _holder_reads(scene) == holds
        page = (await scene.operator.get("/admin/repositories/delisted")).json()
        assert str(scene.repository) not in [r["id"] for r in page["items"]]
        # Again: a no-op.
        assert (await scene.relist())["relisted"] is False
    finally:
        await scene.done()


async def test_the_delisting_routes_need_the_platform_operator_role_and_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        url = f"/admin/repositories/{scene.repository}/delist"
        for actor in (scene.visitor, scene.world.author, scene.world.gm):
            assert (await actor.put(url, json={"reason": "x"})).status_code == 403
            assert (await actor.delete(url)).status_code == 403
            assert (await actor.get("/admin/repositories/delisted")).status_code == 403
        page = (await scene.operator.get("/admin/repositories/delisted")).json()
        assert str(scene.repository) not in [r["id"] for r in page["items"]]

        # An id that is no repository, and a library's, are the same 404.
        for missing in (uuid.uuid4(), scene.table):
            put = await scene.operator.put(
                f"/admin/repositories/{missing}/delist", json={"reason": "x"}
            )
            assert put.status_code == 404
            assert put.json()["type"] == "repository-not-found"
            assert (
                await scene.operator.delete(f"/admin/repositories/{missing}/delist")
            ).status_code == 404
    finally:
        await scene.done()


def test_every_admin_route_asks_for_the_platform_operator_role() -> None:
    """The audit of `/admin`: a route there that forgot the gate would be open to anyone."""
    found = {
        (method, route.path): require_platform_operator_role in list(_calls(route.dependant))
        for route in _routes(app.router)
        if route.path.startswith("/admin")
        for method in route.methods
    }
    assert len(found) >= 8
    assert [k for k, gated in found.items() if not gated] == []
    for key in (
        ("GET", "/admin/repositories/delisted"),
        ("PUT", "/admin/repositories/{repository_id}/delist"),
        ("DELETE", "/admin/repositories/{repository_id}/delist"),
    ):
        assert key in found


# --- The Owners are told, once; the log says so -------------------------------------------------


async def test_the_owners_are_told_once_and_the_log_records_both_ways(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    co_owner = await make_actor(raw_client, fake_jwks_server, "co-owner")
    organizer = await make_actor(raw_client, fake_jwks_server, "organizer")
    try:
        async with admin_session_factory() as session:
            session.add_all(
                [
                    Membership(
                        tenant_id=scene.repository,
                        user_id=co_owner.user_id,
                        role=MembershipRole.OWNER,
                    ),
                    Membership(
                        tenant_id=scene.repository,
                        user_id=organizer.user_id,
                        role=MembershipRole.ORGA,
                    ),
                ]
            )
            await session.commit()

        await scene.delist("Copied from a publisher")
        await scene.delist("Copied from a publisher")  # again, as the operators may
        await scene.delist("Copied from somebody else")  # and again with other words
        name = f"Armoury {scene.word}"
        for owner in (scene.world.author, co_owner):
            [told] = await _notices(owner, "repository_delisted")
            assert told["title"] == f"{name} was taken off Discover and closed to new copies"
            assert "Reason: Copied from a publisher" in told["body"]
            assert "keep their copies" in told["body"]
            assert "cannot update from it until it is listed again" in told["body"]
        # An Organizer is not an Owner, a library that holds it is told nothing.
        assert await _notices(organizer, "repository_delisted") == []
        assert await _notices(scene.world.gm, "repository_delisted") == []

        await scene.relist()
        await scene.relist()
        for owner in (scene.world.author, co_owner):
            [back] = await _notices(owner, "repository_relisted")
            assert back["title"] == f"{name} is listed again"
        assert await _notices(organizer, "repository_relisted") == []

        log = await scene.world.author.get(f"/tenants/{scene.repository}/activity-log")
        entries = [e for e in log.json()["items"] if e["action"].startswith("repository.")]
        delisted = [e for e in entries if e["action"] == "repository.delisted"]
        relisted = [e for e in entries if e["action"] == "repository.relisted"]
        # Each delist is logged, with the operator who made it; a no-op relist is not.
        assert len(delisted) == 3
        assert {e["actor_id"] for e in delisted + relisted} == {str(scene.operator.user_id)}
        assert len(relisted) == 1
        # Words the operators wrote are not in the log, which Organizers read too.
        assert "copied" not in str(log.json()).lower().replace("copied_", "")
    finally:
        await scene.done()
        await cleanup([], [co_owner, organizer])


# --- Making it public while it is delisted ----------------------------------------------------


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def test_a_delisted_repository_cannot_be_made_public_and_the_check_says_why(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, public=False)
    try:
        owner, r = scene.world.author, scene.repository
        assert (await owner.get(f"/tenants/{r}/flip-check")).json()["delisted"] is None
        await scene.delist("Hateful content")

        check = (await owner.get(f"/tenants/{r}/flip-check")).json()
        assert check["delisted"]["reason"] == "Hateful content"
        assert set(check["delisted"]) == {"reason", "at"}

        refused = await owner.put(f"/tenants/{r}/public", json={"summary": "Every blade"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-delisted"
        assert "Hateful content" in refused.json()["detail"]
        assert "tenant" not in (refused.json()["title"] + refused.json()["detail"]).lower()
        # Nothing was kept, not even the summary beside it.
        profile = (await owner.get(f"/tenants/{r}/profile")).json()
        assert (profile["visibility"], profile["summary"]) == ("private", "")

        await scene.relist()
        made = await owner.put(f"/tenants/{r}/public", json={"summary": "Every blade"})
        assert made.status_code == 200, made.text
    finally:
        await scene.done()


async def test_a_public_repository_that_is_delisted_can_still_be_made_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.delist()
        made = await scene.world.author.delete(f"/tenants/{scene.repository}/public")
        assert made.status_code == 200, made.text
        profile = (await scene.world.author.get(f"/tenants/{scene.repository}/profile")).json()
        assert profile["visibility"] == "private"
        assert profile["delisted"] is not None
        # It stays delisted: private and closed, and listed nowhere.
        assert (await _visitor_reads(scene))["listed"] == 0
    finally:
        await scene.done()


async def test_discover_counts_nothing_of_a_delisted_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    scene = await _scene(raw_client, fake_jwks_server)
    try:
        await scene.world.author.patch(
            f"/tenants/{scene.repository}/profile", json={"tags": [f"t{scene.word}"]}
        )

        def counts(body: dict[str, Any]) -> dict[str, int]:
            return {t["value"]: t["count"] for t in body["tags"]}

        facets = (await scene.visitor.get("/discover/facets")).json()
        assert counts(facets)[f"t{scene.word}"] == 1
        await scene.delist()
        facets = (await scene.visitor.get("/discover/facets")).json()
        assert f"t{scene.word}" not in counts(facets)
        found = await scene.visitor.get("/discover/repositories", params={"tag": f"t{scene.word}"})
        assert found.json()["total"] == 0
    finally:
        await scene.done()


# --- Suspending an account -------------------------------------------------------------------


async def _delisted_ids(operator: Actor, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    found: set[uuid.UUID] = set()
    page = 1
    while True:
        response = await operator.get("/admin/repositories/delisted", params={"page": page})
        body = response.json()
        found |= {uuid.UUID(r["id"]) for r in body["items"]}
        if page * body["size"] >= body["total"]:
            break
        page += 1
    return found & set(ids)


async def test_suspending_an_account_delists_the_repositories_it_owns_and_no_others(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    operator = await make_actor(raw_client, fake_jwks_server, "operator", roles=OPERATORS)
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    other = await make_actor(raw_client, fake_jwks_server, "other")
    mine = await owner.create_tenant("Mine", kind="repository")
    shared = await owner.create_tenant("Shared with another Owner", kind="repository")
    organised = await other.create_tenant("Organised by the owner", kind="repository")
    authored = await other.create_tenant("Authored by the owner", kind="repository")
    play = await owner.create_tenant("A table")
    try:
        async with admin_session_factory() as session:
            session.add_all(
                [
                    Membership(tenant_id=shared, user_id=other.user_id, role=MembershipRole.OWNER),
                    Membership(
                        tenant_id=organised, user_id=owner.user_id, role=MembershipRole.ORGA
                    ),
                    Membership(
                        tenant_id=authored, user_id=owner.user_id, role=MembershipRole.AUTHOR
                    ),
                ]
            )
            await session.commit()
        everything = [mine, shared, organised, authored, play]

        suspended = await operator.put(
            f"/admin/users/{owner.user_id}/suspend", json={"reason": "spam"}
        )
        assert suspended.status_code == 200

        # What the account owns is delisted, with the words of a suspension; what it only organises
        # or authors, and its library, are not.
        assert await _delisted_ids(operator, everything) == {mine, shared}
        page = (await operator.get("/admin/repositories/delisted")).json()
        reasons = {r["id"]: r["reason"] for r in page["items"]}
        assert reasons[str(mine)] == SUSPENSION_REASON == "Its Owner's account was suspended"
        assert reasons[str(shared)] == SUSPENSION_REASON
        # The other Owner of a shared one is told, once.
        [told] = await _notices(other, "repository_delisted")
        assert (
            told["title"]
            == "Shared with another Owner was taken off Discover and closed to new copies"
        )
        assert SUSPENSION_REASON in told["body"]

        # Again: the same, and nobody is told twice.
        again = await operator.put(f"/admin/users/{owner.user_id}/suspend", json={"reason": "spam"})
        assert again.status_code == 200
        assert len(await _notices(other, "repository_delisted")) == 1

        # Lifting the suspension does not list them again.
        lifted = await operator.delete(f"/admin/users/{owner.user_id}/suspend")
        assert lifted.status_code == 200
        assert await _delisted_ids(operator, everything) == {mine, shared}

        # An operator does, with the same call as ever.
        relisted = await operator.delete(f"/admin/repositories/{mine}/delist")
        assert relisted.json()["relisted"] is True
        assert await _delisted_ids(operator, everything) == {shared}
    finally:
        await cleanup([mine, shared, organised, authored, play], [operator, owner, other])


async def test_a_suspension_leaves_the_words_of_an_operator_who_delisted_first(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    operator = await make_actor(raw_client, fake_jwks_server, "operator", roles=OPERATORS)
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Mine", kind="repository")
    try:
        put = await operator.put(
            f"/admin/repositories/{repository}/delist", json={"reason": "Plagiarised"}
        )
        assert put.status_code == 200
        before = put.json()
        assert (
            await operator.put(f"/admin/users/{owner.user_id}/suspend", json={})
        ).status_code == 200
        page = (await operator.get("/admin/repositories/delisted")).json()
        [row] = [r for r in page["items"] if r["id"] == str(repository)]
        assert (row["reason"], row["delisted_at"]) == ("Plagiarised", before["delisted_at"])
        # Told once: by the delist that came first (read in the database, for the account is
        # suspended and cannot ask).
        async with admin_session_factory() as session:
            told = await session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == owner.user_id,
                    Notification.type == "repository_delisted",
                )
            )
        assert told == 1
    finally:
        await cleanup([repository], [operator, owner])
