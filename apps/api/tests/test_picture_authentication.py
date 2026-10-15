"""ADR 0300, RFC 0038 section 6 item 7: a private repository's picture is for a signed-in user.

`GET /tenants/{id}/picture` stays open for a play tenant and for a public repository, and asks for
a token for a private one. A request with no token gets the answer of a tenant that has no
picture, so nothing tells a private repository from an unknown id. Any signed-in user may read it,
a member or not: authentication alone. The cover routes ask for a token already, and a test holds
them to it.
"""

import uuid
from collections.abc import Iterator

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import set_visibility
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import delete
from test_public_repository_read import _public_world

from lorenzo_api.dependencies import get_current_user, get_optional_user
from lorenzo_api.main import app
from lorenzo_api.models import TenantProfilePicture

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-picture"
COVER = b"\x89PNG\r\n\x1a\n" + b"fake-cover"


def _file(content: bytes = PNG) -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("p.png", content, "image/png")}


async def _tenant_with_picture(owner: Actor, name: str, *, kind: str) -> uuid.UUID:
    tenant = await owner.create_tenant(name, kind=kind)
    response = await owner.put(f"/tenants/{tenant}/picture", files=_file())
    assert response.status_code == 204, response.text
    return tenant


async def test_a_private_repositorys_picture_is_closed_to_a_request_with_no_token(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    try:
        response = await raw_client.get(f"/tenants/{private}/picture")

        assert response.status_code == 404
        assert PNG not in response.content
    finally:
        await cleanup([private], [owner])


async def test_a_request_with_no_token_cannot_tell_a_private_repository_from_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The answer for a private repository that has a picture, one that has none, a play tenant
    without one and an id nobody has are the same but for the id they name."""
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    bare = await owner.create_tenant("No picture", kind="repository")
    table = await owner.create_tenant("Table")
    unknown = uuid.uuid4()
    try:
        answers = []
        for tenant in (private, bare, table, unknown):
            response = await raw_client.get(f"/tenants/{tenant}/picture")
            body = response.json()
            answers.append(
                (
                    response.status_code,
                    response.headers["content-type"],
                    body["type"],
                    body["title"],
                    body["detail"].replace(str(tenant), "<id>"),
                )
            )

        assert len(set(answers)) == 1
        assert answers[0][0] == 404
    finally:
        await cleanup([private, bare, table], [owner])


async def test_a_signed_in_user_reads_a_private_repositorys_picture_member_or_not(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger", roles=())
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    try:
        for reader in (owner, stranger):
            response = await reader.get(f"/tenants/{private}/picture")

            assert response.status_code == 200, response.text
            assert response.content == PNG
            assert response.headers["content-type"] == "image/png"
    finally:
        await cleanup([private], [owner, stranger])


async def test_a_public_repositorys_picture_stays_open(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    public = await _tenant_with_picture(owner, "Public", kind="repository")
    try:
        await set_visibility([public], "public")

        response = await raw_client.get(f"/tenants/{public}/picture")
        assert response.status_code == 200
        assert response.content == PNG

        await set_visibility([public], "private")
        assert (await raw_client.get(f"/tenants/{public}/picture")).status_code == 404
    finally:
        await cleanup([public], [owner])


async def test_a_play_tenants_picture_is_unchanged(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    table = await _tenant_with_picture(owner, "Table", kind="play")
    try:
        signed_out = await raw_client.get(f"/tenants/{table}/picture")
        signed_in = await owner.get(f"/tenants/{table}/picture")

        assert (signed_out.status_code, signed_out.content) == (200, PNG)
        assert (signed_in.status_code, signed_in.content) == (200, PNG)
    finally:
        await cleanup([table], [owner])


async def test_a_token_that_is_sent_is_checked_whatever_the_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    table = await _tenant_with_picture(owner, "Table", kind="play")
    try:
        for tenant in (private, table, uuid.uuid4()):
            response = await raw_client.get(
                f"/tenants/{tenant}/picture", headers={"Authorization": "Bearer not.a.token"}
            )

            assert response.status_code == 401, response.text
            assert response.headers["content-type"] == "application/problem+json"
    finally:
        await cleanup([private, table], [owner])


async def test_an_authorization_header_that_is_not_a_bearer_token_is_no_token(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    table = await _tenant_with_picture(owner, "Table", kind="play")
    try:
        basic = {"Authorization": "Basic abc"}

        assert (
            await raw_client.get(f"/tenants/{private}/picture", headers=basic)
        ).status_code == 404
        assert (await raw_client.get(f"/tenants/{table}/picture", headers=basic)).status_code == 200
    finally:
        await cleanup([private, table], [owner])


async def test_a_repository_that_loses_its_picture_is_a_404_for_everyone(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    private = await _tenant_with_picture(owner, "Private", kind="repository")
    try:
        async with admin_session_factory() as session:
            await session.execute(
                delete(TenantProfilePicture).where(TenantProfilePicture.tenant_id == private)
            )
            await session.commit()

        assert (await owner.get(f"/tenants/{private}/picture")).status_code == 404
        assert (await raw_client.get(f"/tenants/{private}/picture")).status_code == 404
    finally:
        await cleanup([private], [owner])


async def test_the_covers_ask_for_a_token_and_a_private_repositorys_stays_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Every cover route has asked for a token since ADR 0213 and 0287; none of them gains an open
    form here. A signed-in user with no library reads a public repository's cover and not a
    private one's."""
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    repository = await owner.create_tenant("Cover", kind="repository")
    library = await owner.create_tenant("Library")
    try:
        assert (
            await owner.put(f"/tenants/{repository}/profile/cover", files=_file(COVER))
        ).status_code == 204
        routes = (
            f"/tenants/{repository}/profile/cover",
            f"/repositories/{repository}/profile/cover",
            f"/tenants/{library}/repositories/{repository}/profile/cover",
        )

        for route in routes:
            response = await raw_client.get(route)
            assert response.status_code == 401, (route, response.text)
            assert COVER not in response.content

        assert (await owner.get(routes[0])).content == COVER
        assert (await visitor.get(routes[1])).status_code == 404
    finally:
        await cleanup([repository, library], [owner, visitor])


def _routes(router: object) -> Iterator[APIRoute]:
    for route in router.routes:  # type: ignore[attr-defined]
        if hasattr(route, "original_router"):
            yield from _routes(route.original_router)
        elif isinstance(route, APIRoute):
            yield route


def _dependency_calls(dependant: Dependant) -> set[object]:
    calls: set[object] = {dependant.call}
    for sub in dependant.dependencies:
        calls |= _dependency_calls(sub)
    return calls


def _calls_of(method: str, path: str) -> set[object]:
    for route in _routes(app.router):
        if route.path == path and method in route.methods:
            return _dependency_calls(route.dependant)
    raise AssertionError(f"no route {method} {path}")


def test_the_audit_of_which_picture_routes_ask_for_what() -> None:
    """The picture reads and what each asks for (ADR 0300). A route added to this list of the
    open ones, or one that stops asking, changes this on purpose."""
    # Signed in for a private repository, open otherwise: it takes a token if one is sent.
    assert get_optional_user in _calls_of("GET", "/tenants/{tenant_id}/picture")
    assert get_current_user not in _calls_of("GET", "/tenants/{tenant_id}/picture")

    # A campaign belongs to a play tenant, never to a repository (a trigger keeps it so), and a
    # user's picture is a user's: both stay open (ADR 0056).
    for path in (
        "/tenants/{tenant_id}/campaigns/{campaign_id}/picture",
        "/users/{user_id}/picture",
    ):
        calls = _calls_of("GET", path)
        assert get_current_user not in calls
        assert get_optional_user not in calls

    # Every cover asks for a signed-in user.
    for path in (
        "/tenants/{tenant_id}/profile/cover",
        "/tenants/{tenant_id}/repositories/{repository_id}/profile/cover",
        "/repositories/{repository_id}/profile/cover",
    ):
        assert get_current_user in _calls_of("GET", path), path


async def test_a_released_public_repositorys_picture_and_cover_are_there_for_a_visitor(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The picture needs no token and the cover any one; neither is held back once the repository
    is public and released."""
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        assert (
            await world.author.put(f"/tenants/{world.repository}/picture", files=_file())
        ).status_code == 204
        assert (
            await world.author.put(f"/tenants/{world.repository}/profile/cover", files=_file(COVER))
        ).status_code == 204

        for reader in (raw_client, visitor):
            response = await reader.get(f"/tenants/{world.repository}/picture")
            assert (response.status_code, response.content) == (200, PNG)
        cover = await visitor.get(f"/repositories/{world.repository}/profile/cover")
        assert (cover.status_code, cover.content) == (200, COVER)
        assert (
            await raw_client.get(f"/repositories/{world.repository}/profile/cover")
        ).status_code == 401
    finally:
        await world.done()
        await cleanup([], [visitor])
