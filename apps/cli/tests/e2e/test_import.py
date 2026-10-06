"""`lorenzo plan` and `lorenzo apply` against the real API (ADR 0144)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e.helpers import (
    FIXTURES,
    by_slug,
    make_tenant,
    own_stats,
    parent_names,
    run_cli,
    tenant_id,
)
from e2e.stack import Stack


def seeded_tenant(stack: Stack, token: str, tmp_path: Path) -> str:
    tenant = make_tenant(stack, token)
    seeded = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes")
    assert seeded.exit_code == 0, seeded.output
    return tenant


def plan(stack: Stack, token: str, tmp_path: Path, tenant: str, *args: str) -> Any:
    return run_cli(
        stack,
        token,
        tmp_path,
        "plan",
        "--tenant",
        tenant,
        "--review-queue",
        str(tmp_path / "review-queue.json"),
        "--proposed-map",
        str(tmp_path / "proposed.map.toml"),
        *args,
    )


def apply(stack: Stack, token: str, tmp_path: Path, tenant: str, *args: str) -> Any:
    return run_cli(
        stack,
        token,
        tmp_path,
        "apply",
        "--tenant",
        tenant,
        "--review-queue",
        str(tmp_path / "review-queue.json"),
        "--proposed-map",
        str(tmp_path / "proposed.map.toml"),
        *args,
    )


def statuses(document: dict[str, Any]) -> dict[str, str]:
    return {item["slug"]: item["status"] for item in document["items"] if item["slug"]}


def test_a_tenant_that_was_not_seeded_is_told_to_run_seed(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    result = plan(stack, token, tmp_path, tenant, str(FIXTURES / "weapons.js"), "--json")

    assert result.exit_code == 1
    problems = json.loads(result.stdout)["problems"]
    assert any("hasn't been seeded" in p and "lorenzo seed" in p for p in problems)


def test_the_plan_says_what_each_item_will_be(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    result = plan(stack, token, tmp_path, tenant, str(FIXTURES / "weapons.js"), "--json")

    document = json.loads(result.stdout)
    items = {i["key"]: i for i in document["items"]}
    assert result.exit_code == 1  # the moon whip is held for review
    assert statuses(document) == {
        "basic-weapons-purple-sword": "create",
        "basic-weapons-purple-bow": "create",
        "basic-weapons-purple-dart": "create",
        "basic-weapons-moon-whip": "held",
    }
    assert items["purple glare"]["status"] == "skipped"
    assert "Cantrip" in items["purple glare"]["skipped_because"]
    sword = items["purple sword"]
    assert sword["parents"] == ["blade", "dnd5e-martial", "dnd5e-versatile", "melee-weapon"]
    assert sword["stats"] == {
        "sourcebook": "T:W 4, P 149",
        "own_weight": 3.0,
        "damage_dice_count": 1,
        "damage_die": 8,
        "damage_type": "slashing",
        "damage_versatile_die": 10,
        "attack_ability": "Strength",
        "ability_to_damage": True,
    }
    assert items["purple bow"]["parents"] == [
        "bow",
        "dnd5e-heavy",
        "dnd5e-martial",
        "dnd5e-two-handed",
        "dnd5e-uses-ammunition",
    ]
    assert items["purple bow"]["stats"]["range_normal"] == 150
    assert items["purple bow"]["stats"]["range_long"] == 600
    # A thrown dagger-like weapon is melee and ranged, from its range text alone.
    assert items["purple dart"]["parents"] == [
        "dnd5e-finesse",
        "dnd5e-simple",
        "dnd5e-throwable",
        "melee-weapon",
        "ranged-weapon",
    ]
    header = document["header"]
    assert header["tenant"]["kind"] == "repository"
    assert header["counts"]["create"] == 3 and header["counts"]["held"] == 1
    assert header["user_map_sha256"] == "" and header["builtin_version"] == "2"


def test_what_needs_a_decision_goes_to_the_review_queue_with_a_row_to_paste(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    plan(stack, token, tmp_path, tenant, str(FIXTURES / "weapons.js"))

    queue = json.loads((tmp_path / "review-queue.json").read_text())
    value = next(q for q in queue if q["kind"] == "value")
    assert (value["list"], value["key"], value["attribute"]) == ("weapons", "moon whip", "type")
    assert value["value"] == "'Legendary'"
    assert '"legendary" = "attach-form-only"' in value["suggestion"]
    assert {"kind": "attribute", "attribute": "flavour"}.items() <= next(
        q for q in queue if q["kind"] == "attribute"
    ).items()
    proposed = (tmp_path / "proposed.map.toml").read_text()
    assert "[classify.weapons.type]" in proposed
    assert "[attributes.weapons]" in proposed


def test_apply_imports_what_is_resolved_and_leaves_the_rest_for_review(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    result = apply(stack, token, tmp_path, tenant, str(FIXTURES / "weapons.js"), "--yes")

    assert result.exit_code == 1  # one item is still held
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        sword = by_slug(api, tid, "basic-weapons-purple-sword")
        assert sword["name"] == "Purple sword"
        assert parent_names(sword) == ["Blade", "Martial weapon", "Melee weapon", "Versatile"]
        assert own_stats(sword) == {
            "sourcebook": "T:W 4, P 149",
            "own_weight": 3.0,
            "damage_dice_count": 1,
            "damage_die": 8,
            "damage_type": "slashing",
            "damage_versatile_die": 10,
            "attack_ability": "Strength",
            "ability_to_damage": True,
        }
        descriptions = [i for i in sword["information"] if i["type"] == "description"]
        assert [p["content"] for d in descriptions for p in d["payloads"]] == ["Versatile (1d10)"]
        assert {g["name"] for g in sword["stat_groups"]} >= {"physical", "damaging", "sourcebook"}
        dart = by_slug(api, tid, "basic-weapons-purple-dart")
        assert parent_names(dart) == [
            "Finesse",
            "Melee weapon",
            "Ranged weapon",
            "Simple weapon",
            "Throwable",
        ]
        assert own_stats(dart)["own_weight"] == 0.25
        # The property is a category with its own description, so it shows up where it is used,
        # and the category lists every weapon that has it.
        versatile = by_slug(api, tid, "dnd5e-versatile")
        assert [i["type"] for i in versatile["information"]] == ["description"]
        assert "two hands" in versatile["information"][0]["payloads"][0]["content"]
        assert "Purple sword" in [e["name"] for e in versatile["instances"]]
        heavy = by_slug(api, tid, "dnd5e-heavy")
        assert [e["name"] for e in heavy["instances"]] == ["Purple bow"]
        held = api.get(
            f"/tenants/{tid}/entities/resolve", params={"slug": "basic-weapons-moon-whip"}
        )
        assert held.json() == []  # nothing was guessed
        glare = api.get(
            f"/tenants/{tid}/entities/resolve", params={"slug": "basic-weapons-purple-glare"}
        )
        assert glare.json() == []


def test_a_row_in_the_map_settles_it_and_a_second_run_finds_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    map_file = str(FIXTURES / "legendary.map.toml")
    files = str(FIXTURES / "weapons.js")

    dry = plan(stack, token, tmp_path, tenant, files, "--map", map_file, "--json")
    applied = apply(stack, token, tmp_path, tenant, files, "--map", map_file, "--yes")
    again = plan(stack, token, tmp_path, tenant, files, "--map", map_file, "--json")
    twice = apply(stack, token, tmp_path, tenant, files, "--map", map_file, "--yes")

    assert dry.exit_code == 2
    plan_document = json.loads(dry.stdout)
    assert plan_document["new_categories"] == [
        {
            "slug": "hb-legendary",
            "name": "Legendary weapon",
            "under": "dnd5e-weapon-proficiency",
            "axis": "proficiency",
        }
    ]
    assert len(plan_document["header"]["user_map_sha256"]) == 64
    assert applied.exit_code == 0, applied.output
    assert again.exit_code == 0, again.output
    assert set(statuses(json.loads(again.stdout)).values()) == {"exists"}
    assert twice.exit_code == 0
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        whip = by_slug(api, tid, "basic-weapons-moon-whip")
        assert parent_names(whip) == ["Legendary weapon", "Melee weapon", "Whip"]
        category = by_slug(api, tid, "hb-legendary")
        assert parent_names(category) == ["Weapon proficiency (D&D 5e)"]


def test_gear_armour_tools_ammo_and_packs(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    result = apply(stack, token, tmp_path, tenant, str(FIXTURES / "gear.js"), "--yes")

    assert result.exit_code == 0, result.output  # nothing was left unresolved
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        plate = by_slug(api, tid, "basic-armour-purple-plate")
        assert parent_names(plate) == ["Armor", "Heavy armor"]
        assert own_stats(plate) == {
            "armor": 18,
            "own_weight": 60.0,
            "sourcebook": "HB",
            "strength_required": 15,
            "stealth_disadvantage": True,
        }
        robe = by_slug(api, tid, "basic-armour-violet-robe")
        assert parent_names(robe) == ["Armor"]
        assert "armor" not in own_stats(robe)  # a formula has no number to store
        backpack = by_slug(api, tid, "basic-gear-backpack")
        assert parent_names(backpack) == ["Container", "Gear"]
        assert backpack["name"] == "Backpack"
        assert own_stats(backpack)["price"] == 200
        lamp = by_slug(api, tid, "basic-gear-purple-lamp")
        assert own_stats(lamp)["price"] == 550
        bullets = by_slug(api, tid, "basic-gear-violet-bullets")
        assert bullets["name"] == "Bullets, Violet (10)"
        assert parent_names(bullets) == ["Ammunition"]
        assert own_stats(bullets)["own_weight"] == 0.5  # 10 at 0.05 each
        assert own_stats(bullets)["price"] == 50
        tools = by_slug(api, tid, "basic-tools-purplemancer-s-tools")
        assert parent_names(tools) == ["Artisan's tools", "Tool"]
        assert own_stats(tools)["price"] == 150_000  # 1,500 gp
        arrows = by_slug(api, tid, "basic-ammo-purple-arrow")
        assert arrows["name"] == "Arrows, purple"
        assert parent_names(arrows) == ["Ammunition"]
        pack = by_slug(api, tid, "basic-packs-purple-pack")
        assert pack["name"] == "Purple pack"
        assert own_stats(pack)["price"] == 1000
        assert parent_names(pack) == ["Gear"]
