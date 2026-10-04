"""`lorenzo seed --list` (ADR 0169): what the built-in seed makes, read from the file and from
nobody else."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
from plain import plain
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app
from lorenzo_cli.seed import LAYERS, load_builtin

runner = CliRunner()
SPEC = load_builtin()


def runtime(tmp_path: Path, seen: list[httpx.Request]) -> Runtime:
    """A runtime whose network records every request and answers none of them."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500)

    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(handler),
    )


def listing(tmp_path: Path, *args: str):  # noqa: ANN201
    seen: list[httpx.Request] = []
    result = runner.invoke(app, ["seed", "--list", *args], obj=runtime(tmp_path, seen))
    return result, seen


def test_it_lists_every_layer_and_asks_nobody(tmp_path: Path) -> None:
    result, seen = listing(tmp_path)

    assert result.exit_code == 0, result.output
    assert seen == []  # no login, no tenant, no API
    text = plain(result.output)
    assert f"The built-in seed, version {SPEC.version}." in text
    for layer in LAYERS:
        assert f"{layer}:" in text
    assert "dnd5e-martial" in text and "crossbow" in text and "damage_die" in text
    assert "contents(weight)" in text and "sum(own_weight, contents_weight)" in text


def test_it_counts_what_each_layer_makes(tmp_path: Path) -> None:
    text = plain(listing(tmp_path)[0].output)

    for layer in LAYERS:
        groups = sum(g.layer == layer for g in SPEC.groups)
        definitions = sum(d.layer == layer for d in SPEC.definitions)
        nodes = [n for n in SPEC.nodes if n.layer == layer]
        described = sum(1 for n in nodes if n.description)
        recipes = sum(r.layer == layer for r in SPEC.recipes)
        assert (
            f"{layer}: {groups} stat groups, {definitions} stat definitions, {len(nodes)} "
            f"categories ({described} with a description), {recipes} recipes"
        ) in text


def test_a_layer_can_be_asked_for_alone(tmp_path: Path) -> None:
    result, _ = listing(tmp_path, "--layer", "dnd5e")

    text = plain(result.output)
    assert "dnd5e-martial" in text
    assert "physical-object" not in text and "core:" not in text


def test_a_category_sits_right_under_its_parent_and_deeper(tmp_path: Path) -> None:
    lines = listing(tmp_path, "--layer", "core")[0].output.splitlines()

    def at(slug: str) -> tuple[int, int]:
        index = next(i for i, line in enumerate(lines) if line.split()[:1] == [slug])
        return index, len(lines[index]) - len(lines[index].lstrip())

    ranged, bow = at("ranged-weapon"), at("bow")
    assert bow[0] > ranged[0] and bow[1] > ranged[1]
    assert at("physical-object")[1] < at("weapon")[1] < at("melee-weapon")[1]
    # A tag a category sets is on its line.
    container = lines[at("container")[0]]
    assert "sets is_container" in container


def test_json_is_the_seed_as_data(tmp_path: Path) -> None:
    result, seen = listing(tmp_path, "--json", "--layer", "core")

    data = json.loads(result.output)
    assert seen == []
    assert data["seed_version"] == SPEC.version
    assert list(data["layers"]) == ["core"]
    core = data["layers"]["core"]
    assert core["stat_groups"][0] == "physical"
    assert {"name": "weight", "stat_group": "physical", "value_type": "float"} in core[
        "stat_definitions"
    ]
    crossbow = next(c for c in core["categories"] if c["slug"] == "crossbow")
    assert crossbow["parents"] == ["ranged-weapon"] and crossbow["name"] == "Crossbow"
    assert {"node": "physical-object", "stat": "weight", "kind": "sum"}.items() <= next(
        r for r in core["recipes"] if r["stat"] == "weight"
    ).items()


def test_a_tenant_given_anyway_is_not_asked_about(tmp_path: Path) -> None:
    result, seen = listing(tmp_path, "--tenant", "core")

    assert result.exit_code == 0, result.output
    assert seen == []


def test_it_will_not_go_with_an_option_that_writes(tmp_path: Path) -> None:
    for flag in ("--dry-run", "--yes", "--allow-play-tenant"):
        result, seen = listing(tmp_path, flag)

        assert result.exit_code == 2, flag
        assert f"can't go with {flag}" in plain(result.output)
        assert seen == []


def test_an_unknown_layer_is_refused(tmp_path: Path) -> None:
    result, _ = listing(tmp_path, "--layer", "pathfinder")

    assert result.exit_code == 2
    assert "choose from core, dnd5e" in plain(result.output)


def test_without_list_a_tenant_is_still_needed(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(app, ["seed", "--dry-run"], obj=runtime(tmp_path, seen))

    assert result.exit_code == 2
    assert "Name the repository with --tenant" in plain(result.output)
    assert seen == []
