"""Adding a parent to an item that has some (ADR 0172, 0181, 0182), without a network."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from test_transport import FixedToken
from test_unseed import _item

from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.prototypes import add_parent

TENANT = uuid.UUID(int=1)
CHILD = uuid.UUID(int=2)


def api(seen: list[httpx.Request], have: list[uuid.UUID]) -> LorenzoClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body: dict[str, Any] = {**_item(), "prototype_ids": [str(p) for p in have]}
        return httpx.Response(200, json=body, headers={"ETag": '"v7"'})

    return LorenzoClient(
        "https://api.example/",
        FixedToken(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def test_a_parent_is_added_to_the_ones_the_child_has_with_the_etag_it_was_read_with() -> None:
    seen: list[httpx.Request] = []
    have = [uuid.uuid4(), uuid.uuid4()]
    parent = uuid.uuid4()

    with api(seen, have) as client:
        added = add_parent(client, TENANT, CHILD, parent)

    assert added is True
    assert [r.method for r in seen] == ["GET", "PUT"]
    assert seen[1].url.path.endswith(f"/items/{CHILD}/prototypes")
    assert seen[1].headers["If-Match"] == '"v7"'
    assert json.loads(seen[1].content) == {"prototype_ids": [*map(str, have), str(parent)]}


def test_a_parent_the_child_has_is_not_added_again_and_nothing_is_written() -> None:
    seen: list[httpx.Request] = []
    parent = uuid.uuid4()

    with api(seen, [uuid.uuid4(), parent]) as client:
        added = add_parent(client, TENANT, CHILD, parent)

    assert added is False
    assert [r.method for r in seen] == ["GET"]
