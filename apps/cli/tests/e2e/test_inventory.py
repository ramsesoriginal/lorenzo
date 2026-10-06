"""`lorenzo inventory import` and `export` for a player, against the real API (ADR 0193)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from e2e.helpers import run_cli
from e2e.stack import Stack
from e2e.test_self_service import _table
from lorenzo_cli.inventory.format import parse

FILE = """\
format: lorenzo-inventory/1
owner: Ashfang

## Equipped
- Dagger | weight: 0.5 | value: 2 G
- Backpack
  - Seil | note: from the market
  - Hydra Zahn | weight: 1 | value: ? | note: from the cave under the temple
  - Quiver
    - 22 x [Crossbow bolts](crossbow-bolts) | kind: ammo

## Not carried
- Vault key
- Chest | place: the inn at Pal Vaz
  - Spare cloak
"""


def _library(stack: Stack, table: dict[str, Any], *, placeholder: bool = True) -> None:
    """What the catalog holds beyond _table's Rope: the things FILE names, each public, and the
    placeholder the seed makes (ADR 0192)."""
    names = [
        ("Dagger", "dagger"),
        ("Backpack", "backpack"),
        ("Quiver", "quiver"),
        ("Crossbow bolts", "crossbow-bolts"),
        ("Chest", "chest"),
        ("Spare cloak", "spare-cloak"),
    ]
    if placeholder:
        names.append(("Unsorted item", "unsorted"))
    with stack.api(table["gm"]) as api:
        for name, slug in names:
            made = api.post(
                f"/tenants/{table['tenant_id']}/items",
                json={"name": name, "slug": slug, "prototype_ids": [], "in_public_catalog": True},
            )
            assert made.status_code == 201, made.text


def _write(tmp_path: Path, text: str, name: str = "inventory.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _instances(stack: Stack, table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    with stack.api(table["player"]) as api:
        owned = api.get(
            f"/tenants/{table['tenant_id']}/item-instances/owned-by/{table['character_id']}"
        ).json()
    return {i["title"]: i for g in owned["groups"] for i in g["item_instances"]}


def _notes(stack: Stack, table: dict[str, Any], instance_id: str) -> dict[str, str]:
    with stack.api(table["player"]) as api:
        rows = api.get(
            f"/tenants/{table['tenant_id']}/entities/{instance_id}/information",
            params={"type": "note"},
        ).json()["items"]
    return {row["title"]: row["payloads"][0]["content"] for row in rows}


def test_a_player_imports_matches_placeholders_containers_and_notes(
    stack: Stack, tmp_path: Path
) -> None:
    table = _table(stack)
    _library(stack, table)
    player, slug = table["player"], table["slug"]
    path = _write(tmp_path, FILE)

    done = run_cli(stack, player, tmp_path, "inventory", "import", str(path), "-t", slug, "--yes")

    assert done.exit_code == 0, done.output
    assert "Made 9 (2 unsorted)" in " ".join(done.output.split())
    made = _instances(stack, table)
    character = table["character_id"]
    assert set(made) == {
        "Dagger",
        "Backpack",
        "Seil",
        "Hydra Zahn",
        "Quiver",
        "Crossbow bolts",
        "Vault key",
        "Chest",
        "Spare cloak",
    }
    # Equipped is in the hands, not carried is in none, the rest is inside what the file nests.
    assert made["Dagger"]["container_entity_id"] == character
    assert made["Backpack"]["container_entity_id"] == character
    assert made["Vault key"]["container_entity_id"] is None
    assert made["Chest"]["container_entity_id"] is None
    assert made["Seil"]["container_entity_id"] == made["Backpack"]["entity_id"]
    assert made["Quiver"]["container_entity_id"] == made["Backpack"]["entity_id"]
    assert made["Crossbow bolts"]["container_entity_id"] == made["Quiver"]["entity_id"]
    assert made["Crossbow bolts"]["quantity"] == 22
    assert made["Spare cloak"]["container_entity_id"] == made["Chest"]["entity_id"]
    # What was matched is its item, what was not is the placeholder, and the name is the player's.
    with stack.api(table["player"]) as api:
        unsorted = api.get(
            f"/tenants/{table['tenant_id']}/entities/resolve", params={"slug": ["unsorted"]}
        ).json()[0]["entity_id"]
    assert made["Hydra Zahn"]["prototype_ids"] == [unsorted]
    assert made["Vault key"]["prototype_ids"] == [unsorted]
    assert made["Seil"]["prototype_ids"] != [unsorted]  # read as "rope"
    # What the player wrote about it is theirs to read back.
    assert _notes(stack, table, made["Hydra Zahn"]["entity_id"]) == {
        "Note": "from the cave under the temple",
        "Details": "Weight: 1 lb\nValue: ?",
    }
    assert _notes(stack, table, made["Chest"]["entity_id"]) == {
        "Details": "Place: the inn at Pal Vaz"
    }


def test_a_dry_run_says_what_would_be_made_and_makes_nothing(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table)
    path = _write(tmp_path, FILE)

    done = run_cli(
        stack,
        table["player"],
        tmp_path,
        "inventory",
        "import",
        str(path),
        "-t",
        table["slug"],
        "--dry-run",
    )

    assert done.exit_code == 0, done.output
    text = " ".join(done.output.split())
    assert "9 to make, 7 matched to an item" in text and "2 unsorted" in text
    assert "by title" in text and "by another spelling" in text and "by slug" in text
    assert _instances(stack, table) == {}


def test_a_line_that_cannot_be_made_stops_everything(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table)
    path = _write(
        tmp_path,
        "format: lorenzo-inventory/1\nowner: Ashfang\n\n## Equipped\n- Dagger\n- 9 x Rope\n",
    )

    done = run_cli(
        stack,
        table["player"],
        tmp_path,
        "inventory",
        "import",
        str(path),
        "-t",
        table["slug"],
        "--yes",
    )

    assert done.exit_code == 1
    assert "line 6: 9 x Rope: a stack needs a container" in " ".join(done.output.split())
    assert _instances(stack, table) == {}


def test_a_library_without_the_unsorted_item_says_what_to_run(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table, placeholder=False)
    path = _write(tmp_path, FILE)

    done = run_cli(
        stack,
        table["player"],
        tmp_path,
        "inventory",
        "import",
        str(path),
        "-t",
        table["slug"],
        "--yes",
    )

    assert done.exit_code == 1
    assert "no “unsorted” item" in " ".join(done.output.split())
    assert _instances(stack, table) == {}


def test_a_character_who_has_things_needs_add(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table)
    path = _write(tmp_path, FILE)
    args = ("inventory", "import", str(path), "-t", table["slug"], "--yes")
    assert run_cli(stack, table["player"], tmp_path, *args).exit_code == 0

    again = run_cli(stack, table["player"], tmp_path, *args)

    assert again.exit_code == 1
    assert "already has 9 thing(s)" in " ".join(again.output.split())
    assert len(_instances(stack, table)) == 9


def test_an_export_read_back_with_add_moves_what_it_names_and_makes_the_rest(
    stack: Stack, tmp_path: Path
) -> None:
    table = _table(stack)
    _library(stack, table)
    player, slug = table["player"], table["slug"]
    path = _write(tmp_path, FILE)
    assert (
        run_cli(
            stack, player, tmp_path, "inventory", "import", str(path), "-t", slug, "--yes"
        ).exit_code
        == 0
    )

    exported = run_cli(stack, player, tmp_path, "inventory", "export", "-t", slug)

    assert exported.exit_code == 0, exported.output
    inventory = parse(exported.stdout)
    assert inventory.problems == [] and inventory.owner == "Ashfang" and inventory.library == slug
    top = {line.name: line for line in inventory.equipped}
    assert set(top) == {"Backpack", "Dagger"}
    assert top["Dagger"].weight == 0.5 and top["Dagger"].value == "2 G"
    backpack = {c.name: c for c in top["Backpack"].contents}
    assert backpack["Hydra Zahn"].note == "from the cave under the temple"
    assert backpack["Hydra Zahn"].weight == 1.0 and backpack["Hydra Zahn"].value == "?"
    assert [c.name for c in backpack["Quiver"].contents] == ["Crossbow bolts"]
    assert backpack["Quiver"].contents[0].quantity == 22
    assert {line.name for line in inventory.not_carried} == {"Vault key", "Chest"}
    assert top["Dagger"].ref is not None and top["Dagger"].item is not None

    # Take the dagger out of the hands and put it in the backpack, add a lantern, and read it back.
    edited = exported.stdout.replace("- Dagger", "  - Dagger", 1)
    edited = edited.replace("\n- Backpack", "\n- Backpack", 1)
    lines = edited.splitlines()
    dagger = next(i for i, line in enumerate(lines) if line.strip().startswith("- Dagger"))
    moved = lines.pop(dagger)
    lines.insert(
        next(i for i, line in enumerate(lines) if line.startswith("- Backpack")) + 1, moved
    )
    lines.insert(len(lines), "- Lantern | note: a new one")
    lines.insert(next(i for i, line in enumerate(lines) if line == "## Not carried"), "")
    text = "\n".join(lines) + "\n"
    again = run_cli(
        stack, player, tmp_path, "inventory", "import", str(_write(tmp_path, text, "again.md")),
        "-t", slug, "--add", "--yes",
    )  # fmt: skip

    assert again.exit_code == 0, again.output
    after = _instances(stack, table)
    assert after["Dagger"]["container_entity_id"] == after["Backpack"]["entity_id"]
    assert after["Dagger"]["entity_id"] == exported_id(inventory, "Dagger")  # moved, not made again
    assert len([t for t in after if t == "Dagger"]) == 1
    assert "Lantern" in after


def exported_id(inventory: Any, name: str) -> str:
    return str(next(line for line in inventory.equipped if line.name == name).ref)


def test_the_json_form_goes_both_ways(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table)
    player, slug = table["player"], table["slug"]
    document = {
        "format": "lorenzo-inventory/1",
        "owner": "Ashfang",
        "equipped": [{"name": "Backpack", "contents": [{"name": "Rope", "quantity": 3}]}],
        "not_carried": [{"name": "Trophy", "note": "a skull", "weight": 1}],
    }
    path = _write(tmp_path, json.dumps(document), "inventory.json")

    done = run_cli(stack, player, tmp_path, "inventory", "import", str(path), "-t", slug, "--yes")

    assert done.exit_code == 0, done.output
    made = _instances(stack, table)
    assert made["Rope"]["quantity"] == 3 and made["Trophy"]["container_entity_id"] is None
    exported = json.loads(
        run_cli(stack, player, tmp_path, "inventory", "export", "-t", slug, "--json").stdout
    )
    assert exported["equipped"][0]["contents"][0]["quantity"] == 3
    assert exported["not_carried"][0]["note"] == "a skull"
    assert exported["not_carried"][0]["weight"] == 1.0


def test_a_file_for_another_library_is_refused(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    _library(stack, table)
    path = _write(
        tmp_path,
        "format: lorenzo-inventory/1\nowner: Ashfang\nlibrary: somewhere-else-" + uuid.uuid4().hex[:6]
        + "\n\n## Equipped\n- Dagger\n",
    )  # fmt: skip

    done = run_cli(
        stack,
        table["player"],
        tmp_path,
        "inventory",
        "import",
        str(path),
        "-t",
        table["slug"],
        "--yes",
    )

    assert done.exit_code == 1
    assert "was written for" in " ".join(done.output.split())
    assert _instances(stack, table) == {}
