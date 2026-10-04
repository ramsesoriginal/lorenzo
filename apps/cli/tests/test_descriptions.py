"""A description is titled with its item's name (ADR 0165): finding the placeholder, and the
read-then-patch that changes it."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from test_transport import FixedToken

from lorenzo_cli import descriptions
from lorenzo_cli.client.errors import StaleResourceError
from lorenzo_cli.client.models import EntityDetailOut, InformationOut
from lorenzo_cli.client.transport import LorenzoClient

NOW = datetime(2026, 10, 4, tzinfo=UTC)
TENANT = uuid.uuid4()
INFORMATION = uuid.uuid4()


def information(title: str, type_: str = "description") -> InformationOut:
    return InformationOut(
        id=uuid.uuid4(),
        title=title,
        type=type_,
        is_public=True,
        order=1,
        updated_at=NOW,
        payloads=[],
    )


def detail(name: str, *rows: InformationOut) -> EntityDetailOut:
    return EntityDetailOut.model_construct(name=name, information=list(rows))


def test_a_description_with_the_placeholder_title_is_found() -> None:
    placeholder = information("Description")

    found = descriptions.placeholder_description(detail("Heavy crossbow", placeholder))

    assert found is placeholder


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [information("Heavy crossbow")],
        [information("The Purple Blade")],  # somebody's own display title
        [information("Description", "alias")],  # only a description is the item's title
    ],
)
def test_anything_else_is_left_alone(rows: list[InformationOut]) -> None:
    assert descriptions.placeholder_description(detail("Heavy crossbow", *rows)) is None


def test_an_item_really_named_description_already_shows_its_name() -> None:
    assert (
        descriptions.placeholder_description(detail("Description", information("Description")))
        is None
    )


def client_for(handler: Any) -> LorenzoClient:
    return LorenzoClient(
        "https://api.example/",
        FixedToken(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def reply(title: str) -> dict[str, Any]:
    return information(title).model_dump(mode="json") | {"id": str(INFORMATION)}


def test_retitle_reads_the_row_for_its_etag_then_sends_only_the_title() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=reply("Description"), headers={"ETag": '"v1"'})
        return httpx.Response(200, json=reply("Heavy crossbow"), headers={"ETag": '"v2"'})

    with client_for(handler) as client:
        descriptions.retitle(client, TENANT, INFORMATION, "Heavy crossbow")

    assert [r.method for r in seen] == ["GET", "PATCH"]
    path = f"/tenants/{TENANT}/information/{INFORMATION}"
    assert [r.url.path for r in seen] == [path, path]
    assert seen[1].headers["If-Match"] == '"v1"'
    assert json.loads(seen[1].content) == {"title": "Heavy crossbow"}


def test_a_row_that_changed_in_between_raises_stale() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=reply("Description"), headers={"ETag": '"v1"'})
        return httpx.Response(412, json={"title": "Precondition Failed", "detail": "It changed."})

    with client_for(handler) as client, pytest.raises(StaleResourceError):
        descriptions.retitle(client, TENANT, INFORMATION, "Heavy crossbow")
