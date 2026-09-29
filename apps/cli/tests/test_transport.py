from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from lorenzo_cli.client.errors import (
    LorenzoApiError,
    LorenzoConnectionError,
    LorenzoResponseError,
    StaleResourceError,
)
from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.client.ops import GET_TENANT, Op
from lorenzo_cli.client.transport import LorenzoClient

TENANT = {
    "id": "6f1d3c0e-5a3f-4b8e-9d1e-0b7c1c2d3e4f",
    "slug": "sunken-vale",
    "name": "Sunken Vale",
    "description": "",
    "kind": "repository",
    "published_at": None,
    "created_by": None,
    "updated_by": None,
}


class FixedToken:
    def __init__(self, first: str = "t1", renewed: str | None = None) -> None:
        self._token = first
        self._renewed = renewed
        self.refreshes = 0

    def token(self) -> str:
        return self._token

    def refresh(self) -> str | None:
        self.refreshes += 1
        if self._renewed is not None:
            self._token = self._renewed
        return self._renewed


def make_client(
    handler: Any, tokens: FixedToken | None = None, sleeps: list[float] | None = None
) -> LorenzoClient:
    return LorenzoClient(
        "https://api.example/",
        tokens or FixedToken(),
        transport=httpx.MockTransport(handler),
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
    )


def test_a_call_sends_the_bearer_token_and_parses_the_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TENANT, headers={"ETag": '"v3"'})

    with make_client(handler) as client:
        reply = client.call(GET_TENANT, path={"tenant_id": TENANT["id"]})

    assert isinstance(reply.value, TenantOut)
    assert reply.value.slug == "sunken-vale"
    assert reply.etag == '"v3"'
    assert seen[0].headers["Authorization"] == "Bearer t1"
    assert str(seen[0].url) == f"https://api.example/tenants/{TENANT['id']}"


def test_path_parameters_must_all_be_given() -> None:
    with (
        make_client(lambda request: httpx.Response(200, json=TENANT)) as client,
        pytest.raises(ValueError, match="tenant_id"),
    ):
        client.call(GET_TENANT)


def test_path_parameters_are_escaped() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TENANT)

    with make_client(handler) as client:
        client.call(GET_TENANT, path={"tenant_id": "a/b c"})

    assert seen[0].url.raw_path == b"/tenants/a%2Fb%20c"


def test_an_error_carries_the_problem_body_and_its_detail_as_the_message() -> None:
    problem = {"type": "urn:lorenzo:not-found", "title": "Not found", "detail": "No such tenant."}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json=problem, headers={"Content-Type": "application/problem+json"}
        )

    with make_client(handler) as client, pytest.raises(LorenzoApiError) as raised:
        client.call(GET_TENANT, path={"tenant_id": "x"})

    assert str(raised.value) == "No such tenant."
    assert raised.value.status == 404
    assert raised.value.problem_type == "urn:lorenzo:not-found"
    assert raised.value.problem == problem


def test_an_error_without_a_body_still_reads_sensibly() -> None:
    with (
        make_client(lambda request: httpx.Response(500, text="oops")) as client,
        pytest.raises(LorenzoApiError, match=r"Request failed \(500\)"),
    ):
        client.call(
            GET_TENANT,
            path={"tenant_id": "x"},
        )


def test_412_is_a_stale_resource_error() -> None:
    with (
        make_client(
            lambda request: httpx.Response(412, json={"title": "Precondition Failed"})
        ) as client,
        pytest.raises(StaleResourceError),
    ):
        client.call(GET_TENANT, path={"tenant_id": "x"}, if_match='"v1"')


def test_if_match_is_sent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TENANT)

    with make_client(handler) as client:
        client.call(GET_TENANT, path={"tenant_id": "x"}, if_match='"v9"')

    assert seen[0].headers["If-Match"] == '"v9"'


def test_a_401_refreshes_the_token_once_and_retries() -> None:
    tokens = FixedToken("old", renewed="new")
    used: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        used.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401, json={"title": "Unauthorized"})
        return httpx.Response(200, json=TENANT)

    with make_client(handler, tokens) as client:
        client.call(GET_TENANT, path={"tenant_id": "x"})

    assert used == ["Bearer old", "Bearer new"]
    assert tokens.refreshes == 1


def test_a_401_that_cannot_be_refreshed_is_an_error() -> None:
    tokens = FixedToken("old")  # cannot renew

    with (
        make_client(
            lambda request: httpx.Response(401, json={"title": "Unauthorized"}), tokens
        ) as client,
        pytest.raises(LorenzoApiError) as raised,
    ):
        client.call(GET_TENANT, path={"tenant_id": "x"})

    assert raised.value.status == 401
    assert tokens.refreshes == 1


def test_a_get_is_retried_on_a_503() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=TENANT)

    with make_client(handler, sleeps=sleeps) as client:
        client.call(GET_TENANT, path={"tenant_id": "x"})

    assert len(calls) == 3
    assert len(sleeps) == 2


def test_a_dropped_connection_gives_up_after_the_attempts() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("refused")

    with make_client(handler) as client, pytest.raises(LorenzoConnectionError):
        client.call(GET_TENANT, path={"tenant_id": "x"})

    assert len(calls) == 3


class Thing(BaseModel):
    name: str
    note: str | None = None


CREATE_THING: Op[Thing] = Op("create_thing", "POST", "/things", Thing, Thing)
PUT_THING: Op[Thing] = Op("put_thing", "PUT", "/things/1", Thing, Thing)


def test_a_post_is_never_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with make_client(handler) as client, pytest.raises(LorenzoApiError):
        client.call(CREATE_THING, body=Thing(name="x"))

    assert len(calls) == 1


def test_a_put_is_retried_and_only_the_fields_set_are_sent() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={"name": "x"})

    with make_client(handler) as client:
        reply = client.call(PUT_THING, body=Thing(name="x"))

    assert reply.value == Thing(name="x")
    assert bodies == [{"name": "x"}, {"name": "x"}]  # `note` was never set, so never sent


def test_a_body_the_models_dont_accept_is_a_response_error() -> None:
    with (
        make_client(lambda request: httpx.Response(200, json={"id": "not-a-tenant"})) as client,
        pytest.raises(LorenzoResponseError, match="get_tenant"),
    ):
        client.call(GET_TENANT, path={"tenant_id": "x"})
