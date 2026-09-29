"""The richer taxonomy and the attributes that used to be dropped (ADR 0146)."""

from __future__ import annotations

from typing import Any

from lorenzo_cli.importer.draft import Ancestry, ItemDraft, draft_item
from lorenzo_cli.importer.mapping import load_mapping
from lorenzo_cli.seed import load_builtin

BUILTIN = load_mapping().mapping
ANCESTRY = load_builtin()

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


def draft(list_name: str, key: str, entry: dict[str, Any]) -> ItemDraft:
    return draft_item(list_name, key, entry, "ListsGear.js", BUILTIN, Ancestry(ANCESTRY))


def parents(result: ItemDraft) -> set[str]:
    return set(result.parents)


def test_the_weapon_families_are_found_from_the_name() -> None:
    for name, family in (
        ("Longsword", "blade"),
        ("Battleaxe", "axe"),
        ("Handaxe", "axe"),
        ("Warhammer", "hammer"),
        ("Maul", "hammer"),
        ("Greatclub", "bludgeon"),
        ("Quarterstaff", "bludgeon"),
        ("Glaive", "polearm"),
        ("Javelin", "spear"),
        ("Whip", "whip"),
    ):
        assert family in draft("weapons", name.lower(), {**PLAIN, "name": name}).parents, name


def test_bows_crossbows_and_slings_are_ranged_without_being_told_so() -> None:
    for name, family in (("Longbow", "bow"), ("Hand crossbow", "crossbow"), ("Sling", "sling")):
        entry = {**PLAIN, "name": name, "list": "ranged", "range": "80/320 ft"}
        result = draft("weapons", name.lower(), entry)
        assert family in result.parents and "ranged-weapon" not in result.parents, name


def test_a_crossbow_is_a_crossbow_not_a_bow_although_the_word_is_in_it() -> None:
    result = draft("weapons", "x", {**PLAIN, "name": "Heavy crossbow", "range": "100/400 ft"})

    assert "crossbow" in result.parents and "bow" not in result.parents


def test_a_firearm_is_a_ranged_weapon_by_being_one() -> None:
    entry = {**PLAIN, "name": "Musket", "list": "firearm", "range": "40/120 ft"}

    result = draft("weapons", "musket", entry)

    assert "firearm" in result.parents
    assert "ranged-weapon" not in result.parents  # a firearm already is one
    assert result.issues == []  # so it needs no melee or ranged row of its own


def test_exotic_weapons_have_a_proficiency_of_their_own() -> None:
    assert "dnd5e-exotic" in draft("weapons", "x", {**PLAIN, "type": "Exotic"}).parents


def test_the_properties_in_the_description_become_categories() -> None:
    entry = {**PLAIN, "name": "Dagger", "description": "Finesse, light, thrown"}

    assert parents(draft("weapons", "dagger", entry)) >= {
        "dnd5e-finesse",
        "dnd5e-light",
        "dnd5e-throwable",
    }


def test_every_property_word_is_recognised_and_only_whole_words() -> None:
    for word, slug in (
        ("Finesse", "dnd5e-finesse"),
        ("Heavy", "dnd5e-heavy"),
        ("Light", "dnd5e-light"),
        ("Loading", "dnd5e-loading"),
        ("Reach", "dnd5e-reach"),
        ("Special", "dnd5e-special"),
        ("Thrown", "dnd5e-throwable"),
        ("Two-handed", "dnd5e-two-handed"),
        ("Versatile (1d8)", "dnd5e-versatile"),
        ("Ammunition", "dnd5e-uses-ammunition"),
    ):
        assert slug in draft("weapons", "x", {**PLAIN, "description": word}).parents, word
    lit = draft("weapons", "x", {**PLAIN, "description": "Delightful, heavyset"})
    assert parents(lit).isdisjoint({"dnd5e-light", "dnd5e-heavy"})


def test_versatile_gives_the_two_handed_die() -> None:
    result = draft("weapons", "x", {**PLAIN, "description": "Versatile (1d10)"})

    assert result.stats["damage_versatile_die"] == 10
    assert result.description == "Versatile (1d10)"


def test_a_special_weapon_carries_its_rules_as_an_entry_of_its_own() -> None:
    entry = {**PLAIN, "name": "Lance", "special": True, "tooltip": "Disadvantage within 5 feet."}

    result = draft("weapons", "lance", entry)

    assert "dnd5e-special" in result.parents
    assert [(i.type, i.title, i.content) for i in result.information] == [
        ("note", "Special rules", "Disadvantage within 5 feet.")
    ]


def test_a_weapon_that_is_not_special_is_not_marked() -> None:
    assert "dnd5e-special" not in draft("weapons", "x", {**PLAIN, "special": False}).parents


def test_the_ammunition_a_weapon_fires_is_a_stat_and_the_property_comes_from_its_description() -> (
    None
):
    entry = {**PLAIN, "name": "Shortbow", "ammo": "arrow", "description": "Ammunition, two-handed"}

    result = draft("weapons", "shortbow", entry)

    assert "dnd5e-uses-ammunition" in result.parents
    assert result.stats["ammo_type"] == "arrow"


def test_a_thrown_flask_that_names_itself_as_ammo_does_not_use_ammunition() -> None:
    entry = {**PLAIN, "name": "Vial of Acid", "ammo": "Acid", "description": "Thrown"}

    result = draft("weapons", "acid", entry)

    assert "dnd5e-uses-ammunition" not in result.parents
    assert result.stats["ammo_type"] == "Acid"


def test_what_the_source_says_about_a_weapon_is_kept_as_stats() -> None:
    entry = {
        **PLAIN,
        "ability": 2,
        "abilitytodamage": True,
        "monkweapon": True,
        "isNotWeapon": True,
        "dc": True,
        "baseWeapon": "longsword",
    }

    stats = draft("weapons", "x", entry).stats

    assert stats["attack_ability"] == "Dexterity"
    assert stats["ability_to_damage"] is True
    assert stats["is_monk_weapon"] is True
    assert stats["is_not_weapon"] is True
    assert stats["has_save_dc"] is True
    assert stats["base_weapon"] == "longsword"


def test_other_names_become_an_entry_and_the_chosen_name_is_not_among_them() -> None:
    entry = {**PLAIN, "name": "Handaxe", "nameAlt": ["Axe, Hand", "Hatchet", "Handaxe"]}

    [aliases] = draft("weapons", "handaxe", entry).information

    assert (aliases.type, aliases.title) == ("alias", "Also known as")
    assert aliases.content == "Axe, Hand\nHatchet"


def test_an_item_with_two_names_keeps_the_one_it_did_not_use() -> None:
    result = draft("armour", "padded", {"name": "Padded", "invName": "Padded armor", "ac": 11})

    assert result.name == "Padded armor"
    [aliases] = result.information
    assert aliases.content == "Padded"


def test_ammunition_can_be_magical_and_has_alternative_names() -> None:
    entry = {
        "name": "Arrows",
        "weight": 0.05,
        "isMagicAmmo": True,
        "alternatives": ["arrows, purple", {"$re": ["purple", "i"]}],
        "icon": "Arrows",
    }

    result = draft("ammo", "arrow", entry)

    assert result.stats["is_magical"] is True
    assert result.information[0].content == "arrows, purple"  # the pattern is not a name


def test_what_armour_asks_and_does_is_kept() -> None:
    entry = {
        "name": "Chain mail",
        "type": "heavy",
        "ac": 16,
        "strReq": 13,
        "stealthdis": True,
        "addMod": True,
    }

    stats = draft("armour", "chain mail", entry).stats

    assert stats["strength_required"] == 13
    assert stats["stealth_disadvantage"] is True
    assert stats["adds_modifier"] is True


def test_a_strength_of_zero_is_not_a_requirement() -> None:
    result = draft("armour", "padded", {"name": "Padded", "strReq": 0})

    assert "strength_required" not in result.stats


def test_a_material_in_the_name_is_a_category() -> None:
    assert "silvered" in draft("weapons", "x", {**PLAIN, "name": "Silvered longsword"}).parents
    assert "adamantine" in draft("armour", "x", {"name": "Adamantine plate", "ac": 18}).parents


def test_consumables_are_recognised_by_name() -> None:
    for name in ("Rations (1 day)", "Oil (flask)", "Acid (vial)", "Torch", "Potion of healing"):
        entry = {"infoname": f"{name} [1 gp]", "name": name, "amount": "", "weight": 1}
        assert "consumable" in draft("gear", name.lower(), entry).parents, name
    rope = {"infoname": "Rope [1 gp]", "name": "Rope", "amount": "", "weight": 10}
    assert "consumable" not in draft("gear", "rope", rope).parents


def test_ammunition_is_a_consumable_because_it_is_used_up() -> None:
    assert "consumable" in Ancestry(ANCESTRY).ancestors("ammunition")


def test_gear_can_be_more_than_one_kind_at_once() -> None:
    entry = {"infoname": "Torch [1 cp]", "name": "Torch", "amount": "", "weight": 1}

    assert parents(draft("gear", "torch", entry)) == {"consumable", "lighting"}


def test_gear_kinds_come_from_the_sources_type_or_the_name() -> None:
    def kind(name: str, type_: str | None = None) -> set[str]:
        entry: dict[str, Any] = {"infoname": f"{name} [1 gp]", "name": name, "weight": 1}
        if type_:
            entry["type"] = type_
        return parents(draft("gear", name.lower(), entry))

    assert "clothing" in kind("Common", "clothes")
    assert "clothing" in kind("Robes")
    assert "tack" in kind("Riding", "saddle")
    assert "tack" in kind("Saddlebags")
    assert "climbing" in kind("Grappling hook")
    assert "climbing" in kind("Rope, hempen (50 feet)")
    assert "nautical" in kind("Fishing tackle")
    assert "writing" in kind("Ink pen")
    assert "camping" in kind("Bedroll")
    assert "medicine" in kind("Healer's kit")
    assert "dnd5e-arcane-focus" in kind("Crystal", "arcane focus")
    assert "dnd5e-druidic-focus" in kind("Totem", "druidic focus")
    assert "dnd5e-holy-symbol" in kind("Amulet", "holy symbol")
    assert "dnd5e-spellcasting-focus" in kind("Component pouch")


def test_the_bundle_size_of_a_gear_entry_is_kept() -> None:
    entry = {"infoname": "Caltrops [1 gp]", "name": "Caltrops", "amount": 20, "weight": 0.1}

    result = draft("gear", "caltrops", entry)

    assert result.stats["bundle_amount"] == 20
    assert result.stats["own_weight"] == 2.0


def test_a_bundle_of_one_is_not_worth_a_stat() -> None:
    entry = {"infoname": "Rations (1 day) [5 sp]", "name": "Rations, days of", "amount": 1}

    assert "bundle_amount" not in draft("gear", "rations", entry).stats
