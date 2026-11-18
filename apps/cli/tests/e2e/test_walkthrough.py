"""The README's walkthrough, command for command, against the real API (RFC 0057): an empty table
gets the starters, a campaign and a Fighter, whose armour class the API works out and whose open
choice is answered. Slugs get a suffix, since one database holds every test's tenants."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from e2e.helpers import run_cli
from e2e.stack import Stack

PARTY = """
format = 1
name = "party"
requires = ["dnd5e"]

[[entry]]
slug = "bruna"
name = "Bruna"
kinds = ["being"]
parents = ["dnd5e-fighter"]
stats = { dnd5e_strength = 16, dnd5e_dexterity = 14, dnd5e_level = 3 }
"""


def test_the_walkthrough(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("walkthrough-" + uuid.uuid4().hex[:6])
    table = f"our-table-{uuid.uuid4().hex[:6]}"

    def ok(*args: str) -> Any:
        result = run_cli(stack, token, tmp_path, *args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def data(*args: str) -> Any:
        return json.loads(ok(*args, "--json").stdout)

    ok("tenant", "create", "Our table", "--slug", table, "--kind", "play")
    assert [s["name"] for s in data("starter", "list")["starters"]] == [
        "dnd5e",
        "neutral",
        "wrath-and-glory",
    ]
    ok("apply", "--starter", "neutral", "-t", table, "--yes")
    ok("apply", "--starter", "dnd5e", "-t", table, "--yes")
    shown = " ".join(ok("system", "show", "dnd5e", "-t", table).output.split())
    assert "dnd5e" in shown
    ok(
        "campaign",
        "create",
        "Lost Mine",
        "--slug",
        "lost-mine",
        "--system",
        "dnd5e",
        "-t",
        table,
        "--yes",
    )

    party = tmp_path / "party.toml"
    party.write_text(PARTY, encoding="utf-8")
    ok("apply", str(party), "-t", table, "--yes")
    preview = data("formula", "preview", "dnd5e_armor_class", "--on", "bruna", "-t", table)
    assert preview["value"] == 12
    open_choices = data("grants", "show", "bruna", "-t", table)["open_choices"]
    assert [c["label"] for c in open_choices] == ["Fighting style"]
    ok("grants", "apply", "bruna", "-t", table, "--pick", "Fighting style=Defense", "--yes")
    assert data("grants", "show", "bruna", "-t", table)["open_choices"] == []
    sheet = " ".join(
        ok("being", "show", "bruna", "-t", table, "--campaign", "lost-mine").output.split()
    )
    assert "Bruna" in sheet
    ok("check", "-t", table)
    ok("export", "dnd5e", "-t", table, "-o", str(tmp_path / "my-dnd5e.toml"))
    exported = (tmp_path / "my-dnd5e.toml").read_text(encoding="utf-8")
    assert 'slug = "dnd5e"' in exported and "dnd5e_armor_class" in exported
