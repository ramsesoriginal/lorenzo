"""The README's setup of the four repositories, run command for command against the real API
(RFC 0033 §7, ADR 0183), and what happens to a table's items when a repository is corrected or
grows later (§8).

Every repository here is made the way a person makes it: `tenant create`, `seed --layer`,
`repo offer`, `apply --part`, `repo publish`. The tests below say what the setup left, and how a
correction travels; the details of each step are in the files that test that step.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from e2e.helpers import FIXTURES, by_slug, own_stats, parent_names, run_cli, tenant_id
from e2e.stack import Stack

MAP = ["--map", str(FIXTURES / "legendary-form.map.toml")]
WEAPONS = [*MAP, str(FIXTURES / "weapons.js")]
GEAR = [*MAP, str(FIXTURES / "gear.js")]
SWORD = "basic-weapons-purple-sword"
LAMP = "basic-gear-purple-lamp"


class Setup:
    """RFC 0033 §7: the eighteen commands, in order. Slugs get a suffix, since one database holds
    every test's tenants."""

    def __init__(self, stack: Stack, work: Path) -> None:
        self.stack = stack
        self.work = work
        self.token = stack.creator_token("setup-" + uuid.uuid4().hex[:6])
        tag = uuid.uuid4().hex[:6]
        self.core = f"core-{tag}"
        self.equipment = f"common-fantasy-eq-{tag}"
        self.rules = f"dnd5e-{tag}"
        self.bridge = f"dnd5e-common-eq-{tag}"
        self.tables = 0
        self.tag = tag

        # A0
        self.ok("tenant", "create", "Core", "--slug", self.core)
        self.ok("seed", "--tenant", self.core, "--layer", "core", "--yes")
        self.ok("repo", "publish", "--tenant", self.core)
        # A1: a copy of A0, the forms and the neutral items, public
        self.ok("tenant", "create", "Common Fantasy Equipment", "--slug", self.equipment)
        self.ok("repo", "offer", self.equipment, "--tenant", self.core, "--yes")
        self.ok("seed", "--tenant", self.equipment, "--layer", "equipment", "--yes")
        self.neutral(WEAPONS)
        self.ok("repo", "publish", "--tenant", self.equipment)
        # B: a copy of A0, with the D&D layer
        self.ok("tenant", "create", "Dungeons and Dragons 5e", "--slug", self.rules)
        self.ok("repo", "offer", self.rules, "--tenant", self.core, "--yes")
        self.ok("seed", "--tenant", self.rules, "--layer", "dnd5e", "--yes")
        self.ok("repo", "publish", "--tenant", self.rules)
        # C: copies of A1 and B, the category-level attachments, then the D&D prototypes
        self.ok("tenant", "create", "Common D&D5e Equipment", "--slug", self.bridge)
        self.ok("repo", "offer", self.bridge, "--tenant", self.equipment, "--yes")
        self.ok("repo", "offer", self.bridge, "--tenant", self.rules, "--yes")
        self.ok("seed", "--tenant", self.bridge, "--layer", "dnd5e-equipment", "--yes")
        self.system(WEAPONS)
        self.ok("repo", "publish", "--tenant", self.bridge)

    def neutral(self, files: list[str]) -> None:
        self.ok(
            "apply", "--tenant", self.equipment, "--part", "neutral", "--public-catalog", *files,
            "--review-queue", str(self.work / "review-queue.json"),
            "--proposed-map", str(self.work / "proposed.map.toml"),
            "--yes",
        )  # fmt: skip

    def system(self, files: list[str]) -> None:
        self.ok(
            "apply", "--tenant", self.bridge, "--part", "system", *files,
            "--review-queue", str(self.work / "review-queue.json"),
            "--proposed-map", str(self.work / "proposed.map.toml"),
            "--yes",
        )  # fmt: skip

    def table(self, *repositories: str) -> str:
        """A table, with each of the repositories offered to it, in order."""
        self.tables += 1
        slug = f"my-table-{self.tag}-{self.tables}"
        self.ok("tenant", "create", "My table", "--slug", slug, "--kind", "play")
        for repository in repositories:
            self.ok("repo", "offer", slug, "--tenant", repository, "--yes")
        return slug

    def cli(self, *args: str) -> Any:
        return run_cli(self.stack, self.token, self.work, *args)

    def ok(self, *args: str) -> Any:
        result = self.cli(*args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def json(self, *args: str) -> tuple[int, Any]:
        result = self.cli(*args, "--json")
        return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else None

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

    def updates(self, repository: str, table: str) -> tuple[int, dict[str, Any]]:
        code, document = self.json("repo", "updates", repository, "--tenant", table)
        return code, document

    def take(self, repository: str, table: str) -> str:
        result = self.ok("repo", "updates", repository, "--tenant", table, "--apply", "--yes")
        return str(result.output)

    def waiting(self, table: str, repository: str) -> bool:
        """What `repo list` marks as "updated since": published after the table last synced."""
        _, rows = self.json("repo", "list", "--tenant", table)
        row = next(r for r in rows if r["repository"]["slug"] == repository)
        published = datetime.fromisoformat(row["repository"]["published_at"])
        return published > datetime.fromisoformat(row["synced_at"] or row["copied_at"])

    def attachments(self, repository: str) -> int:
        return int(self.json("repo", "contents", "--tenant", repository)[1]["holds"]["attachments"])


def names(rows: list[dict[str, Any]]) -> set[str]:
    return {row["name"] for row in rows}


def test_the_setup_leaves_four_repositories_and_the_bridge_attaches_what_it_made(
    stack: Stack, tmp_path: Path
) -> None:
    setup = Setup(stack, tmp_path)

    contents = {
        name: setup.json("repo", "contents", "--tenant", slug)[1]
        for name, slug in (
            ("core", setup.core),
            ("equipment", setup.equipment),
            ("rules", setup.rules),
            ("bridge", setup.bridge),
        )
    }

    # Each is published, and holds the layers it is built from and no more.
    assert all(c["tenant"]["published_at"] for c in contents.values())
    held = {
        name: [
            layer for layer, found in c["seed"]["layers"].items() if found["holds"] == "complete"
        ]
        for name, c in contents.items()
    }
    assert held == {
        "core": ["core"],
        "equipment": ["core", "equipment"],
        "rules": ["core", "dnd5e"],
        "bridge": ["core", "equipment", "dnd5e", "dnd5e-equipment"],
    }
    assert {name: {r["slug"] for r in c["built_on"]} for name, c in contents.items()} == {
        "core": set(),
        "equipment": {setup.core},
        "rules": {setup.core},
        "bridge": {setup.core, setup.equipment, setup.rules},
    }
    # The bridge's own: the six forms, and a prototype for every sword, bow and dart that has
    # something of the system's. The equipment holds the items and no prototype.
    assert contents["bridge"]["holds"]["attachments"] > 6
    assert contents["equipment"]["holds"]["attachments"] == 0
    assert setup.entity(setup.equipment, SWORD)["prototypes"]
    assert "price" not in own_stats(setup.entity(setup.equipment, SWORD))
    assert parent_names(setup.entity(setup.bridge, SWORD)) == [
        "Blade",
        "Melee weapon",
        "Purple sword (D&D 5e)",
    ]


def test_a_table_is_usable_with_the_equipment_alone_and_gets_dnd_on_the_same_items_later(
    stack: Stack, tmp_path: Path
) -> None:
    setup = Setup(stack, tmp_path)

    table = setup.table(setup.equipment)
    before = setup.entity(table, SWORD)
    setup.ok("repo", "offer", table, "--tenant", setup.bridge, "--yes")
    after = setup.entity(table, SWORD)

    assert parent_names(before) == ["Blade", "Melee weapon"]
    assert "damage_die" not in {s["name"] for s in before["stats"]}
    assert before["id"] == after["id"]  # the same sword, not a second one
    assert parent_names(after) == ["Blade", "Melee weapon", "Purple sword (D&D 5e)"]
    dice = next(s for s in after["stats"] if s["name"] == "damage_die")
    assert dice["value"] == 8 and dice["own"] is False


def test_a_correction_is_taken_from_the_repository_it_was_made_in_and_nothing_else_must_move(
    stack: Stack, tmp_path: Path
) -> None:
    setup = Setup(stack, tmp_path)
    table = setup.table(setup.equipment, setup.bridge)

    # The equipment corrects its Purple sword, and publishes once.
    setup.rename(setup.equipment, SWORD, "Purple sword, corrected")
    setup.ok("repo", "publish", "--tenant", setup.equipment)

    # The table takes it from the equipment. The bridge has done nothing and has nothing to say.
    code, updates = setup.updates(setup.equipment, table)
    assert code == 2 and names(updates["changed"]) == {"Purple sword"}
    assert setup.updates(setup.bridge, table)[0] == 0
    setup.take(setup.equipment, table)
    sword = setup.entity(table, SWORD)
    assert sword["name"] == "Purple sword, corrected"
    assert parent_names(sword) == ["Blade", "Melee weapon", "Purple sword (D&D 5e)"]  # D&D is kept

    # A correction to the rules, or to core, goes the same way: from where it was made.
    setup.rename(setup.rules, "dnd5e-martial", "Martial weapon, corrected")
    setup.ok("repo", "publish", "--tenant", setup.rules)
    setup.take(setup.rules, table)
    assert setup.entity(table, "dnd5e-martial")["name"] == "Martial weapon, corrected"
    assert "Purple sword (D&D 5e)" in parent_names(setup.entity(table, SWORD))

    # The bridge keeps its own copy current when its author chooses to. It keeps what it attached,
    # and publishing again announces nothing to a table that has everything.
    attached = setup.attachments(setup.bridge)
    setup.take(setup.equipment, setup.bridge)
    assert setup.entity(setup.bridge, SWORD)["name"] == "Purple sword, corrected"
    assert "Purple sword (D&D 5e)" in parent_names(setup.entity(setup.bridge, SWORD))
    assert setup.attachments(setup.bridge) == attached
    setup.ok("repo", "publish", "--tenant", setup.bridge)
    assert setup.updates(setup.bridge, table)[0] == 0

    # A table that arrives after all of this has the corrected sword, with D&D on it.
    fresh = setup.table(setup.bridge)
    sword = setup.entity(fresh, SWORD)
    assert sword["name"] == "Purple sword, corrected"
    assert "Purple sword (D&D 5e)" in parent_names(sword)


def test_what_the_equipment_adds_later_reaches_a_table_with_its_dnd_whichever_is_taken_first(
    stack: Stack, tmp_path: Path
) -> None:
    setup = Setup(stack, tmp_path)
    in_order = setup.table(setup.equipment, setup.bridge)
    wrong_order = setup.table(setup.equipment, setup.bridge)

    # The equipment imports more, the bridge takes it and writes D&D's half, and each publishes.
    setup.neutral(GEAR)
    setup.take(setup.equipment, setup.bridge)  # without it the bridge has no item to attach to
    setup.system(GEAR)
    assert not setup.waiting(in_order, setup.equipment)
    # A repository's changes are there to be taken as soon as they are made: publishing again
    # announces them (`repo list` says "updated since"), it isn't what lets a table see them.
    assert names(setup.updates(setup.equipment, in_order)[1]["added"]) >= {"Purple lamp"}
    setup.ok("repo", "publish", "--tenant", setup.equipment)
    setup.ok("repo", "publish", "--tenant", setup.bridge)
    assert setup.waiting(in_order, setup.equipment) and setup.waiting(in_order, setup.bridge)

    # In order: the items, then the prototypes that attach to them.
    setup.take(setup.equipment, in_order)
    setup.take(setup.bridge, in_order)
    assert parent_names(setup.entity(in_order, LAMP)) == ["Gear", "Purple lamp (D&D 5e)"]

    # The other way round, the prototypes arrive and wait for the item they attach to, and say so...
    code, waiting = setup.updates(setup.bridge, wrong_order)
    assert code == 2
    assert {a["reason"] for a in waiting["attachments_added"]} == {
        "the item it attaches to isn't here"
    }
    assert all(a["applicable"] is False for a in waiting["attachments_added"])
    left = setup.cli("repo", "updates", setup.bridge, "--tenant", wrong_order, "--apply", "--yes")
    assert left.exit_code == 2  # what waits is left, and the exit code says so
    assert "the item it attaches to isn't here" in " ".join(left.output.split())
    assert parent_names(setup.entity(wrong_order, "srd5e-gear-purple-lamp")) == []
    # ...and when the items come, the next run of the bridge's updates attaches them.
    setup.take(setup.equipment, wrong_order)
    assert parent_names(setup.entity(wrong_order, LAMP)) == ["Gear"]
    code, ready = setup.updates(setup.bridge, wrong_order)
    assert code == 2 and all(a["applicable"] for a in ready["attachments_added"])
    setup.take(setup.bridge, wrong_order)
    assert parent_names(setup.entity(wrong_order, LAMP)) == ["Gear", "Purple lamp (D&D 5e)"]
    assert setup.updates(setup.bridge, wrong_order)[0] == 0
