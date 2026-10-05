"""`lorenzo item list|add` and `lorenzo character list` (ADR 0190): names to ids, one create."""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from plain import plain
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

TENANT = uuid.UUID(int=1)
ROPE = uuid.UUID(int=10)
TORCH = uuid.UUID(int=11)
ROPE_TOO = uuid.UUID(int=12)
ASHFANG = uuid.UUID(int=20)
BRISK = uuid.UUID(int=21)
PACK = uuid.UUID(int=30)


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
        "in_public_catalog": True,
    }


def page(rows: list[Any]) -> dict[str, Any]:
    return {"items": rows, "total": len(rows), "page": 1, "size": 100, "pages": 1}


class World:
    """One library, a catalog, and the caller's characters; records every request."""

    def __init__(
        self,
        *,
        catalog: list[dict[str, Any]] | None = None,
        mine: list[tuple[uuid.UUID, str]] | None = None,
        everyone: list[tuple[uuid.UUID, str]] | None = None,
        slugs: dict[str, uuid.UUID] | None = None,
        refusal: httpx.Response | None = None,
    ) -> None:
        self.catalog = (
            catalog if catalog is not None else [item(ROPE, "Rope"), item(TORCH, "Torch")]
        )
        self.mine = mine if mine is not None else [(ASHFANG, "Ashfang")]
        self.everyone = everyone if everyone is not None else [*self.mine, (BRISK, "Brisk")]
        self.slugs = slugs or {}
        self.refusal = refusal
        self.seen: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        path, params = request.url.path, request.url.params
        base = f"/tenants/{TENANT}"
        if path == "/tenants":
            summary = {
                "id": str(TENANT),
                "slug": "table-one",
                "name": "Table One",
                "role": "participant",
                "kind": "play",
            }
            return httpx.Response(200, json=page([summary]))
        if path == base:
            return httpx.Response(
                200,
                json={
                    "id": str(TENANT),
                    "slug": "table-one",
                    "name": "Table One",
                    "kind": "play",
                    "description": "",
                    "created_by": None,
                    "updated_by": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "published_at": None,
                    "npcs_shared_with_gms": True,
                },
            )
        if path == f"{base}/characters":
            rows = self.mine if params.get("mine") == "true" else self.everyone
            return httpx.Response(
                200,
                json=page([{"entity_id": str(i), "name": n, "is_pc": True} for i, n in rows]),
            )
        if path == f"{base}/items":
            query = (params.get("q") or "").lower()
            return httpx.Response(
                200, json=page([i for i in self.catalog if query in i["title"].lower()])
            )
        if path.startswith(f"{base}/items/"):
            wanted = path.rsplit("/", 1)[1]
            for found in self.catalog:
                if found["entity_id"] == wanted:
                    return httpx.Response(200, json=found)
            return httpx.Response(404, json={"title": "Not found", "detail": "No such item."})
        if path == f"{base}/entities/resolve":
            hits = [
                {"slug": s, "entity_id": str(self.slugs[s]), "name": s, "kinds": ["item"]}
                for s in params.get_list("slug")
                if s in self.slugs
            ]
            return httpx.Response(200, json=hits)
        if path == f"{base}/item-instances" and request.method == "POST":
            if self.refusal is not None:
                return self.refusal
            body = json.loads(request.content)
            made = item(uuid.UUID(int=99), "Rope")
            made.update(
                owner_entity_id=body["owner_character_id"],
                container_entity_id=body.get("container_entity_id"),
                quantity=body.get("quantity") if body.get("container_entity_id") else None,
                slug=None,
                bound=False,
            )
            return httpx.Response(201, json=made)
        return httpx.Response(404, json={"title": "Not Found", "detail": "No such thing."})

    def posts(self) -> list[dict[str, Any]]:
        return [
            json.loads(r.content)
            for r in self.seen
            if r.method == "POST" and r.url.path.endswith("/item-instances")
        ]


def run(world: World, tmp_path: Path, *args: str):
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(world.handler),
    )
    return runner.invoke(app, list(args), obj=runtime)


# --- item list ----------------------------------------------------------------------------------


def test_item_list_shows_the_catalog_with_ids(tmp_path: Path) -> None:
    result = run(World(), tmp_path, "item", "list", "-t", "table-one")

    assert result.exit_code == 0, result.output
    text = plain(result.output)
    assert f"Rope {ROPE}" in text
    assert f"Torch {TORCH}" in text


def test_item_list_passes_the_query_on_and_can_print_json(tmp_path: Path) -> None:
    world = World()
    result = run(world, tmp_path, "item", "list", "-t", "table-one", "-q", "tor", "--json")

    assert result.exit_code == 0, result.output
    assert [row["title"] for row in json.loads(result.stdout)] == ["Torch"]


def test_item_list_says_when_the_catalog_is_empty(tmp_path: Path) -> None:
    result = run(World(catalog=[]), tmp_path, "item", "list", "-t", "table-one")

    assert "Nothing is in the catalog you can see yet." in plain(result.output)


# --- character list -----------------------------------------------------------------------------


def test_character_list_is_yours_unless_all_is_asked_for(tmp_path: Path) -> None:
    mine = run(World(), tmp_path, "character", "list", "-t", "table-one", "--json")
    everyone = run(World(), tmp_path, "character", "list", "-t", "table-one", "--all", "--json")

    assert [row["name"] for row in json.loads(mine.stdout)] == ["Ashfang"]
    assert [row["name"] for row in json.loads(everyone.stdout)] == ["Ashfang", "Brisk"]


# --- item add -----------------------------------------------------------------------------------


def test_add_by_title_to_your_only_character_makes_one_not_carried(tmp_path: Path) -> None:
    world = World()
    result = run(world, tmp_path, "item", "add", "rope", "-t", "table-one")

    assert result.exit_code == 0, result.output
    assert world.posts() == [
        {
            "prototype_id": str(ROPE),
            "owner_character_id": str(ASHFANG),
            "container_entity_id": None,
            "quantity": 1,
            "name": None,
        }
    ]
    text = plain(result.output)
    assert "Added Rope to Ashfang." in text
    assert str(uuid.UUID(int=99)) in text


def test_add_by_id_or_by_slug_finds_the_item_directly(tmp_path: Path) -> None:
    by_id = run(World(), tmp_path, "item", "add", str(TORCH), "-t", "table-one")
    by_slug_world = World(slugs={"basic-gear-torch": TORCH})
    by_slug = run(by_slug_world, tmp_path, "item", "add", "basic-gear-torch", "-t", "table-one")

    assert by_id.exit_code == 0, by_id.output
    assert by_slug.exit_code == 0, by_slug.output
    assert by_slug_world.posts()[0]["prototype_id"] == str(TORCH)


def test_add_takes_a_name_of_its_own(tmp_path: Path) -> None:
    world = World()
    result = run(world, tmp_path, "item", "add", "Rope", "-t", "table-one", "--name", "Old rope")

    assert result.exit_code == 0, result.output
    assert world.posts()[0]["name"] == "Old rope"


def test_an_item_title_that_matches_two_is_never_guessed(tmp_path: Path) -> None:
    world = World(catalog=[item(ROPE, "Rope"), item(ROPE_TOO, "ROPE")])
    result = run(world, tmp_path, "item", "add", "rope", "-t", "table-one")

    assert result.exit_code == 1
    text = plain(result.output)
    assert "More than one item is called “rope”" in text
    assert str(ROPE) in text
    assert str(ROPE_TOO) in text
    assert world.posts() == []


def test_an_item_nothing_matches_says_where_to_look(tmp_path: Path) -> None:
    world = World()
    result = run(world, tmp_path, "item", "add", "sword", "-t", "table-one")

    assert result.exit_code == 1
    assert "`lorenzo item list`" in plain(result.output)
    assert world.posts() == []


def test_a_stack_needs_a_container_and_is_not_asked_for_without_one(tmp_path: Path) -> None:
    world = World()
    result = run(world, tmp_path, "item", "add", "rope", "-t", "table-one", "-n", "3")

    assert result.exit_code == 1
    assert "needs a container" in plain(result.output)
    assert world.posts() == []


def test_a_stack_goes_into_the_container_named(tmp_path: Path) -> None:
    world = World()
    backpack = uuid.UUID(int=77)
    result = run(
        world,
        tmp_path,
        "item",
        "add",
        "rope",
        "-t",
        "table-one",
        "-n",
        "3",
        "--into",
        str(backpack),
    )

    assert result.exit_code == 0, result.output
    assert world.posts()[0]["container_entity_id"] == str(backpack)
    assert world.posts()[0]["quantity"] == 3
    assert "Added 3 x Rope to Ashfang." in plain(result.output)


def test_with_two_characters_one_must_be_named_by_name_or_id(tmp_path: Path) -> None:
    mine = [(ASHFANG, "Ashfang"), (BRISK, "Brisk")]
    refused = run(World(mine=mine), tmp_path, "item", "add", "rope", "-t", "table-one")
    world = World(mine=mine)
    named = run(world, tmp_path, "item", "add", "rope", "-t", "table-one", "--owner", "brisk")

    assert refused.exit_code == 1
    assert "more than one character" in plain(refused.output)
    assert named.exit_code == 0, named.output
    assert world.posts()[0]["owner_character_id"] == str(BRISK)


def test_another_beings_id_is_passed_on_for_the_api_to_judge(tmp_path: Path) -> None:
    npc = uuid.UUID(int=55)
    world = World()
    result = run(world, tmp_path, "item", "add", "rope", "-t", "table-one", "--owner", str(npc))

    assert result.exit_code == 0, result.output
    assert world.posts()[0]["owner_character_id"] == str(npc)


def test_the_apis_own_refusal_is_shown_as_it_says_it(tmp_path: Path) -> None:
    refusal = httpx.Response(
        403,
        json={
            "type": "self-service-disabled",
            "title": "Self-service is switched off",
            "detail": "Making your own items is switched off for this character.",
        },
        headers={"content-type": "application/problem+json"},
    )
    result = run(World(refusal=refusal), tmp_path, "item", "add", "rope", "-t", "table-one")

    assert result.exit_code == 1
    assert "switched off for this character" in plain(result.output)


def test_add_prints_the_instance_as_json(tmp_path: Path) -> None:
    result = run(World(), tmp_path, "item", "add", "rope", "-t", "table-one", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["owner_entity_id"] == str(ASHFANG)
