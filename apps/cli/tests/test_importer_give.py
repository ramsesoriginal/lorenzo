from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest

from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer.give import PackError, entity_id_of, give_pack, groups_of
from lorenzo_cli.importer.packs import PackLine, render

TENANT = uuid.UUID(int=1)
PACK = uuid.UUID(int=100)
CONTENTS = render(
    [
        PackLine(0, 1, "Backpack", "gear-backpack"),
        PackLine(1, 5, "Rations", "gear-rations"),
        PackLine(1, 2, "Torch", "gear-torch"),
        PackLine(1, 1, "Alms box", None),
        PackLine(0, 3, "Bell", "gear-bell"),
        PackLine(0, 1, "Censer", None),
    ]
)
KNOWN = {"gear-backpack", "gear-rations", "gear-torch", "gear-bell"}


class Tokens:
    def token(self) -> str:
        return "t"

    def refresh(self) -> str | None:
        return None


def detail(content: str) -> dict[str, Any]:
    payload = {
        "id": str(uuid.uuid4()),
        "order": 0,
        "updated_at": "2026-01-01T00:00:00Z",
        "kind": "description",
        "content": content,
        "locale": "en-US",
    }
    return {
        "id": str(PACK),
        "name": "Pack",
        "slug": "pack",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "stats": [],
        "stat_groups": [],
        "information": [
            {
                "id": str(uuid.uuid4()),
                "title": "Description",
                "type": "description",
                "is_public": True,
                "order": 0,
                "updated_at": "2026-01-01T00:00:00Z",
                "payloads": [payload],
            }
        ],
        "prototypes": [],
        "instances": [],
        "parent": None,
        "quantity": None,
        "children": [],
    }


def instance(entity_id: uuid.UUID) -> dict[str, Any]:
    nothing: dict[str, Any] = dict.fromkeys(
        ("weight", "height", "price", "rarity", "hp", "armor", "container_entity_id"), None
    )
    return {
        **nothing,
        "entity_id": str(entity_id),
        "title": "x",
        "quantity": 1,
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
        "owner_entity_id": None,
        "slug": None,
        "bound": False,
    }


def api(known: set[str], description: str = CONTENTS) -> tuple[LorenzoClient, list[dict[str, Any]]]:
    created: list[dict[str, Any]] = []
    ids = {slug: uuid.UUID(int=200 + i) for i, slug in enumerate(sorted(known))}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/entities/resolve"):
            wanted = request.url.params.get_list("slug")
            hits = [
                {"slug": s, "entity_id": str(ids[s]), "name": s, "kinds": ["item"]}
                for s in wanted
                if s in ids
            ]
            return httpx.Response(200, json=hits)
        if path.endswith(f"/entities/{PACK}"):
            return httpx.Response(200, json=detail(description))
        if path.endswith("/item-instances") and request.method == "POST":
            created.append(json.loads(request.content))
            return httpx.Response(201, json=instance(uuid.UUID(int=900 + len(created) - 1)))
        return httpx.Response(404, json={"title": "no"})

    client = LorenzoClient(
        "https://api.example",
        Tokens(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    return client, created


def test_lines_are_grouped_under_their_container() -> None:
    lines = [PackLine(1, 2, "x", "a"), PackLine(0, 1, "B", "b"), PackLine(1, 5, "R", "r")]

    groups = groups_of(lines)

    assert [(g.line.label, [c.label for c in g.children]) for g in groups] == [
        ("x", []),  # an orphan at depth 1 starts its own group
        ("B", ["R"]),
    ]


def test_the_container_is_made_first_and_what_is_in_it_goes_inside_with_its_quantity() -> None:
    client, created = api(KNOWN)

    given = give_pack(client, TENANT, str(PACK))

    backpack, rations, torch = created[0], created[1], created[2]
    assert "container_entity_id" not in backpack and backpack["quantity"] == 1
    assert rations["container_entity_id"] == str(uuid.UUID(int=900))  # inside the backpack
    assert (rations["quantity"], torch["quantity"]) == (5, 2)
    assert torch["container_entity_id"] == rations["container_entity_id"]
    assert [g.text for g in given][:3] == ["1 x Backpack", "5 x Rations", "2 x Torch"]


def test_loose_things_are_each_their_own_instance_and_plain_text_is_skipped() -> None:
    client, created = api(KNOWN)
    said: list[str] = []

    give_pack(client, TENANT, str(PACK), say=said.append)

    bell = str(
        uuid.UUID(int=201)
    )  # the tenant knows: backpack 200, bell 201, rations 202, torch 203
    bells = [c for c in created if c["prototype_id"] == bell]
    assert len(created) == 3 + 3  # backpack, rations, torch; three loose bells
    assert len(bells) == 3 and all("container_entity_id" not in b for b in bells)
    assert all(b["quantity"] == 1 for b in bells)
    assert "skipped Alms box: it isn't a catalog item" in said
    assert "skipped Censer: it isn't a catalog item" in said


def test_into_puts_a_stack_of_loose_things_in_that_container() -> None:
    client, created = api(KNOWN)
    chest = uuid.UUID(int=555)

    give_pack(client, TENANT, str(PACK), into=chest)

    stacks = [c for c in created if c.get("container_entity_id") == str(chest)]
    assert sorted(c["quantity"] for c in stacks) == [1, 3]  # the backpack, and the three bells


def test_an_owner_gets_everything() -> None:
    client, created = api(KNOWN)
    alice = uuid.UUID(int=777)

    give_pack(client, TENANT, str(PACK), owner=alice)

    assert created and all(c["owner_character_id"] == str(alice) for c in created)


def test_a_dry_run_creates_nothing() -> None:
    client, created = api(KNOWN)
    said: list[str] = []

    given = give_pack(client, TENANT, str(PACK), dry_run=True, say=said.append)

    assert created == []
    assert "would create 5 x Rations" in said
    assert sum(g.created for g in given) == 1 + 5 + 2 + 3


def test_a_pack_with_items_missing_from_the_tenant_creates_nothing_and_says_which() -> None:
    client, created = api({"gear-backpack"})

    with pytest.raises(PackError, match="gear-bell, gear-rations, gear-torch"):
        give_pack(client, TENANT, str(PACK))
    assert created == []


def test_a_description_without_a_list_is_not_a_pack() -> None:
    client, _ = api(KNOWN, description="Just a lovely backpack.")

    with pytest.raises(PackError, match="no contents list"):
        give_pack(client, TENANT, str(PACK))


def test_too_many_loose_things_is_a_typo_not_a_request() -> None:
    client, _ = api(KNOWN, description=render([PackLine(0, 500, "Bell", "gear-bell")]))

    with pytest.raises(PackError, match="more than 50"):
        give_pack(client, TENANT, str(PACK))


def test_a_reference_is_an_id_or_a_slug_in_the_tenant() -> None:
    client, _ = api(KNOWN)

    assert entity_id_of(client, TENANT, str(PACK), "pack") == PACK
    assert entity_id_of(client, TENANT, "gear-bell", "pack") == uuid.UUID(int=201)
    with pytest.raises(PackError, match="no pack “nope”"):
        entity_id_of(client, TENANT, "nope", "pack")
