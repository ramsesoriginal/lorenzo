"""`lorenzo repo contents` (ADR 0169): what a repository holds and how much of each seed layer,
read from a fake API that only answers reads."""

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
from lorenzo_cli.seed import LAYERS, holdings, load_builtin

runner = CliRunner()
SPEC = load_builtin()
REPO = uuid.UUID(int=1)
CORE = uuid.UUID(int=2)
PLAY = uuid.UUID(int=3)
NOW = "2026-10-03T12:00:00Z"


def page(items: list[Any], *, total: int | None = None) -> dict[str, Any]:
    return {
        "items": items,
        "total": len(items) if total is None else total,
        "page": 1,
        "size": 100,
        "pages": 1 if items else 0,
    }


def tenant(tenant_id: uuid.UUID, slug: str, kind: str, published: str | None) -> dict[str, Any]:
    return {
        "id": str(tenant_id),
        "slug": slug,
        "name": slug.title(),
        "description": "",
        "kind": kind,
        "published_at": published,
        "npcs_shared_with_gms": True,
        "created_by": None,
        "updated_by": None,
    }


def subscription(
    slug: str, *, copied: str | None, published: str | None, synced: str | None = None
) -> dict[str, Any]:
    return {
        "repository": {
            "id": str(CORE),
            "name": slug.title(),
            "slug": slug,
            "description": "",
            "published_at": published,
        },
        "granted_at": NOW,
        "copied_at": copied,
        "synced_at": synced,
        "contributed": None,
    }


class Shelf:
    """One repository tenant and what it holds, answering the reads `repo contents` makes."""

    def __init__(
        self,
        *,
        slug: str = "core",
        kind: str = "repository",
        published: str | None = None,
        layers: tuple[str, ...] = ("core",),
        other_groups: int = 0,
        other_definitions: int = 0,
        other_items: int = 0,
        subscribers: int = 0,
        built_on: list[dict[str, Any]] | None = None,
    ) -> None:
        group_id = uuid.UUID(int=100)
        self.tenant = tenant(REPO if kind == "repository" else PLAY, slug, kind, published)
        self.groups = [g.name for g in SPEC.groups if g.layer in layers] + [
            f"homebrew-{n}" for n in range(other_groups)
        ]
        self.definitions = [d.name for d in SPEC.definitions if d.layer in layers] + [
            f"homebrew_{n}" for n in range(other_definitions)
        ]
        self.nodes = [n.slug for n in SPEC.nodes if n.layer in layers]
        self.items = len(self.nodes) + other_items
        self.subscribers = subscribers
        self.built_on = built_on or []
        self.group_id = group_id
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:  # noqa: C901
        self.requests.append(request)
        path = request.url.path
        tid = self.tenant["id"]
        if request.method != "GET":
            return httpx.Response(405)
        if path == f"/tenants/{tid}":
            return httpx.Response(200, json=self.tenant)
        if path == f"/tenants/{tid}/stat-groups":
            rows = [
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "priority": 0,
                    "mandatory": False,
                    "created_at": NOW,
                    "updated_at": NOW,
                }
                for name in self.groups
            ]
            return httpx.Response(200, json=page(rows))
        if path == f"/tenants/{tid}/stat-definitions":
            rows = [
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "stat_group_id": str(self.group_id),
                    "value_type": "int",
                    "enum_values": [],
                    "created_at": NOW,
                    "updated_at": NOW,
                }
                for name in self.definitions
            ]
            return httpx.Response(200, json=page(rows))
        if path == f"/tenants/{tid}/entities/resolve":
            wanted = request.url.params.get_list("slug")
            found = [
                {"slug": slug, "entity_id": str(uuid.uuid4()), "name": slug, "kinds": ["item"]}
                for slug in wanted
                if slug in self.nodes
            ]
            return httpx.Response(200, json=found)
        if path == f"/tenants/{tid}/items":
            return httpx.Response(200, json=page([], total=self.items))
        if path == f"/tenants/{tid}/subscribers":
            rows = [
                {
                    "tenant_id": str(uuid.UUID(int=500 + n)),
                    "name": f"Table {n}",
                    "slug": f"table-{n}",
                    "granted_at": NOW,
                    "granted_by": None,
                }
                for n in range(self.subscribers)
            ]
            return httpx.Response(200, json=page(rows))
        if path == f"/tenants/{tid}/repositories":
            return httpx.Response(200, json=page(self.built_on))
        return httpx.Response(404, json={"title": "Not Found", "detail": path})


def contents(tmp_path: Path, shelf: Shelf, *args: str):  # noqa: ANN201
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(shelf.handler),
    )
    return runner.invoke(
        app, ["repo", "contents", "--tenant", shelf.tenant["id"], *args], obj=runtime
    )


# --- which layers a tenant holds -----------------------------------------------------------------


def layer_of(name: str, groups: list[str], definitions: list[str], categories: list[str]) -> Any:
    return next(
        h
        for h in holdings(SPEC, groups=groups, definitions=definitions, categories=categories)
        if h.layer == name
    )


def test_a_layer_with_everything_is_complete_and_one_with_nothing_is_not_there() -> None:
    everything = (
        [g.name for g in SPEC.groups],
        [d.name for d in SPEC.definitions],
        [n.slug for n in SPEC.nodes],
    )

    assert [h.holds for h in holdings(SPEC, groups=[], definitions=[], categories=[])] == [
        "not there"
    ] * len(LAYERS)
    assert [
        h.holds
        for h in holdings(
            SPEC, groups=everything[0], definitions=everything[1], categories=everything[2]
        )
    ] == ["complete"] * len(LAYERS)


def test_a_layer_with_some_of_it_is_partly_there_and_counts_each_kind() -> None:
    dnd = [n.slug for n in SPEC.nodes if n.layer == "dnd5e"]

    holding = layer_of("dnd5e", [], [], dnd[:5])

    assert holding.holds == "partly"
    assert (holding.categories.present, holding.categories.in_seed) == (5, len(dnd))
    assert holding.definitions.present == 0


def test_a_layer_without_stat_groups_is_complete_with_the_rest() -> None:
    # dnd5e makes no stat groups of its own, so zero of zero doesn't count against it.
    holding = layer_of(
        "dnd5e",
        [],
        [d.name for d in SPEC.definitions if d.layer == "dnd5e"],
        [n.slug for n in SPEC.nodes if n.layer == "dnd5e"],
    )

    assert holding.groups.in_seed == 0
    assert holding.holds == "complete"


# --- the command ---------------------------------------------------------------------------------


def test_a_core_repository_shows_core_complete_and_dnd5e_not_there(tmp_path: Path) -> None:
    shelf = Shelf(layers=("core",), published=NOW, subscribers=2)

    result = contents(tmp_path, shelf)

    assert result.exit_code == 0, result.output
    text = plain(result.output)
    assert "core (Core) is a repository, published 2026-10-03, granted to 2 tenant(s)." in text
    assert "Built on nothing: it has copied no repository." in text
    assert "Holds 6 stat groups, 18 stat definitions and 33 items (categories included)." in text
    assert "core complete 6 of 6 18 of 18 33 of 33" in text
    assert "dnd5e not there - 0 of 22 0 of 28" in text
    assert "Beyond the seed: 0 stat groups, 0 stat definitions and 0 items." in text


def test_a_draft_says_so(tmp_path: Path) -> None:
    text = plain(contents(tmp_path, Shelf()).output)

    assert "is a repository, a draft, granted to 0 tenant(s)." in text


def test_what_the_seed_doesnt_name_is_counted_beyond_it(tmp_path: Path) -> None:
    shelf = Shelf(layers=("core", "dnd5e"), other_groups=1, other_definitions=3, other_items=82)

    text = plain(contents(tmp_path, shelf).output)

    assert "Holds 7 stat groups, 43 stat definitions and 143 items" in text
    assert "dnd5e complete - 22 of 22 28 of 28" in text
    assert "Beyond the seed: 1 stat groups, 3 stat definitions and 82 items." in text


def test_a_layer_half_there_is_partly(tmp_path: Path) -> None:
    shelf = Shelf(layers=("core", "dnd5e"))
    shelf.nodes = shelf.nodes[:-10]
    shelf.items = len(shelf.nodes)

    text = plain(contents(tmp_path, shelf).output)

    assert "dnd5e partly - 22 of 22 18 of 28" in text


def test_a_bridge_says_what_it_is_built_on_and_whether_that_changed(tmp_path: Path) -> None:
    built = subscription("core", copied="2026-10-02T12:00:00Z", published="2026-10-04T12:00:00Z")
    shelf = Shelf(slug="dnd5e", layers=("core", "dnd5e"), built_on=[built])
    unchanged = Shelf(
        slug="dnd5e",
        layers=("core", "dnd5e"),
        built_on=[
            subscription("core", copied="2026-10-02T12:00:00Z", published="2026-10-01T12:00:00Z")
        ],
    )
    granted_only = Shelf(
        slug="dnd5e",
        layers=("core", "dnd5e"),
        built_on=[subscription("core", copied=None, published=NOW)],
    )

    changed_text = plain(contents(tmp_path, shelf).output)
    unchanged_text = plain(contents(tmp_path, unchanged).output)
    granted_text = plain(contents(tmp_path, granted_only).output)

    assert "Built on core, copied 2026-10-02 and has published since." in changed_text
    assert "Built on core, copied 2026-10-02." in unchanged_text
    assert "published since" not in unchanged_text
    assert "Built on nothing" in granted_text  # granted but never copied is not a dependency


def test_json_has_the_same_facts(tmp_path: Path) -> None:
    shelf = Shelf(layers=("core",), published=NOW, subscribers=1, other_items=2)

    result = contents(tmp_path, shelf, "--json")

    data = json.loads(result.output)
    assert data["tenant"]["slug"] == "core" and data["tenant"]["kind"] == "repository"
    assert data["tenant"]["published_at"].startswith("2026-10-03")
    assert data["granted_to"] == 1 and data["built_on"] == []
    assert data["holds"] == {"stat_groups": 6, "stat_definitions": 18, "items": 35}
    assert data["seed"]["version"] == SPEC.version
    assert data["seed"]["layers"]["core"]["holds"] == "complete"
    assert data["seed"]["layers"]["core"]["categories"] == {"present": 33, "in_seed": 33}
    assert data["seed"]["layers"]["dnd5e"]["holds"] == "not there"
    assert data["beyond_seed"] == {"stat_groups": 0, "stat_definitions": 0, "items": 2}


def test_a_play_tenant_is_refused(tmp_path: Path) -> None:
    shelf = Shelf(slug="table", kind="play")

    result = contents(tmp_path, shelf)

    assert result.exit_code == 1
    assert "play tenant, not a repository" in plain(result.output)
    assert "can't be inspected" in plain(result.output)


def test_it_only_reads_and_says_nothing_about_which_instance(tmp_path: Path) -> None:
    shelf = Shelf(layers=("core",))

    result = contents(tmp_path, shelf)

    assert {r.method for r in shelf.requests} == {"GET"}
    assert "Using the official Lorenzo" not in result.output
    # The item total is one request, not a walk of every item.
    item_requests = [r for r in shelf.requests if r.url.path.endswith("/items")]
    assert len(item_requests) == 1 and item_requests[0].url.params["size"] == "1"
