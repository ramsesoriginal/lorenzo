"""How `seed` reads the items it already finds in a tenant: from the listing, not one by one
(ADR 0143), against a stand-in API that counts what it is asked."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.plan import read_items

TENANT = uuid.UUID(int=1)


class Tokens:
    def token(self) -> str:
        return "t"

    def refresh(self) -> str | None:
        return None


def item(entity_id: uuid.UUID, title: str) -> dict[str, Any]:
    nothing: dict[str, Any] = dict.fromkeys(
        ("weight", "height", "price", "rarity", "hp", "armor", "container_entity_id", "quantity"),
        None,
    )
    return {
        **nothing,
        "entity_id": str(entity_id),
        "title": title,
        "prototype_ids": [],
        "is_container": None,
        "descriptions": [],
        "pictures": [],
        "physical_stats": [],
        "economic_stats": [],
        "destroyable_stats": [],
        "damaging_stats": [],
        "tags": [],
        "created_by": None,
        "updated_by": None,
        "updated_at": "2026-01-01T00:00:00Z",
        "in_public_catalog": False,
    }


class Api:
    """A tenant's items: those it lists (in pages of `size`, as many pages as `pages_override`
    says, if given) and those only a request by id finds."""

    def __init__(
        self,
        listed: list[uuid.UUID],
        *,
        unlisted: list[uuid.UUID] | None = None,
        pages_override: int | None = None,
    ) -> None:
        self.listed = listed
        self.unlisted = unlisted or []
        self.pages_override = pages_override
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/items"):
            self.requests.append(f"list page {request.url.params['page']}")
            size = int(request.url.params["size"])
            number = int(request.url.params["page"])
            rows = self.listed[(number - 1) * size : number * size]
            pages = self.pages_override or -(-len(self.listed) // size)
            return httpx.Response(
                200,
                json={
                    "items": [item(i, "listed") for i in rows],
                    "total": len(self.listed),
                    "page": number,
                    "size": size,
                    "pages": pages,
                },
            )
        entity_id = uuid.UUID(path.rsplit("/", 1)[1])
        self.requests.append("get by id")
        if entity_id in self.listed or entity_id in self.unlisted:
            return httpx.Response(200, json=item(entity_id, "by id"))
        return httpx.Response(404, json={"title": "no"})

    def client(self) -> LorenzoClient:
        return LorenzoClient(
            "https://api.example",
            Tokens(),
            transport=httpx.MockTransport(self.handler),
            sleep=lambda _: None,
        )


def ids(count: int, start: int = 1000) -> list[uuid.UUID]:
    return [uuid.UUID(int=start + n) for n in range(count)]


def test_the_nodes_a_tenant_has_are_read_from_one_page_of_the_listing() -> None:
    held = ids(40)
    api = Api(held)
    wanted = {"a": held[3], "b": held[17], "c": held[39]}

    found = read_items(api.client(), TENANT, wanted)

    assert api.requests == ["list page 1"]
    assert list(found) == ["a", "b", "c"]
    assert {slug: i.entity_id for slug, i in found.items()} == wanted
    assert {i.title for i in found.values()} == {"listed"}


def test_a_tenant_with_several_pages_is_read_page_by_page_and_not_node_by_node() -> None:
    held = ids(250)
    api = Api(held)
    wanted = {"first": held[0], "middle": held[120], "last": held[249]}

    found = read_items(api.client(), TENANT, wanted)

    assert api.requests == ["list page 1", "list page 2", "list page 3"]
    assert {slug: i.entity_id for slug, i in found.items()} == wanted


def test_what_the_listing_does_not_hold_is_asked_for_by_id() -> None:
    held, hidden = ids(5), ids(2, start=9000)
    api = Api(held, unlisted=hidden)
    wanted = {"shown": held[2], "hidden": hidden[0]}

    found = read_items(api.client(), TENANT, wanted)

    assert api.requests == ["list page 1", "get by id"]
    assert found["shown"].title == "listed" and found["hidden"].title == "by id"


def test_a_tenant_with_far_more_items_than_the_seed_has_nodes_is_read_node_by_node() -> None:
    held = ids(100)
    api = Api(held, pages_override=11)
    wanted = {"a": held[3], "b": held[17]}

    found = read_items(api.client(), TENANT, wanted)

    # The first page tells how big the tenant is, and no more of it is listed.
    assert api.requests == ["list page 1", "get by id", "get by id"]
    assert {slug: i.entity_id for slug, i in found.items()} == wanted


def test_nothing_is_asked_when_no_node_exists_yet() -> None:
    api = Api(ids(10))

    assert read_items(api.client(), TENANT, {}) == {}
    assert api.requests == []
