"""Handing a pack out through the API (RFC 0032, ADR 0150): one call, and its answer and refusals."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import PackGivenOut
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer.give import (
    PackError,
    count_instances,
    entity_id_of,
    give_pack,
    tree_lines,
)
from lorenzo_cli.main import app

TENANT = uuid.UUID(int=1)
PACK = uuid.UUID(int=100)
ALICE = uuid.UUID(int=200)
SLUGS = {"explorers-pack": PACK, "alice": ALICE}


class Tokens:
    def token(self) -> str:
        return "t"

    def refresh(self) -> str | None:
        return None


def instance(title: str, quantity: int | None) -> dict[str, Any]:
    nothing: dict[str, Any] = dict.fromkeys(
        ("weight", "height", "price", "rarity", "hp", "armor", "container_entity_id"), None
    )
    return {
        **nothing,
        "entity_id": str(uuid.uuid4()),
        "title": title,
        "quantity": quantity,
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
        "owner_entity_id": str(ALICE),
        "slug": None,
        "bound": False,
    }


def answer(*, dry_run: bool = False, group: bool = False) -> dict[str, Any]:
    """A backpack holding rations and torches, and a loose rope: for a group, none of it has a
    count at the top."""
    top = None if group else 1
    return {
        "pack_id": str(PACK),
        "owner_entity_id": str(ALICE),
        "dry_run": dry_run,
        "created": [
            {
                "item_instance": instance("Backpack", top),
                "children": [
                    {"item_instance": instance("Rations", 5), "children": []},
                    {"item_instance": instance("Torch", 2), "children": []},
                ],
            },
            {"item_instance": instance("Rope", None if group else 2), "children": []},
        ],
    }


def api(
    reply: httpx.Response | None = None,
) -> tuple[LorenzoClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/entities/resolve"):
            hits = [
                {"slug": s, "entity_id": str(SLUGS[s]), "name": s, "kinds": ["item"]}
                for s in request.url.params.get_list("slug")
                if s in SLUGS
            ]
            return httpx.Response(200, json=hits)
        if path.endswith("/item-instances/from-pack") and request.method == "POST":
            sent.append(request)
            if reply is not None:
                return reply
            return httpx.Response(
                201, json=answer(dry_run=request.url.params.get("dry_run") == "true")
            )
        return httpx.Response(404, json={"title": "no"})

    client = LorenzoClient(
        "https://api.example",
        Tokens(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    return client, sent


def refusal(status: int, kind: str, **extra: Any) -> httpx.Response:
    return httpx.Response(
        status,
        json={"type": kind, "title": "Refused", "detail": "It can't be done.", **extra},
        headers={"content-type": "application/problem+json"},
    )


def test_a_pack_is_given_with_one_call_naming_ids() -> None:
    client, sent = api()

    given = give_pack(client, TENANT, "explorers-pack", "alice")

    [request] = sent
    assert json.loads(request.content) == {
        "pack_id": str(PACK),
        "owner_entity_id": str(ALICE),
        "override": False,
    }
    assert "dry_run" not in request.url.params
    assert [entry.item_instance.title for entry in given.created] == ["Backpack", "Rope"]
    assert given.dry_run is False


def test_ids_are_used_as_they_are() -> None:
    client, sent = api()

    give_pack(client, TENANT, str(PACK), str(ALICE))

    assert json.loads(sent[0].content)["pack_id"] == str(PACK)


def test_a_dry_run_asks_for_one() -> None:
    client, sent = api()

    given = give_pack(client, TENANT, "explorers-pack", "alice", dry_run=True)

    assert sent[0].url.params.get("dry_run") == "true"
    assert given.dry_run is True


def test_override_is_passed_on() -> None:
    client, sent = api()

    give_pack(client, TENANT, "explorers-pack", "alice", override=True)

    assert json.loads(sent[0].content)["override"] is True


def test_what_was_made_is_shown_by_what_is_inside_what() -> None:
    given = PackGivenOut.model_validate(answer())

    assert tree_lines(given) == ["1 x Backpack", "  5 x Rations", "  2 x Torch", "2 x Rope"]
    assert count_instances(given) == 4


def test_a_groups_top_level_has_no_count_to_show() -> None:
    given = PackGivenOut.model_validate(answer(group=True))

    assert tree_lines(given) == ["Backpack", "  5 x Rations", "  2 x Torch", "Rope"]


def test_a_list_that_cant_be_handed_out_is_shown_with_its_lines() -> None:
    client, _ = api(
        refusal(
            422,
            "pack-list",
            lines=["“Alms box” has no link to an item", "“gone” is not an item of this tenant"],
        )
    )

    with pytest.raises(PackError) as raised:
        give_pack(client, TENANT, "explorers-pack", "alice")

    assert str(raised.value) == (
        "“explorers-pack” can't be handed out as it is:\n"
        "  - “Alms box” has no link to an item\n"
        "  - “gone” is not an item of this tenant"
    )


def test_something_that_is_not_a_pack_is_said_so() -> None:
    client, _ = api(refusal(422, "not-a-pack"))

    with pytest.raises(PackError, match="isn't a pack"):
        give_pack(client, TENANT, "explorers-pack", "alice")


def test_any_other_refusal_is_the_apis_own() -> None:
    client, _ = api(refusal(409, "capacity-exceeded"))

    with pytest.raises(LorenzoApiError) as raised:
        give_pack(client, TENANT, "explorers-pack", "alice")

    assert raised.value.status == 409
    assert raised.value.problem_type == "capacity-exceeded"


def test_a_pack_or_owner_that_is_not_there_is_named_and_nothing_is_sent() -> None:
    client, sent = api()

    with pytest.raises(PackError, match="no pack “nope”"):
        give_pack(client, TENANT, "nope", "alice")
    with pytest.raises(PackError, match="no being or group “nobody”"):
        give_pack(client, TENANT, "explorers-pack", "nobody")
    assert sent == []


def test_a_reference_is_an_id_or_a_slug_in_the_tenant() -> None:
    client, _ = api()

    assert entity_id_of(client, TENANT, str(PACK), "pack") == PACK
    assert entity_id_of(client, TENANT, "explorers-pack", "pack") == PACK
    with pytest.raises(PackError, match="no pack “nope”"):
        entity_id_of(client, TENANT, "nope", "pack")


def test_an_owner_is_required() -> None:
    result = CliRunner().invoke(app, ["pack", "give", "explorers-pack", "--tenant", "camp"])

    assert result.exit_code == 2
    assert "--owner" in result.output
