from __future__ import annotations

from typing import Any

from lorenzo_cli.importer.draft import Ancestry, ItemDraft, draft_item
from lorenzo_cli.importer.mapping import Mapping, load_mapping
from lorenzo_cli.importer.vocabulary import load as load_builtin

BUILTIN = load_mapping().mapping


def draft(
    list_name: str,
    key: str,
    entry: dict[str, Any],
    mapping: Mapping = BUILTIN,
    file: str = "ListsGear.js",
) -> ItemDraft:
    return draft_item(list_name, key, entry, file, mapping, Ancestry(load_builtin()))


# A weapon with nothing in its name or description that a rule reacts to.
PLAIN = {
    "name": "Stick thing",
    "source": [["HB", 0]],
    "list": "melee",
    "type": "Martial",
    "damage": [1, 6, "bludgeoning"],
    "range": "Melee",
    "weight": 2,
}

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
    # A blade, martial, versatile (the description says so) and melee; `weapon` is implied.
    assert result.parents == ["blade", "dnd5e-martial", "dnd5e-versatile", "melee-weapon"]
    assert result.stats == {
        "sourcebook": "SRD 66, P 149",
        "own_weight": 3.0,
        "dnd5e_damage": "1d8",
        "dnd5e_damage_type": "slashing",
        "dnd5e_damage_versatile": "1d10",
        "dnd5e_attack_ability": "Strength",
        "dnd5e_ability_to_damage": True,
    }
    assert result.description == "Versatile (1d10)"
    assert result.issues == [] and result.skip_reason is None
    assert result.namespace == "basic"


def test_a_thrown_weapon_is_melee_and_ranged_from_its_range_text() -> None:
    entry = {**PLAIN, "range": "Melee, 20/60 ft", "type": "Simple", "list": "melee"}

    result = draft("weapons", "dagger", entry)

    assert result.parents == ["dnd5e-simple", "melee-weapon", "ranged-weapon"]
    assert (result.stats["dnd5e_range_normal"], result.stats["dnd5e_range_long"]) == (20, 60)


def test_a_weapon_with_no_list_gets_its_reach_from_its_range() -> None:
    entry = {k: v for k, v in PLAIN.items() if k != "list"}

    assert draft("weapons", "x", entry).parents == ["dnd5e-martial", "melee-weapon"]


def test_a_weapon_that_says_neither_melee_nor_ranged_is_held() -> None:
    entry = {k: v for k, v in PLAIN.items() if k not in ("list", "range")}

    result = draft("weapons", "x", entry)

    assert [i.kind for i in result.issues] == ["reach"]
    assert "melee-weapon" in result.issues[0].suggestion


def test_a_row_that_settles_the_reach_counts_even_if_it_has_no_parents() -> None:
    entry = {**PLAIN, "list": "improvised", "range": "", "type": "Improvised Weapons"}

    result = draft("weapons", "improvised weapon", entry)

    assert result.issues == []
    assert result.parents == ["dnd5e-improvised", "weapon"]


def test_what_the_sheet_treats_as_not_an_item_is_skipped_with_the_reason_first_found() -> None:
    entry = {**PLAIN, "type": "Cantrip", "list": "spell"}

    result = draft("weapons", "fire bolt", entry)

    assert result.skip_reason == "type is 'Cantrip', which the map says isn't an item"


def test_an_unknown_value_is_held_with_a_row_to_paste() -> None:
    result = draft("weapons", "moon whip", {**PLAIN, "type": "Legendary"})

    issue = next(i for i in result.issues if i.kind == "value")
    assert (issue.attribute, issue.value) == ("type", "'Legendary'")
    assert issue.suggestion.startswith("[classify.weapons.type]\n")
    assert '"legendary" = "attach-form-only"' in issue.suggestion


def test_a_value_is_matched_case_insensitively() -> None:
    assert draft("weapons", "x", {**PLAIN, "type": "MARTIAL"}).issues == []
    assert "dnd5e-martial" in draft("weapons", "x", {**PLAIN, "type": "martial"}).parents


def test_the_project_map_can_create_a_category_under_an_axis_root() -> None:
    mapping = load_mapping(
        "schema = 1\n[classify.weapons.type]\n"
        'exotic = { disposition = "create-under", axis = "proficiency", slug = "hb-exotic", name = "Exotic weapon" }\n'
    ).mapping

    result = draft("weapons", "moon whip", {**PLAIN, "type": "Exotic"}, mapping)

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

    result = draft("weapons", "x", {**PLAIN, "type": "Exotic"}, mapping)

    assert [i.kind for i in result.issues] == ["fail"]


def test_attach_form_only_files_it_under_its_form_and_says_uncategorised() -> None:
    mapping = load_mapping(
        'schema = 1\n[classify.weapons.type]\nexotic = "attach-form-only"\n'
    ).mapping

    result = draft("weapons", "x", {**PLAIN, "type": "Exotic"}, mapping)

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
    assert result.stats["dnd5e_armor"] == 16 and result.stats["own_weight"] == 55.0


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


def test_a_shield_is_found_by_its_name() -> None:
    result = draft("armour", "shield", {"name": "Shield", "ac": 2, "weight": 6})

    assert result.parents == ["shield"]  # the armor form is implied
    # D&D adds a shield's armour class to the wearer's, whatever the shield is called.
    tower = draft("armour", "tower shield", {"name": "Tower shield", "type": "", "ac": 3})
    assert tower.parents == ["shield"] and tower.stats["dnd5e_armor"] == 3


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
    assert result.stats == {"dnd5e_price": 100, "own_weight": 1.0, "bundle_amount": 20}
    assert result.parents == ["ammunition"]  # bundles of ammunition replace the gear form


def test_gear_with_an_unlisted_kind_is_just_gear() -> None:
    entry = {
        "infoname": "Anvil [10 gp]",
        "name": "Anvil",
        "amount": "",
        "weight": 25,
        "type": "smithing",
    }

    result = draft("gear", "anvil", entry)

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
    assert result.stats["dnd5e_price"] == 5000


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
    assert result.stats["dnd5e_price"] == 1000
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


def test_the_sheets_own_ways_of_working_out_armour_class_are_features() -> None:
    rage = draft("armour", "rage", {"name": "Thick hide", "ac": "10+Con", "list": "firstlist"})

    assert rage.armor_class_way and rage.skip_reason is None
    assert rage.parents == ["dnd5e-armor-class-features"]
    assert rage.stats == {"dnd5e_ac_10_dex_con": True}  # MPMB adds Dexterity unless it says not


def test_armour_whose_ac_is_a_formula_stays_an_item_that_gives_the_way_while_worn() -> None:
    robe = draft("armour", "robe", {"name": "Robe", "ac": "10+Wis", "weight": 4})
    odd = draft("armour", "robe", {"name": "Odd robe", "ac": "10+Int"})

    assert not robe.armor_class_way and robe.parents == ["armor"]
    assert robe.stats["dnd5e_ac_10_dex_wis"] is True and "dnd5e_armor_formula" not in robe.stats
    assert odd.stats["dnd5e_armor_formula"] == "10+Int"  # no tag for it: kept as text


def test_a_way_without_dexterity_is_a_natural_armour_class() -> None:
    shell = draft("armour", "shell", {"name": "Shell", "ac": 17, "dex": -10, "list": "firstlist"})
    scales = draft("armour", "scales", {"name": "Scales", "ac": 13, "list": "firstlist"})

    assert shell.stats == {"dnd5e_ac_natural": 17}
    assert scales.stats == {"dnd5e_ac_13_dex": True}


def test_a_way_the_starter_has_no_tag_for_is_held_with_a_way_out() -> None:
    odd = draft("armour", "bladesong", {"name": "Bladesong", "ac": "10+Int", "list": "magic"})

    assert [i.attribute for i in odd.issues] == ["ac"]
    assert "no tag" in odd.issues[0].reason


def test_a_way_is_the_systems_alone() -> None:
    from lorenzo_cli.importer.draft import default_parts, part_view

    way = draft("armour", "rage", {"name": "Thick hide", "ac": "10+Con", "list": "firstlist"})

    assert part_view(way, "neutral", default_parts()).skip_reason
    system = part_view(way, "system", default_parts())
    assert system.skip_reason is None and system.name == "Thick hide"  # not a prototype
