from __future__ import annotations

from typing import Any

from lorenzo_cli.importer.draft import Ancestry, ItemDraft, draft_item
from lorenzo_cli.importer.mapping import Mapping, load_mapping
from lorenzo_cli.seed import load_builtin

BUILTIN = load_mapping().mapping


def draft(
    list_name: str,
    key: str,
    entry: dict[str, Any],
    mapping: Mapping = BUILTIN,
    file: str = "ListsGear.js",
) -> ItemDraft:
    return draft_item(list_name, key, entry, file, mapping, Ancestry(load_builtin()))


LONGSWORD = {
    "name": "Longsword",
    "source": [["SRD", 66], ["P", 149]],
    "list": "melee",
    "ability": 1,
    "type": "Martial",
    "damage": [1, 8, "slashing"],
    "range": "Melee",
    "weight": 3,
    "description": "Versatile (1d10)",
    "abilitytodamage": True,
    "regExpSearch": {"$re": ["long.*sword", "i"]},
}


def test_a_weapon_is_named_parented_and_given_its_stats() -> None:
    result = draft("weapons", "longsword", LONGSWORD)

    assert result.name == "Longsword"
    assert result.parents == ["dnd5e-martial", "melee-weapon"]  # `weapon` is implied by melee
    assert result.stats == {
        "sourcebook": "SRD 66, P 149",
        "own_weight": 3.0,
        "damage_dice_count": 1,
        "damage_die": 8,
        "damage_type": "slashing",
    }
    assert result.description == "Versatile (1d10)"
    assert result.issues == [] and result.skip_reason is None
    assert result.namespace == "basic"


def test_a_thrown_weapon_is_melee_and_ranged_from_its_range_text() -> None:
    entry = {**LONGSWORD, "range": "Melee, 20/60 ft", "type": "Simple", "list": "melee"}

    result = draft("weapons", "dagger", entry)

    assert result.parents == ["dnd5e-simple", "melee-weapon", "ranged-weapon"]
    assert (result.stats["range_normal"], result.stats["range_long"]) == (20, 60)


def test_a_weapon_with_no_list_gets_its_reach_from_its_range() -> None:
    entry = {k: v for k, v in LONGSWORD.items() if k != "list"}

    assert draft("weapons", "x", entry).parents == ["dnd5e-martial", "melee-weapon"]


def test_a_weapon_that_says_neither_melee_nor_ranged_is_held() -> None:
    entry = {k: v for k, v in LONGSWORD.items() if k not in ("list", "range")}

    result = draft("weapons", "x", entry)

    assert [i.kind for i in result.issues] == ["reach"]
    assert "melee-weapon" in result.issues[0].suggestion


def test_a_row_that_settles_the_reach_counts_even_if_it_has_no_parents() -> None:
    entry = {**LONGSWORD, "list": "improvised", "range": "", "type": "Improvised Weapons"}

    result = draft("weapons", "improvised weapon", entry)

    assert result.issues == []
    assert result.parents == ["dnd5e-improvised", "weapon"]


def test_what_the_sheet_treats_as_not_an_item_is_skipped_with_the_reason_first_found() -> None:
    entry = {**LONGSWORD, "type": "Cantrip", "list": "spell"}

    result = draft("weapons", "fire bolt", entry)

    assert result.skip_reason == "type is 'Cantrip', which the map says isn't an item"


def test_an_unknown_value_is_held_with_a_row_to_paste() -> None:
    result = draft("weapons", "moon whip", {**LONGSWORD, "type": "Exotic"})

    issue = next(i for i in result.issues if i.kind == "value")
    assert (issue.attribute, issue.value) == ("type", "'Exotic'")
    assert issue.suggestion.startswith("[classify.weapons.type]\n")
    assert '"exotic" = "attach-form-only"' in issue.suggestion


def test_a_value_is_matched_case_insensitively() -> None:
    assert draft("weapons", "x", {**LONGSWORD, "type": "MARTIAL"}).issues == []
    assert "dnd5e-martial" in draft("weapons", "x", {**LONGSWORD, "type": "martial"}).parents


def test_the_project_map_can_create_a_category_under_an_axis_root() -> None:
    mapping = load_mapping(
        "schema = 1\n[classify.weapons.type]\n"
        'exotic = { disposition = "create-under", axis = "proficiency", slug = "hb-exotic", name = "Exotic weapon" }\n'
    ).mapping

    result = draft("weapons", "moon whip", {**LONGSWORD, "type": "Exotic"}, mapping)

    assert result.issues == []
    assert "hb-exotic" in result.parents
    [category] = result.categories
    assert (category.slug, category.parent, category.axis) == (
        "hb-exotic",
        "dnd5e-weapon-proficiency",
        "proficiency",
    )


def test_a_fail_row_refuses_the_item() -> None:
    mapping = load_mapping('schema = 1\n[classify.weapons.type]\nexotic = "fail"\n').mapping

    result = draft("weapons", "x", {**LONGSWORD, "type": "Exotic"}, mapping)

    assert [i.kind for i in result.issues] == ["fail"]


def test_attach_form_only_files_it_under_its_form_and_says_uncategorised() -> None:
    mapping = load_mapping(
        'schema = 1\n[classify.weapons.type]\nexotic = "attach-form-only"\n'
    ).mapping

    result = draft("weapons", "x", {**LONGSWORD, "type": "Exotic"}, mapping)

    assert result.issues == [] and result.uncategorised is True
    assert result.parents == ["melee-weapon"]


def test_armour_takes_its_tier_and_keeps_its_form() -> None:
    entry = {
        "name": "Chain mail",
        "source": [["SRD", 63]],
        "type": "heavy",
        "ac": 16,
        "weight": 55,
        "strReq": 13,
        "stealthdis": True,
        "regExpSearch": {"$re": ["chain mail", "i"]},
    }

    result = draft("armour", "chain mail", entry)

    assert result.parents == ["armor", "dnd5e-heavy-armor"]
    assert result.stats["armor"] == 16 and result.stats["own_weight"] == 55.0


def test_armour_prefers_its_inventory_name() -> None:
    assert draft(
        "armour", "padded", {"name": "Padded", "invName": "Padded armor", "ac": 11}
    ).name == ("Padded armor")


def test_what_the_sheet_uses_to_work_out_ac_is_not_an_item() -> None:
    assert draft(
        "armour", "unarmored", {"name": "Unarmored", "ac": 10, "list": "firstlist"}
    ).skip_reason
    assert draft(
        "armour", "mage armor", {"name": "Mage armor", "ac": 13, "list": "magic"}
    ).skip_reason


def test_an_ac_formula_is_noted_and_not_stored() -> None:
    result = draft("armour", "robe", {"name": "Robe", "ac": "10+Wis"})

    assert "armor" not in result.stats
    assert "formula" in result.notes[0]


def test_a_shield_is_found_by_its_name() -> None:
    result = draft("armour", "shield", {"name": "Shield", "ac": 2, "weight": 6})

    assert result.parents == ["shield"]  # the armor form is implied


def test_gear_takes_its_name_and_price_from_the_display_string_and_its_weight_times_amount() -> (
    None
):
    entry = {
        "infoname": "Arrows (20) [1 gp]",
        "name": "Arrows",
        "amount": 20,
        "weight": 0.05,
        "type": "ammunition",
    }

    result = draft("gear", "arrows (20)", entry)

    assert result.name == "Arrows (20)"
    assert result.stats == {"price": 100, "own_weight": 1.0}
    assert result.parents == ["ammunition"]  # bundles of ammunition replace the gear form


def test_gear_with_an_unlisted_kind_is_just_gear() -> None:
    entry = {
        "infoname": "Saddle [10 gp]",
        "name": "Saddle",
        "amount": "",
        "weight": 25,
        "type": "saddle",
    }

    result = draft("gear", "saddle", entry)

    assert result.parents == ["gear"] and result.uncategorised is True and result.issues == []


def test_a_container_is_recognised_by_a_curated_name() -> None:
    entry = {"infoname": "Backpack [2 gp]", "name": "Backpack", "amount": "", "weight": 5}

    assert draft("gear", "backpack", entry).parents == ["container", "gear"]
    for name in ("Pouch", "Sack", "Quiver", "Chest", "Case, map or scroll", "Component pouch"):
        entry = {"infoname": f"{name} [1 gp]", "name": name, "amount": "", "weight": 1}
        assert "container" in draft("gear", name.lower(), entry).parents, name
    plain = {"infoname": "Crowbar [2 gp]", "name": "Crowbar", "amount": "", "weight": 5}
    assert "container" not in draft("gear", "crowbar", plain).parents


def test_gear_without_a_readable_price_is_held() -> None:
    entry = {"infoname": "Gem [3 marks]", "name": "Gem", "amount": "", "weight": 0}

    result = draft("gear", "gem", entry)

    assert [i.kind for i in result.issues] == ["price"]


def test_tools_take_their_proficiency() -> None:
    entry = {
        "infoname": "Alchemist's supplies [50 gp]",
        "name": "Alchemist's supplies",
        "amount": "",
        "weight": 8,
        "type": "artisan's tools",
    }

    result = draft("tools", "alchemist's supplies", entry)

    assert result.parents == ["dnd5e-artisans-tools", "tool"]
    assert result.stats["price"] == 5000


def test_a_tool_of_no_kind_is_just_a_tool() -> None:
    entry = {"infoname": "Disguise kit [25 gp]", "name": "Disguise kit", "amount": "", "weight": 3}

    assert draft("tools", "disguise kit", entry).parents == ["tool"]


def test_ammunition_uses_its_inventory_name_and_weighs_one() -> None:
    entry = {"name": "Bolts", "invName": "Crossbow bolts", "weight": 0.075, "icon": "Arrows"}

    result = draft("ammo", "bolt", entry)

    assert result.name == "Crossbow bolts"
    assert result.parents == ["ammunition"]
    assert result.stats == {"own_weight": 0.075}


def test_a_pack_has_a_price_in_its_name_and_carries_its_items() -> None:
    entry = {
        "name": "Explorer's pack (10 gp)",
        "source": [["SRD", 70]],
        "items": [["Backpack, with:", "", 5], ["Rations, days of", 10, 2]],
    }

    result = draft("packs", "explorer", entry)

    assert result.name == "Explorer's pack"
    assert result.stats["price"] == 1000
    assert result.pack_items == entry["items"]
    assert result.parents == ["gear"]


def test_attributes_no_rule_mentions_are_listed_and_do_not_block() -> None:
    result = draft("weapons", "x", {**LONGSWORD, "flavour": "loud", "another": 1})

    assert result.unmapped == ["flavour", "another"]
    assert result.issues == []


def test_the_namespace_follows_the_file_the_entry_came_from() -> None:
    mapping = load_mapping('schema = 1\n[namespaces]\n"mine.js" = "hb-alice"\n').mapping

    assert draft("weapons", "x", LONGSWORD, mapping, file="mine.js").namespace == "hb-alice"
    assert draft("weapons", "x", LONGSWORD, mapping, file="ListsGear.js").namespace == "basic"


def test_an_entry_with_no_name_is_held() -> None:
    result = draft("ammo", "x", {"weight": 1})

    assert [i.kind for i in result.issues] == ["name"]


def test_ancestry_drops_a_parent_that_another_implies() -> None:
    ancestry = Ancestry(load_builtin())

    assert ancestry.reduce({"weapon", "melee-weapon", "dnd5e-martial"}) == [
        "dnd5e-martial",
        "melee-weapon",
    ]
    assert ancestry.reduce({"gear", "container"}) == ["container", "gear"]
    assert ancestry.reduce(set()) == []
    ancestry.add("hb-x", "dnd5e-weapon-proficiency")
    assert ancestry.reduce({"hb-x", "dnd5e-weapon-proficiency"}) == ["hb-x"]
