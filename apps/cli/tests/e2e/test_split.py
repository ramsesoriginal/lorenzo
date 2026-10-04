"""The D&D 5e layer as its own repository, a bridge over core (ADR 0162, 0163).

RFC 0025 R8 assumed, and left untested, that a copy of the bridge keeps a homebrew category minted
under an axis root that lives in the core repository. This is that check, against the real API:
core seeded and published, a bridge that copied it and seeded the D&D layer on top and imported
items under both, and a table's tenant that takes the lot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e.helpers import FIXTURES, by_slug, make_tenant, parent_names, run_cli, tenant_id
from e2e.stack import Stack


class Split:
    """Core, a bridge that copied it, and the tenants that draw on the bridge."""

    def __init__(self, stack: Stack, tmp_path: Path) -> None:
        self.stack = stack
        self.tmp_path = tmp_path
        self.token = stack.creator_token("split-owner")
        self.core = make_tenant(stack, self.token, "repository")
        self.bridge = make_tenant(stack, self.token, "repository")
        self.ok("seed", "--tenant", self.core, "--layer", "core", "--yes")
        self.ok("repo", "publish", "--tenant", self.core)
        # The bridge draws on core like any tenant: granted it, then a copy of its own.
        self.ok("repo", "grant", self.bridge, "--tenant", self.core)
        self.ok("repo", "copy", self.core, "--tenant", self.bridge, "--yes")
        self.ok("seed", "--tenant", self.bridge, "--layer", "dnd5e", "--yes")
        self.ok(
            "apply", "--tenant", self.bridge, str(FIXTURES / "weapons.js"),
            "--map", str(FIXTURES / "legendary-form.map.toml"),
            "--review-queue", str(tmp_path / "review-queue.json"),
            "--proposed-map", str(tmp_path / "proposed.map.toml"),
            "--yes",
        )  # fmt: skip
        self.ok("repo", "publish", "--tenant", self.bridge)

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


def test_a_copy_of_the_bridge_keeps_a_category_minted_under_an_axis_root_in_core(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()

    code, offered = split.json("repo", "offer", table, "--tenant", split.bridge, "--yes")

    assert code == 0, offered
    assert offered["dependencies"] == {split.core: "new"}  # core was granted too
    assert offered["granted"] == "new"
    assert offered["copied"] == "copied"
    # One copy brought the whole stack, dependencies first.
    assert [s["name"] for s in offered["copy"]["steps"]] == [split.core, split.bridge]

    # The category the bridge minted under core's `physical-object` came across, and its parent
    # is the table's own copy of that root, not a dangling reference and not a second one.
    root = split.entity(table, "physical-object")
    category = split.entity(table, "hb-legendary-form")
    assert category["name"] == "Legendary weapon"
    assert [p["id"] for p in category["prototypes"]] == [root["id"]]
    # And what the bridge authored from both layers: a weapon with a parent in each.
    whip = split.entity(table, "basic-weapons-moon-whip")
    assert parent_names(whip) == ["Legendary weapon", "Melee weapon", "Whip"]
    martial = split.entity(table, "dnd5e-martial")
    assert "Purple sword" in [e["name"] for e in martial["instances"]]
    with stack.api(split.token) as api:
        held = api.get(f"/tenants/{tenant_id(api, table)}/repositories").json()["items"]
    assert {row["repository"]["slug"] for row in held} == {split.core, split.bridge}
    assert all(row["copied_at"] for row in held)


def test_a_tenant_needs_both_grants_and_the_plan_says_which_is_missing(
    stack: Stack, tmp_path: Path
) -> None:
    split = Split(stack, tmp_path)
    table = split.table()
    split.ok("repo", "grant", table, "--tenant", split.bridge)  # only the bridge

    code, plan = split.json("repo", "copy-plan", split.bridge, "--tenant", table)
    refused = split.cli("repo", "copy", split.bridge, "--tenant", table, "--yes")

    assert code == 1
    assert [(s["name"], s["granted"]) for s in plan["steps"]] == [
        (split.core, False),
        (split.bridge, True),
    ]
    assert refused.exit_code == 1
    assert f"{split.core} (not granted)" in said(refused)

    split.ok("repo", "grant", table, "--tenant", split.core)
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
    split.rename(split.core, "weapon", "Weapon, corrected")
    split.ok("repo", "publish", "--tenant", split.core)
    taken = split.ok("repo", "updates", split.core, "--tenant", split.bridge, "--apply", "--yes")
    assert "Took 1 changed" in said(taken)
    assert split.entity(split.bridge, "weapon")["name"] == "Weapon, corrected"
    split.ok("repo", "publish", "--tenant", split.bridge)

    # the table sees it on core's own route, and takes it there.
    code, updates = split.json("repo", "updates", split.core, "--tenant", table)
    assert code == 2
    assert [r["name"] for r in updates["changed"]] == ["Weapon"]
    split.ok("repo", "updates", split.core, "--tenant", table, "--apply", "--yes")
    assert split.entity(table, "weapon")["name"] == "Weapon, corrected"
    assert split.json("repo", "updates", split.core, "--tenant", table)[0] == 0


def test_seeding_both_layers_into_one_repository_still_works_and_says_the_split_is_better(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("split-owner")
    both = make_tenant(stack, token, "repository")
    only_core = make_tenant(stack, token, "repository")

    plain = run_cli(stack, token, tmp_path, "seed", "--tenant", both, "--dry-run")
    core = run_cli(
        stack, token, tmp_path, "seed", "--tenant", only_core, "--layer", "core", "--dry-run"
    )
    as_json = run_cli(stack, token, tmp_path, "seed", "--tenant", both, "--dry-run", "--json")

    assert plain.exit_code == 2 and core.exit_code == 2
    assert "Both layers are going into this one repository" in said(plain)
    assert "ADR 0162" in said(plain)
    assert "Both layers" not in said(core)
    json.loads(as_json.stdout)  # the advice never reaches a script's document
    assert "Both layers" not in as_json.stdout
