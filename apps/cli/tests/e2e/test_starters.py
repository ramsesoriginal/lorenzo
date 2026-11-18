"""The starters against the real API (ADR 0491): each applies to an empty library on top of the
neutral one, a second apply finds nothing to do, and what they set up works: modifiers, proficiency,
armour class, dice pools, the sheet templates and the choices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e.helpers import by_slug, make_tenant, run_cli, tenant_id
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
parents = ["wg-archetype-imperial-guardsman"]
stats = { wg_agility = 4, wg_ballistic_skill = 3, wg_toughness = 3, wg_tier = 2, wg_strength = 3, wg_strength_bonus = 1, wg_athletics = 2 }

[[entry]]
slug = "scout"
name = "Scout"
kinds = ["being"]
parents = ["wg-archetype-space-marine-scout"]
stats = { wg_tier = 2 }
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
    # An archetype brings its ratings and its ability; a Species its Speed, Resolve and abilities.
    assert value("wg_pool_ballistic_skill", "scout") == 7  # the archetype's agility 4 + skill 3
    assert value("wg_resolve", "scout") == 3  # willpower 3 - 1, +1 for an Astartes
    assert value("wg_speed", "scout") == 7
    assert value("wg_influence", "scout") == 1  # fellowship 1 - 1 + the archetype's +1
    guard = json.loads(cli("grants", "show", "trooper", "-t", tenant, "--json").stdout)
    assert [d["feature"]["name"] for d in guard["due"]] == ["Look Out, Sir!"]
    scout = json.loads(cli("grants", "show", "scout", "-t", tenant, "--json").stdout)
    assert {d["feature"]["name"] for d in scout["due"]} == {
        "Use the Terrain",
        "Defender of Humanity",
        "Honour the Chapter",
        "Space Marine Implants",
    }
    fearless = json.loads(
        cli("feature", "show", "wg-talent-fearless", "-t", tenant, "--json").stdout
    )
    assert "wg_willpower" in json.dumps(fearless)  # Willpower Rating 4+, checked by the API

    listed = json.loads(cli("starter", "list", "--json").stdout)
    assert [s["name"] for s in listed["starters"]] == ["dnd5e", "neutral", "wrath-and-glory"]


ARMOURY = """
format = 1
name = "armoury"
requires = ["dnd5e"]

[[entry]]
slug = "chain-mail"
name = "Chain mail"
parents = ["armor", "dnd5e-heavy-armor"]
stats = { dnd5e_armor = 16 }

[[entry]]
slug = "leather"
name = "Leather"
parents = ["armor", "dnd5e-light-armor"]
stats = { dnd5e_armor = 11 }

[[entry]]
slug = "shield"
name = "Shield"
parents = ["armor"]
stats = { dnd5e_armor = 2 }

[[entry]]
slug = "knight"
name = "Knight"
kinds = ["being"]
parents = ["dnd5e-fighter"]
stats = { dnd5e_dexterity = 14 }

[[entry]]
slug = "rogue"
name = "Rogue"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 16 }
"""


def test_dnd_armor_class_comes_from_what_is_worn(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("armour")
    tenant = make_tenant(stack, token, kind="play")
    for starter in ("neutral", "dnd5e"):
        applied = run_cli(
            stack, token, tmp_path, "apply", "--starter", starter, "-t", tenant, "--yes"
        )
        assert applied.exit_code == 0, applied.output
    armoury = tmp_path / "armoury.toml"
    armoury.write_text(ARMOURY, encoding="utf-8")
    assert (
        run_cli(stack, token, tmp_path, "apply", str(armoury), "-t", tenant, "--yes").exit_code == 0
    )

    def armor_class(being: str) -> object:
        found = run_cli(
            stack, token, tmp_path, "formula", "preview", "dnd5e_armor_class", "--on", being,
            "-t", tenant, "--json",
        )  # fmt: skip
        assert found.exit_code == 0, found.output
        return json.loads(found.stdout)["value"]

    assert armor_class("knight") == 12  # nothing worn: 10 + Dexterity +2

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)

        def wear(item: str, being: str, active: bool = True) -> None:
            made = api.post(
                f"/tenants/{tid}/item-instances",
                json={
                    "prototype_id": by_slug(api, tid, item)["id"],
                    "container_entity_id": by_slug(api, tid, being)["id"],
                    "active": active,
                },
            )
            assert made.status_code == 201, made.text

        wear("chain-mail", "knight")
        wear("shield", "knight")
        wear("leather", "rogue")
        wear("chain-mail", "rogue", active=False)  # carried, not worn

    assert armor_class("knight") == 18  # chain mail 16, no Dexterity for heavy armor, shield +2
    assert armor_class("rogue") == 14  # leather 11 + Dexterity +3; the chain mail is not worn


FEATURED = """
format = 1
name = "featured"
requires = ["dnd5e"]

[[entry]]
slug = "shell"
name = "Shell"
kinds = ["feature"]
parents = ["dnd5e-armor-class-features"]
stats = { dnd5e_ac_natural = 17 }

[[entry]]
slug = "barbarian"
name = "Barbarian"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 14, dnd5e_constitution = 16 }

[[entry]]
slug = "monk"
name = "Monk"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 16, dnd5e_wisdom = 16 }

[[entry]]
slug = "wizard"
name = "Wizard"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 14 }

[[entry]]
slug = "turtle"
name = "Turtle"
kinds = ["being"]
parents = ["dnd5e-character"]

[[entry]]
slug = "chain-mail"
name = "Chain mail"
parents = ["armor", "dnd5e-heavy-armor"]
stats = { dnd5e_armor = 16 }

[[entry]]
slug = "ring-of-protection"
name = "Ring of protection"
parents = ["gear"]
stats = { dnd5e_ac_bonus = 1 }

[[entry]]
slug = "shield"
name = "Shield"
parents = ["armor"]
stats = { dnd5e_armor = 2 }
"""


def test_dnd_armor_class_takes_the_best_way_a_feature_gives(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("ac-ways")
    tenant = make_tenant(stack, token, kind="play")

    def ok(*args: str) -> Any:
        result = run_cli(stack, token, tmp_path, *args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    for starter in ("neutral", "dnd5e"):
        ok("apply", "--starter", starter, "-t", tenant, "--yes")
    featured = tmp_path / "featured.toml"
    featured.write_text(FEATURED, encoding="utf-8")
    ok("apply", str(featured), "-t", tenant, "--yes")

    def armor_class(being: str) -> object:
        found = ok("formula", "preview", "dnd5e_armor_class", "--on", being, "-t", tenant, "--json")
        return json.loads(found.stdout)["value"]

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)

        def wear(item: str, being: str) -> str:
            made = api.post(
                f"/tenants/{tid}/item-instances",
                json={
                    "prototype_id": by_slug(api, tid, item)["id"],
                    "container_entity_id": by_slug(api, tid, being)["id"],
                    "active": True,
                },
            )
            assert made.status_code == 201, made.text
            return str(made.json()["entity_id"])

        def take_off(instance: str) -> None:
            gone = api.delete(f"/tenants/{tid}/item-instances/{instance}")
            assert gone.status_code == 204, gone.text

        def award(feature: str, being: str) -> None:
            ok("feature", "award", feature, "--to", being, "-t", tenant, "--yes")

        assert armor_class("barbarian") == 12  # no feature yet: 10 + Dexterity +2
        award("dnd5e-unarmored-defense-barbarian", "barbarian")
        assert armor_class("barbarian") == 15  # 10 + Dexterity +2 + Constitution +3
        shield = wear("shield", "barbarian")
        assert armor_class("barbarian") == 17  # a shield still counts
        take_off(shield)
        wear("chain-mail", "barbarian")
        assert armor_class("barbarian") == 16  # armor worn: the way no longer applies
        award("dnd5e-defense", "barbarian")
        assert armor_class("barbarian") == 17  # Defense: +1 while wearing armor
        award("dnd5e-defense", "monk")

        award("dnd5e-unarmored-defense-monk", "monk")
        assert armor_class("monk") == 16  # 10 + Dexterity +3 + Wisdom +3
        wear("shield", "monk")
        assert armor_class("monk") == 15  # a shield ends it: 10 + 3 + 2

        award("dnd5e-mage-armor", "wizard")
        assert armor_class("wizard") == 12  # the spell starts switched off
        ok("feature", "activate", "dnd5e-mage-armor", "--on", "wizard", "-t", tenant, "--yes")
        assert armor_class("wizard") == 15  # 13 + Dexterity +2

        award("shell", "turtle")
        assert armor_class("turtle") == 17  # a natural armor class, no Dexterity
        wear("ring-of-protection", "turtle")
        assert armor_class("turtle") == 18  # a bonus on top of any way

    again = run_cli(stack, token, tmp_path, "plan", "--starter", "dnd5e", "-t", tenant)
    assert again.exit_code == 0, again.output  # the formulas read back as written
