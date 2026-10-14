"""ADR 0292: Discover, the listing of public repositories, its facets and a repository's storefront,
and the facts of the current release that a publish writes for it to list.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import release_world
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import in_tenant, set_visibility
from httpx import AsyncClient
from sqlalchemy import delete, select, text

from lorenzo_api.db import async_session_factory
from lorenzo_api.models import Entity, RepositoryProfile, Tenant, TenantKind


class _Shelf:
    """Repositories made straight in the database, all with one unique word in their names so a
    test sees only its own however many others the database holds."""

    def __init__(self) -> None:
        self.word = uuid.uuid4().hex[:10]
        self.ids: list[uuid.UUID] = []

    async def add(
        self,
        name: str,
        *,
        visibility: str = "public",
        published: bool = True,
        released: bool = True,
        summary: str = "",
        tags: tuple[str, ...] = (),
        system: str | None = None,
        languages: tuple[str, ...] = ("en",),
        age_days: int = 0,
        description: str = "",
    ) -> uuid.UUID:
        async with admin_session_factory() as session:
            tenant = Tenant(
                name=f"{name} {self.word}",
                kind=TenantKind.REPOSITORY,
                description=description,
                published_at=datetime.now(UTC) if published else None,
            )
            session.add(tenant)
            await session.flush()
            session.add(
                RepositoryProfile(
                    tenant_id=tenant.id,
                    visibility=visibility,
                    summary=summary,
                    tags=list(tags),
                    system=system,
                    languages=list(languages),
                    release_label="1.0" if released else None,
                    released_at=datetime.now(UTC) - timedelta(days=age_days) if released else None,
                    entry_count=12 if released else None,
                    stat_definition_count=3 if released else None,
                )
            )
            await session.commit()
            self.ids.append(tenant.id)
            return tenant.id

    async def done(self) -> None:
        async with admin_session_factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id.in_(self.ids)))
            await session.commit()


async def _visitor(raw_client: AsyncClient, jwks: FakeJwksServer) -> Actor:
    return await make_actor(raw_client, jwks, "visitor", roles=())


async def _names(visitor: Actor, shelf: _Shelf, **params: Any) -> list[str]:
    response = await visitor.get("/discover/repositories", params={"q": shelf.word} | params)
    assert response.status_code == 200, response.text
    return [i["name"].removesuffix(f" {shelf.word}") for i in response.json()["items"]]


# --- What is listed -----------------------------------------------------------------------------


async def test_only_public_published_repositories_with_a_release_are_listed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        await shelf.add("Listed")
        await shelf.add("Private", visibility="private")
        await shelf.add("Draft", published=False)
        await shelf.add("Unreleased", released=False)

        response = await visitor.get("/discover/repositories", params={"q": shelf.word})
        assert response.status_code == 200
        body = response.json()
        assert [i["name"] for i in body["items"]] == [f"Listed {shelf.word}"]
        assert body["total"] == 1
        item = body["items"][0]
        assert (item["release"]["label"], item["entries"], item["stat_definitions"]) == (
            "1.0",
            12,
            3,
        )
        assert item["has_cover"] is False
    finally:
        await shelf.done()
        await cleanup([], [visitor])


async def test_listing_needs_a_signed_in_user_and_not_a_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf = _Shelf()
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("A table")
    try:
        await shelf.add("Armoury")
        assert (await raw_client.get("/discover/repositories")).status_code == 401
        for path in ("/discover/facets", f"/discover/repositories/{uuid.uuid4()}"):
            assert (await raw_client.get(path)).status_code == 401, path
        # A user who has a library reads it the same.
        response = await gm.get("/discover/repositories", params={"q": shelf.word})
        assert [i["name"] for i in response.json()["items"]] == [f"Armoury {shelf.word}"]
    finally:
        await shelf.done()
        await cleanup([table], [gm])


# --- Search, filters and order --------------------------------------------------------------------


async def test_search_matches_the_name_the_summary_and_the_tags_without_regard_to_case(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        await shelf.add("Armoury")
        await shelf.add("Bestiary", summary="Beasts of the Mistral coast")
        await shelf.add("Cities", tags=("mistral",))
        await shelf.add("Dungeons")

        async def found(word: str) -> list[str]:
            response = await visitor.get("/discover/repositories", params={"q": f"{word}"})
            return sorted(
                i["name"].removesuffix(f" {shelf.word}")
                for i in response.json()["items"]
                if shelf.word in i["name"]
            )

        assert await found("ARMOURY") == ["Armoury"]
        assert await found("mistral") == ["Bestiary", "Cities"]
        assert await found(shelf.word) == ["Armoury", "Bestiary", "Cities", "Dungeons"]
        # A wildcard in the word is a plain character.
        assert await found("%") == []
        assert await found("_") == []
    finally:
        await shelf.done()
        await cleanup([], [visitor])


async def test_the_tag_the_system_and_the_language_narrow_the_listing_exactly(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        await shelf.add("A", tags=("osr", "weapons"), system="Pathfinder", languages=("en", "de"))
        await shelf.add("B", tags=("osr",), system="dnd5e", languages=("en",))
        await shelf.add("C", tags=("horror",), system="dnd5e", languages=("de",))

        assert await _names(visitor, shelf, tag="osr") == ["A", "B"]
        assert await _names(visitor, shelf, tag="OSR") == ["A", "B"]
        assert await _names(visitor, shelf, tag="osr", system="dnd5e") == ["B"]
        assert await _names(visitor, shelf, system="PATHFINDER") == ["A"]
        assert await _names(visitor, shelf, language="de") == ["A", "C"]
        assert await _names(visitor, shelf, tag="osr", language="de") == ["A"]
        assert await _names(visitor, shelf, tag="weap") == []  # exact, not a part
    finally:
        await shelf.done()
        await cleanup([], [visitor])


async def test_the_order_is_by_name_or_by_the_latest_release_and_never_by_popularity(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        await shelf.add("banana", age_days=1)
        await shelf.add("Apple", age_days=30)
        await shelf.add("cherry", age_days=10)

        assert await _names(visitor, shelf) == ["Apple", "banana", "cherry"]
        assert await _names(visitor, shelf, sort="released") == ["banana", "cherry", "Apple"]
        assert (
            await visitor.get("/discover/repositories", params={"sort": "popular"})
        ).status_code == 422
    finally:
        await shelf.done()
        await cleanup([], [visitor])


async def test_a_page_is_capped_and_a_listing_goes_only_so_deep(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        for n in range(7):
            await shelf.add(f"Repository {n}")
        url = "/discover/repositories"
        small = (await visitor.get(url, params={"q": shelf.word, "size": 3, "page": 2})).json()
        assert (small["total"], small["page"], small["size"], len(small["items"])) == (7, 2, 3, 3)
        last = (await visitor.get(url, params={"q": shelf.word, "size": 3, "page": 3})).json()
        assert len(last["items"]) == 1

        # More than the cap is the cap, whatever is asked.
        big = (await visitor.get(url, params={"q": shelf.word, "size": 5000})).json()
        assert "size" in big, big
        assert (big["size"], len(big["items"])) == (50, 7)

        # And a listing goes at most a thousand deep.
        deep = await visitor.get(url, params={"size": 50, "page": 21})
        assert deep.status_code == 422
        assert deep.json()["type"] == "discover-too-deep"
        assert "Narrow it" in deep.json()["detail"]
        ok = await visitor.get(url, params={"size": 50, "page": 20})
        assert ok.status_code == 200
    finally:
        await shelf.done()
        await cleanup([], [visitor])


async def test_the_facets_count_what_the_listed_repositories_say_of_themselves(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    tag, system = f"t{shelf.word}", f"s{shelf.word}"
    try:
        await shelf.add("A", tags=(tag,), system=system.upper(), languages=("en", "de"))
        await shelf.add("B", tags=(tag,), system=system, languages=("en",))
        await shelf.add("C", tags=(tag,), visibility="private", system=system)
        facets = (await visitor.get("/discover/facets")).json()
        assert facets["enabled"] is False  # the deployment does not accept public repositories

        assert {"value": tag, "count": 2} in facets["tags"]
        assert {"value": system, "count": 2} in facets["systems"]  # cases fold
        by_language = {f["value"]: f["count"] for f in facets["languages"]}
        assert by_language["en"] >= 2 and by_language["de"] >= 1
        assert len(facets["tags"]) <= 100
    finally:
        await shelf.done()
        await cleanup([], [visitor])


# --- The storefront ----------------------------------------------------------


async def test_a_storefront_is_the_listing_entry_the_description_and_the_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    shelf, visitor = _Shelf(), await _visitor(raw_client, fake_jwks_server)
    try:
        listed = await shelf.add(
            "Armoury",
            summary="Every blade",
            description="A long description of the armoury.",
            system="dnd5e",
        )
        private = await shelf.add("Secret", visibility="private")
        draft = await shelf.add("Draft", published=False)

        page = await visitor.get(f"/discover/repositories/{listed}")
        assert page.status_code == 200, page.text
        body = page.json()
        assert body["item"]["id"] == str(listed)
        assert body["description"] == "A long description of the armoury."
        assert (body["profile"]["summary"], body["profile"]["visibility"]) == (
            "Every blade",
            "public",
        )
        assert body["profile"]["preview"] == "showcase"
        for hidden in (private, draft, uuid.uuid4()):
            gone = await visitor.get(f"/discover/repositories/{hidden}")
            assert gone.status_code == 404
            assert gone.json()["type"] == "repository-not-found"
    finally:
        await shelf.done()
        await cleanup([], [visitor])


# --- The facts a publish writes ----------------------------------------------------------


async def test_a_publish_a_rollback_and_a_relabel_keep_the_listing_facts_of_the_current_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    visitor = await _visitor(raw_client, fake_jwks_server)
    world.actors.append(visitor)
    try:
        await set_visibility([world.repository], "public")

        async def entry() -> dict[str, Any] | None:
            response = await visitor.get(f"/discover/repositories/{world.repository}")
            return response.json()["item"] if response.status_code == 200 else None

        assert await entry() is None  # public, but nothing released yet
        await world.publish(label="1.0")
        first = await entry()
        assert first is not None
        # Armoury: three entries and a stat group of four definitions.
        assert (first["release"]["label"], first["entries"], first["stat_definitions"]) == (
            "1.0",
            3,
            4,
        )

        async with admin_session_factory() as session:
            session.add(Entity(tenant_id=world.repository, name="Spear"))
            await session.commit()
        await world.publish(label="2.0")
        second = await entry()
        assert second is not None
        assert (second["release"]["label"], second["entries"]) == ("2.0", 4)

        releases = {r["label"]: r for r in await world.releases()}
        back = await world.author.put(
            f"/tenants/{world.repository}/releases/{releases['1.0']['id']}/current",
            json={"acknowledge_breaking": True},
        )
        assert back.status_code == 200, back.text
        third = await entry()
        assert third is not None
        assert (third["release"]["label"], third["entries"]) == ("1.0", 3)

        renamed = await world.author.patch(
            f"/tenants/{world.repository}/releases/{releases['1.0']['id']}",
            json={"label": "1.0 final"},
        )
        assert renamed.status_code == 200, renamed.text
        fourth = await entry()
        assert fourth is not None and fourth["release"]["label"] == "1.0 final"
    finally:
        await world.done()


# --- The wall ----------------------------------------------------------


async def test_the_listing_reads_the_profile_of_a_public_repository_and_nothing_else_of_it() -> (
    None
):
    """`discover_read` opens the profile of a listed repository to any request, with no library and
    no gated read, and no table beside it."""
    shelf = _Shelf()
    try:
        listed = await shelf.add("Armoury", summary="Every blade")
        private = await shelf.add("Secret", visibility="private", summary="Hidden")
        draft = await shelf.add("Draft", published=False)
        unreleased = await shelf.add("Unreleased", released=False)
        async with admin_session_factory() as session:
            session.add(Entity(tenant_id=listed, name="Sword"))
            await session.commit()

        async with async_session_factory() as session:
            await in_tenant(session, uuid.UUID(int=0))
            seen = set(
                await session.scalars(
                    select(RepositoryProfile.tenant_id).where(
                        RepositoryProfile.tenant_id.in_([listed, private, draft, unreleased])
                    )
                )
            )
            assert seen == {listed}
            assert list(await session.scalars(select(Entity.name))) == []
            assert (await session.scalar(text("SELECT count(*) FROM repository_release"))) == 0
    finally:
        await shelf.done()
