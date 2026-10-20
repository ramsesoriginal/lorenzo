"""The route audit of RFC 0040 / ADR 0219: every route that asks for "a membership"
(`get_tenant_context`) is on exactly one of three lists, and an Author is refused where the list
says so.

A membership used to mean an administrator (the roles were Owner and Organizer), so a route that
asked for nothing more was an admin route by accident. With an Author, it is an authoring route, so
each route chooses. A new route that forgets to fails `test_every_membership_route_is_on_the_audit`
instead of silently handing an Author its power.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from _author_world import World, make_world
from _fake_jwks import FakeJwksServer
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient

from lorenzo_api.dependencies import get_tenant_admin_context, get_tenant_context
from lorenzo_api.main import app
from lorenzo_api.routers.stats import _vocabulary_gate

T = "/tenants/{tenant_id}"
STAT_DEFINITION = T + "/stat-definitions/{stat_definition_id}"
STAT_GROUP = T + "/stat-groups/{stat_group_id}"
ENTITY_COMPUTED = T + "/entities/{entity_id}/computed-stats"
REPOSITORY = T + "/repositories/{repository_id}"

# Any member, an Author too: editing content, and the reads that editing and checking need.
AUTHORING = {
    ("GET", T + "/calendar-imports/{source_key}/document"),
    ("POST", T + "/calendar-imports/plan"),
    ("POST", T + "/calendar-imports"),
    ("POST", T + "/calendars/{calendar_id}/observances"),
    ("POST", T + "/calendars"),
    ("GET", ENTITY_COMPUTED),
    ("DELETE", ENTITY_COMPUTED + "/{stat_definition_id}"),
    ("PUT", ENTITY_COMPUTED + "/{stat_definition_id}"),
    ("POST", ENTITY_COMPUTED + "/{stat_definition_id}/preview"),
    ("POST", T + "/items"),
    ("POST", T + "/items/bulk-add-prototype"),
    ("POST", T + "/items/bulk-remove-prototype"),
    ("POST", T + "/items/bulk-reparent-prototype"),
    ("DELETE", T + "/items/{entity_id}"),
    ("PATCH", T + "/items/{entity_id}"),
    ("PUT", T + "/items/{entity_id}/prototypes"),
    ("POST", T + "/entities"),
    ("DELETE", T + "/entities/{entity_id}"),
    ("PUT", T + "/entities/{entity_id}/kinds/{kind}"),
    ("DELETE", T + "/entities/{entity_id}/kinds/{kind}"),
    ("PUT", T + "/entities/{entity_id}/parents"),
    ("GET", T + "/profile"),
    ("GET", T + "/profile/cover"),
    ("GET", REPOSITORY + "/profile"),
    ("GET", REPOSITORY + "/profile/cover"),
    ("GET", T + "/release-preview"),
    ("GET", T + "/releases"),
    ("GET", T + "/attachments"),
    ("GET", T + "/repositories"),
    ("GET", REPOSITORY + "/contributions"),
    ("GET", REPOSITORY + "/copy-plan"),
    ("GET", REPOSITORY + "/dependencies"),
    ("GET", REPOSITORY + "/entities"),
    ("GET", REPOSITORY + "/entities/{entity_id}"),
    ("GET", REPOSITORY + "/entities/{entity_id}/pictures/{payload_id}"),
    ("GET", REPOSITORY + "/preview"),
    ("GET", T + "/showcase"),
    ("GET", REPOSITORY + "/releases"),
    ("GET", REPOSITORY + "/stat-groups"),
    ("GET", REPOSITORY + "/updates"),
    ("POST", T + "/stat-definitions"),
    ("GET", STAT_DEFINITION + "/dependents"),
    ("POST", STAT_DEFINITION + "/enum-values"),
    ("POST", T + "/stat-groups"),
    ("PATCH", STAT_GROUP),
    ("PUT", T + "/stat-groups/order"),
    ("PUT", STAT_GROUP + "/order"),
    ("PATCH", STAT_DEFINITION),
}

# A copy and applying updates ask for an admin, except as a dry run, which an Author may do to
# check what would happen (the route says so inline).
ADMIN_UNLESS_DRY_RUN = {
    ("POST", REPOSITORY + "/copy"),
    ("POST", REPOSITORY + "/updates"),
}

# An Owner or an Organizer: `get_tenant_admin_context`.
ADMIN = {
    ("GET", T + "/events/{event_id}/participants"),
    ("PUT", T + "/events/{event_id}/participants/{being_id}"),
    ("DELETE", T + "/events/{event_id}/participants/{being_id}"),
    ("GET", T + "/events/{event_id}/relationships"),
    ("POST", T + "/events/compare"),
    ("PUT", T + "/events/{event_id}/relationships/{other_event_id}"),
    ("DELETE", T + "/events/{event_id}/relationships/{other_event_id}"),
    ("PATCH", T),
    ("GET", T + "/activity-log"),
    ("POST", T + "/campaigns"),
    ("DELETE", T + "/campaigns/{campaign_id}"),
    ("PUT", T + "/campaigns/{campaign_id}/admin-opt-out"),
    ("DELETE", T + "/campaigns/{campaign_id}/admin-opt-out"),
    ("GET", T + "/knowledge"),
    ("GET", T + "/memberships"),
    ("POST", T + "/notifications"),
    ("PUT", T + "/picture"),
    ("DELETE", T + "/picture"),
    ("GET", T + "/subscribers"),
    ("GET", T + "/subscribers/summary"),
    ("DELETE", STAT_DEFINITION),
    ("DELETE", STAT_DEFINITION + "/enum-values/{enum_value_id}"),
    ("DELETE", STAT_GROUP),
}

# An Owner, checked in the route (each has its own problem type). Removing a membership is the
# Owner's too, or your own.
OWNER = {
    ("DELETE", T),
    ("POST", T + "/memberships"),
    ("POST", T + "/memberships/bulk"),
    ("PATCH", T + "/memberships/{user_id}"),
    ("DELETE", T + "/memberships/{user_id}"),
    ("PUT", T + "/published"),
    ("GET", T + "/flip-check"),
    ("PUT", T + "/public"),
    ("PUT", T + "/showcase"),
    ("DELETE", T + "/public"),
    ("DELETE", T + "/published"),
    ("PATCH", T + "/releases/{release_id}"),
    ("PUT", T + "/releases/{release_id}/current"),
    ("PUT", T + "/subscribers/{subscriber_tenant_id}"),
    ("DELETE", T + "/subscribers/{subscriber_tenant_id}"),
    ("DELETE", REPOSITORY),
    # An Owner's invite links (ADR 0220): made, listed and revoked.
    ("POST", T + "/invites"),
    ("GET", T + "/invites"),
    ("DELETE", T + "/invites/{invite_id}"),
    ("PATCH", T + "/profile"),
    ("PUT", T + "/profile/cover"),
    ("DELETE", T + "/profile/cover"),
}


def _routes(router: object) -> Iterator[APIRoute]:
    for route in router.routes:  # type: ignore[attr-defined]
        if hasattr(route, "original_router"):
            yield from _routes(route.original_router)
        elif isinstance(route, APIRoute):
            yield route


def _calls(dependant: Dependant) -> Iterator[object]:
    yield dependant.call
    for sub in dependant.dependencies:
        yield from _calls(sub)


def _membership_routes() -> dict[tuple[str, str], bool]:
    """Every (method, path) that asks for a membership, with whether it asks for an admin."""
    found: dict[tuple[str, str], bool] = {}
    for route in _routes(app.router):
        calls = list(_calls(route.dependant))
        for method in route.methods:
            # The stat vocabulary asks for a membership to write and only for a participant to read.
            asks = get_tenant_context in calls or (_vocabulary_gate in calls and method != "GET")
            if asks:
                found[(method, route.path)] = get_tenant_admin_context in calls
    return found


def test_the_audit_is_not_empty() -> None:
    assert len(_membership_routes()) > 50


def test_every_membership_route_is_on_the_audit() -> None:
    found = _membership_routes()
    listed = AUTHORING | ADMIN | OWNER | ADMIN_UNLESS_DRY_RUN
    assert sorted(set(found) - listed) == [], "a route asks for a membership and chose no tier"
    assert sorted(listed - set(found)) == [], "the audit lists a route that is gone"


def test_no_route_is_on_two_tiers() -> None:
    tiers = [AUTHORING, ADMIN, OWNER, ADMIN_UNLESS_DRY_RUN]
    for i, first in enumerate(tiers):
        for second in tiers[i + 1 :]:
            assert first & second == set()


def test_the_admin_routes_carry_the_admin_gate_and_the_others_do_not() -> None:
    found = _membership_routes()
    for key in ADMIN:
        assert found[key], f"{key} is on the admin list and has no admin gate"
    for key in AUTHORING | OWNER | ADMIN_UNLESS_DRY_RUN:
        assert not found[key], f"{key} has the admin gate and is not on the admin list"


# What the owner-tier routes need to get past their own validation to the check.
_FILES: dict[tuple[str, str], object] = {
    ("PUT", T + "/profile/cover"): {"file": ("cover.png", b"x", "image/png")},
}

_BODIES: dict[tuple[str, str], object] = {
    ("POST", T + "/memberships"): {"user_id": str(uuid.uuid4()), "role": "author"},
    ("POST", T + "/memberships/bulk"): [{"user_id": str(uuid.uuid4()), "role": "author"}],
    ("PATCH", T + "/memberships/{user_id}"): {"role": "author"},
    ("PATCH", T + "/releases/{release_id}"): {"notes": "x"},
    ("POST", T + "/invites"): {"kind": "tenant_role", "role": "author"},
    ("PUT", T + "/showcase"): {"entity_ids": []},
    ("PATCH", T + "/profile"): {"summary": "x"},
}


def _url(path: str, world: World) -> str:
    ids = {
        "{tenant_id}": world.tenant_id,
        "{subscriber_tenant_id}": uuid.uuid4(),
        "{repository_id}": uuid.uuid4(),
        "{release_id}": uuid.uuid4(),
        "{invite_id}": uuid.uuid4(),
        "{user_id}": uuid.uuid4(),
    }
    for placeholder, value in ids.items():
        path = path.replace(placeholder, str(value))
    for placeholder in (
        "{campaign_id}",
        "{entity_id}",
        "{event_id}",
        "{being_id}",
        "{other_event_id}",
        "{stat_definition_id}",
        "{stat_group_id}",
        "{enum_value_id}",
    ):
        path = path.replace(placeholder, str(uuid.uuid4()))
    return path.replace("{kind}", "item")


async def _call(world: World, who: str, method: str, path: str, **kwargs: object) -> int:
    actor = getattr(world, who)
    key = (method, path)
    if key in _BODIES:
        kwargs["json"] = _BODIES[key]
    if key in _FILES:
        kwargs["files"] = _FILES[key]
    response = await actor.client.request(
        method, _url(path, world), headers=actor.headers, **kwargs
    )
    return response.status_code


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_an_author_is_refused_on_every_admin_and_owner_route(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    try:
        for method, path in sorted(ADMIN | OWNER):
            status = await _call(world, "author", method, path)
            assert status == 403, f"an Author got {status} from {method} {path}"
        for method, path in sorted(ADMIN_UNLESS_DRY_RUN):
            status = await _call(
                world, "author", method, path, json={"dry_run": False, "actions": []}
            )
            assert status == 403, f"an Author got {status} from {method} {path}"
    finally:
        await world.clean_up()


async def test_an_organizer_is_refused_on_every_owner_route_and_not_on_the_admin_ones(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        for method, path in sorted(OWNER):
            status = await _call(world, "orga", method, path)
            assert status == 403, f"an Organizer got {status} from {method} {path}"
        # Past the gate, to whatever the route does with ids that are nothing: never a 403.
        for method, path in sorted(ADMIN):
            status = await _call(world, "orga", method, path)
            assert status != 403, f"an Organizer was refused {method} {path}"
    finally:
        await world.clean_up()


async def test_a_dry_run_of_a_copy_or_of_updates_is_not_refused_to_an_author(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        for method, path in sorted(ADMIN_UNLESS_DRY_RUN):
            status = await _call(
                world, "author", method, path, json={"dry_run": True, "actions": []}
            )
            assert status != 403, f"an Author was refused a dry run of {method} {path}"
    finally:
        await world.clean_up()


async def test_a_stranger_gets_404_on_every_membership_route(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        # Deleting a tenant asks for the platform role before it looks at the tenant.
        for method, path in sorted(AUTHORING | ADMIN | OWNER | ADMIN_UNLESS_DRY_RUN):
            if (method, path) == ("DELETE", T):
                continue
            status = await _call(world, "outsider", method, path)
            assert status == 404, f"a stranger got {status} from {method} {path}"
    finally:
        await world.clean_up()
