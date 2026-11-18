"""The starters against the real API (ADR 0491): each applies to an empty library on top of the
neutral one, a second apply finds nothing to do, and what they set up works: modifiers, proficiency,
armour class, dice pools, the sheet templates and the choices."""

from __future__ import annotations

import json
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack


def test_the_starters_apply_and_work(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("starters")
    tenant = make_tenant(stack, token, kind="play")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    refused = cli("plan", "--starter", "dnd5e", "-t", tenant, "--json")
    assert refused.exit_code == 1  # it requires the neutral starter, and says so
    assert any("requires neutral" in p for p in json.loads(refused.stdout)["problems"])

    for starter in ("neutral", "dnd5e", "wrath-and-glory"):
        applied = cli("apply", "--starter", starter, "-t", tenant, "--yes", "--json")
        assert applied.exit_code == 0, f"{starter}: {applied.output[-3000:]}"
        again = cli("plan", "--starter", starter, "-t", tenant)
        assert again.exit_code == 0, f"{starter}: {again.output[-3000:]} {again.stderr[-2000:]}"

    hero = tmp_path / "hero.toml"
    hero.write_text(
        """
format = 1
name = "heroes"
requires = ["dnd5e", "wrath-and-glory"]

[[entry]]
slug = "hero"
name = "Hero"
kinds = ["being"]
parents = ["dnd5e-fighter"]
stats = { dnd5e_dexterity = 15, dnd5e_strength = 8, dnd5e_level = 5 }

[[entry]]
slug = "trooper"
name = "Trooper"
kinds = ["being"]
parents = ["wg-archetype"]
stats = { wg_agility = 4, wg_ballistic_skill = 3, wg_toughness = 3, wg_tier = 2, wg_strength = 3, wg_strength_bonus = 1, wg_athletics = 2 }
""",
        encoding="utf-8",
    )
    assert cli("apply", str(hero), "-t", tenant, "--yes").exit_code == 0

    def value(stat: str, on: str) -> object:
        found = cli("formula", "preview", stat, "--on", on, "-t", tenant, "--json")
        assert found.exit_code == 0, found.output
        return json.loads(found.stdout)["value"]

    assert value("dnd5e_strength_mod", "hero") == -1  # floor(8 / 2 - 5)
    assert value("dnd5e_dexterity_mod", "hero") == 2
    assert value("dnd5e_proficiency_bonus", "hero") == 3  # level 5
    assert value("dnd5e_armor_class", "hero") == 12  # 10 + min(2, no cap) + no shield
    assert value("wg_pool_ballistic_skill", "trooper") == 7  # agility 4 + skill 3
    assert str(value("wg_roll_ballistic_skill", "trooper")).lower() == "7d6"
    assert value("wg_max_wounds", "trooper") == 7  # tier 2 x 2 + toughness 3
    assert value("wg_resilience", "trooper") == 4  # toughness 3 + armour 0 + 1
    # What the character starts with fills the rest: attributes at 1, skills at 0, Speed 6.
    assert value("wg_pool_athletics", "trooper") == 6  # strength 3 + bonus 1 + athletics 2
    assert value("wg_defence", "trooper") == 1  # initiative 1 - 1, and a trait is at least 1
    assert value("wg_resolve", "trooper") == 1  # willpower 1 - 1, at least 1
    assert value("wg_influence", "trooper") == 1  # fellowship 1 - 1, at least 1
    assert value("wg_passive_awareness", "trooper") == 1  # half of intellect 1 + 0, rounded up
    assert value("wg_max_traumatic_injuries", "trooper") == 3  # tier 2 + 1
    assert value("wg_speed", "trooper") == 6  # no armour with Bulk

    sheets = json.loads(cli("template", "matching", "hero", "-t", tenant, "--json").stdout)
    assert "Character sheet (D&D 5e)" in {t["name"] for t in sheets["templates"]}
    choices = json.loads(cli("grants", "show", "hero", "-t", tenant, "--json").stdout)
    assert [c["label"] for c in choices["open_choices"]] == ["Fighting style"]
    talent = json.loads(cli("grants", "show", "trooper", "-t", tenant, "--json").stdout)
    assert [c["label"] for c in talent["open_choices"]] == ["Talent"]

    listed = json.loads(cli("starter", "list", "--json").stdout)
    assert [s["name"] for s in listed["starters"]] == ["dnd5e", "neutral", "wrath-and-glory"]
