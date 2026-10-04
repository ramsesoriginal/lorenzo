"""The seed as four repositories, a bridge over them, and the tables that take them (ADR 0162,
0163, 0175; RFC 0033).

Core is the neutral vocabulary (A0). The equipment (A1) and the D&D 5e rules (B) are each a copy of
it with a layer seeded on top. The bridge (C) copied both, attached the rules' Economic object to
the equipment's forms, and imported items under all three. RFC 0025 R8 assumed, and left untested,
that a copy of a bridge keeps a homebrew category minted under a root that lives in the core
repository; this checks that, and that a table which took the equipment first gets the D&D prices
when it takes the bridge later, against the real API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import FIXTURES, by_slug, make_tenant, parent_names, run_cli, tenant_id
from e2e.stack import Stack


class Split:
    """Core, the equipment and the rules over it, a bridge over both, and the tenants that draw on
    the bridge."""

    def __init__(self, stack: Stack, tmp_path: Path) -> None:
        self.stack = stack
        self.tmp_path = tmp_path
        self.token = stack.creator_token("split-owner")
        self.core = make_tenant(stack, self.token, "repository")
        self.equipment = make_tenant(stack, self.token, "repository")
        self.rules = make_tenant(stack, self.token, "repository")
        self.bridge = make_tenant(stack, self.token, "repository")
        self.ok("seed", "--tenant", self.core, "--layer", "core", "--yes")
        self.ok("repo", "publish", "--tenant", self.core)
        # The equipment and the rules draw on core like any tenant: granted it, then a copy of
        # its own, with a layer seeded on top.
        for repository, layer in ((self.equipment, "equipment"), (self.rules, "dnd5e")):
            self.ok("repo", "grant", repository, "--tenant", self.core)
            self.ok("repo", "copy", self.core, "--tenant", repository, "--yes")
            self.ok("seed", "--tenant", repository, "--layer", layer, "--yes")
            self.ok("repo", "publish", "--tenant", repository)
        # The bridge takes both, with core under them, and adds what joins them.
        self.ok("repo", "offer", self.bridge, "--tenant", self.equipment, "--yes")
        self.ok("repo", "offer", self.bridge, "--tenant", self.rules, "--yes")
        self.ok("seed", "--tenant", self.bridge, "--layer", "dnd5e-equipment", "--yes")
        self.ok(
            "apply", "--tenant", self.bridge, str(FIXTURES / "weapons.js"),
            "--map", str(FIXTURES / "legendary-form.map.toml"),
            "--review-queue", str(tmp_path / "review-queue.json"),
            "--proposed-map", str(tmp_path / "proposed.map.toml"),
            "--yes",
        )  # fmt: skip
        self.ok("repo", "publish", "--tenant", self.bridge)

    @property
    def everything(self) -> set[str]:
        return {self.core, self.equipment, self.rules, self.bridge}

    def cli(self, *args: str) -> Any:
        return run_cli(self.stack, self.token, self.tmp_path, *args)

    def ok(self, *args: str) -> Any:
        result = self.cli(*args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def json(self, *args: str) -> tuple[int, Any]:
        result = self.cli(*args, "--json")
        return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else None

    def table(self) -> str:
        return make_tenant(self.stack, self.token, "play")

    def entity(self, tenant: str, slug: str) -> dict[str, Any]:
        with self.stack.api(self.token) as api:
            return by_slug(api, tenant_id(api, tenant), slug)

    def rename(self, tenant: str, slug: str, name: str) -> None:
        with self.stack.api(self.token) as api:
            tid = tenant_id(api, tenant)
            entity = by_slug(api, tid, slug)
            path = f"/tenants/{tid}/items/{entity['id']}"
            etag = api.get(path).headers["ETag"]
            response = api.patch(path, json={"name": name}, headers={"If-Match": etag})
            assert response.status_code == 200, response.text


def said(result: Any) -> str:
    return " ".join(result.output.split())


def all_titles(api: httpx.Client, tid: str) -> list[str]:
    titles: list[str] = []
    page = 1
    while True:
        body = api.get(f"/tenants/{tid}/items", params={"page": page, "size": 100}).json()
        titles += [item["title"] for item in body["items"]]
        if page >= body["pages"]:
            return titles
        page += 1


def test_a_copy_of_the_bridge_keeps_a_category_minted_under_a_root_in_core(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()

    code, offered = split.json("repo", "offer", table, "--tenant", split.bridge, "--yes")

    assert code == 0, offered
    assert offered["dependencies"] == {
        split.core: "new",
        split.equipment: "new",
        split.rules: "new",
    }  # all granted too
    assert offered["granted"] == "new"
    assert offered["copied"] == "copied"
    # One copy brought the whole stack, dependencies first: core under the two that are built on
    # it, and the bridge last.
    steps = [s["name"] for s in offered["copy"]["steps"]]
    assert set(steps) == split.everything
    assert steps[0] == split.core and steps[-1] == split.bridge

    # The category the bridge minted under core's `physical-object` came across, and its parent
    # is the table's own copy of that root, not a dangling reference and not a second one.
    root = split.entity(table, "physical-object")
    category = split.entity(table, "hb-legendary-form")
    assert category["name"] == "Legendary weapon"
    assert [p["id"] for p in category["prototypes"]] == [root["id"]]
    # And what the bridge authored from the layers: a weapon with a parent in each.
    whip = split.entity(table, "basic-weapons-moon-whip")
    assert parent_names(whip) == ["Legendary weapon", "Melee weapon", "Whip"]
    martial = split.entity(table, "dnd5e-martial")
    assert "Purple sword" in [e["name"] for e in martial["instances"]]
    with stack.api(split.token) as api:
        held = api.get(f"/tenants/{tenant_id(api, table)}/repositories").json()["items"]
    assert {row["repository"]["slug"] for row in held} == split.everything
    assert all(row["copied_at"] for row in held)


def test_a_table_that_took_the_equipment_first_gets_the_prices_when_it_takes_the_bridge(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()
    split.ok("repo", "offer", table, "--tenant", split.equipment, "--yes")
    before = split.entity(table, "weapon")
    # The equipment alone: a Weapon is a physical object, and has no price, for it has no system.
    assert parent_names(before) == ["Physical object"]
    assert "price" not in {s["name"] for s in before["stats"]}

    code, offered = split.json("repo", "offer", table, "--tenant", split.bridge, "--yes")

    assert code == 0, offered
    assert offered["dependencies"] == {
        split.core: "copied",
        split.equipment: "copied",
        split.rules: "new",
    }
    steps = {s["name"]: s for s in offered["copy"]["steps"]}
    assert set(steps) == {split.rules, split.bridge}  # what it had it didn't take twice
    assert steps[split.bridge]["attachments"] == 6
    # The Weapon it already had has the Economic object as a parent now, and the price of 0 it
    # carries, which the table's Weapon doesn't hold itself.
    weapon = split.entity(table, "weapon")
    assert parent_names(weapon) == ["Economic object (D&D 5e)", "Physical object"]
    price = next(s for s in weapon["stats"] if s["name"] == "price")
    assert price["value"] == 0 and price["own"] is False
    economic = split.entity(table, "dnd5e-economic-object")
    assert [p["name"] for p in economic["prototypes"]] == ["D&D 5e"]
    # All six forms, and not the root they hang from.
    for form in ("weapon", "armor", "tool", "container", "consumable", "gear"):
        assert "Economic object (D&D 5e)" in parent_names(split.entity(table, form)), form
    assert "Economic object (D&D 5e)" not in parent_names(split.entity(table, "melee-weapon"))
    # One Weapon, not a copy of the equipment's and a copy of the bridge's.
    with stack.api(split.token) as api:
        titles = all_titles(api, tenant_id(api, table))
    assert titles.count("Weapon") == 1 and titles.count("Economic object (D&D 5e)") == 1


def test_the_bridge_counts_what_it_attaches_and_the_layers_it_holds(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)

    code, contents = split.json("repo", "contents", "--tenant", split.bridge)
    layers = contents["seed"]["layers"]

    assert code == 0, contents
    assert contents["holds"]["attachments"] == 6
    assert {name: layer["holds"] for name, layer in layers.items()} == {
        "core": "complete",
        "equipment": "complete",
        "dnd5e": "complete",
        "dnd5e-equipment": "complete",
    }
    assert layers["dnd5e-equipment"]["attachments"] == {"present": 6, "in_seed": 6}
    # Each of the others holds only its own layer and what it is built on.
    equipment = split.json("repo", "contents", "--tenant", split.equipment)[1]["seed"]["layers"]
    assert [name for name, layer in equipment.items() if layer["holds"] == "complete"] == [
        "core",
        "equipment",
    ]
    assert equipment["dnd5e-equipment"]["attachments"] == {"present": 0, "in_seed": 6}


def test_a_tenant_needs_every_grant_and_the_plan_says_which_is_missing(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()
    split.ok("repo", "grant", table, "--tenant", split.bridge)  # only the bridge

    code, plan = split.json("repo", "copy-plan", split.bridge, "--tenant", table)
    refused = split.cli("repo", "copy", split.bridge, "--tenant", table, "--yes")

    assert code == 1
    assert {s["name"]: s["granted"] for s in plan["steps"]} == {
        split.core: False,
        split.equipment: False,
        split.rules: False,
        split.bridge: True,
    }
    assert refused.exit_code == 1
    assert f"{split.core} (not granted)" in said(refused)

    for repository in (split.core, split.equipment, split.rules):
        split.ok("repo", "grant", table, "--tenant", repository)
    assert split.json("repo", "copy-plan", split.bridge, "--tenant", table)[0] == 0
    split.ok("repo", "copy", split.bridge, "--tenant", table, "--yes")
    assert split.entity(table, "hb-legendary-form")["name"] == "Legendary weapon"


def test_a_correction_to_core_reaches_the_bridge_and_then_the_table(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()
    split.ok("repo", "offer", table, "--tenant", split.bridge, "--yes")

    # core corrects a name and announces it; the bridge takes it, and publishes in its turn.
    split.rename(split.core, "physical-object", "Physical object, corrected")
    split.ok("repo", "publish", "--tenant", split.core)
    taken = split.ok("repo", "updates", split.core, "--tenant", split.bridge, "--apply", "--yes")
    assert "Took 1 changed" in said(taken)
    assert split.entity(split.bridge, "physical-object")["name"] == "Physical object, corrected"
    split.ok("repo", "publish", "--tenant", split.bridge)

    # the table sees it on core's own route, and takes it there.
    code, updates = split.json("repo", "updates", split.core, "--tenant", table)
    assert code == 2
    assert [r["name"] for r in updates["changed"]] == ["Physical object"]
    split.ok("repo", "updates", split.core, "--tenant", table, "--apply", "--yes")
    assert split.entity(table, "physical-object")["name"] == "Physical object, corrected"
    assert split.json("repo", "updates", split.core, "--tenant", table)[0] == 0


def test_seeding_every_layer_into_one_repository_still_works_and_says_the_split_is_better(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("split-owner")
    everything = make_tenant(stack, token, "repository")
    only_core = make_tenant(stack, token, "repository")

    plain = run_cli(stack, token, tmp_path, "seed", "--tenant", everything, "--dry-run")
    core = run_cli(
        stack, token, tmp_path, "seed", "--tenant", only_core, "--layer", "core", "--dry-run"
    )
    as_json = run_cli(stack, token, tmp_path, "seed", "--tenant", everything, "--dry-run", "--json")

    assert plain.exit_code == 2 and core.exit_code == 2
    assert "Every layer is going into this one repository" in said(plain)
    assert "ADR 0162, 0175" in said(plain)
    assert "Every layer" not in said(core)
    json.loads(as_json.stdout)  # the advice never reaches a script's document
    assert "Every layer" not in as_json.stdout
