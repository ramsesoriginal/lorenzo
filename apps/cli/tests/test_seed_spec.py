from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from lorenzo_cli.seed import load_builtin
from lorenzo_cli.seed.spec import SeedSpec


def spec_data(**overrides: Any) -> dict[str, Any]:
    """A small valid seed to break one thing at a time."""
    data: dict[str, Any] = {
        "schema": 1,
        "version": "t",
        "group": [{"name": "physical", "layer": "core"}, {"name": "tags", "layer": "core"}],
        "definition": [
            {"name": "weight", "group": "physical", "value_type": "float", "layer": "core"},
            {"name": "is_container", "group": "tags", "value_type": "bool", "layer": "core"},
        ],
        "node": [
            {"slug": "thing", "name": "Thing", "layer": "core"},
            {"slug": "box", "name": "Box", "layer": "core", "parents": ["thing"]},
        ],
        "recipe": [],
    }
    data.update(overrides)
    return data


def test_the_builtin_seed_is_the_taxonomy_and_stats_the_rfc_decided() -> None:
    seed = load_builtin()

    core = [n.slug for n in seed.nodes if n.layer == "core"]
    dnd5e = [n.slug for n in seed.nodes if n.layer == "dnd5e"]
    assert core == [
        "physical-object", "weapon", "melee-weapon", "ranged-weapon", "blade", "axe", "hammer",
        "bludgeon", "spear", "polearm", "whip", "bow", "crossbow", "sling", "firearm", "armor",
        "shield", "tool", "container", "consumable", "ammunition", "gear", "clothing", "climbing",
        "nautical", "lighting", "writing", "camping", "tack", "medicine", "material", "silvered",
        "adamantine",
    ]  # fmt: skip
    assert len(dnd5e) == 28
    assert all(slug.startswith("dnd5e-") for slug in dnd5e)
    assert {g.name for g in seed.groups} == {
        "physical", "economic", "destroyable", "damaging", "tags", "sourcebook",
    }  # fmt: skip
    types = {d.name: d.value_type for d in seed.definitions}
    assert len(types) == 40
    assert types["own_weight"] == "float" and types["price"] == "int"
    assert types["armor"] == "int" and types["armor_formula"] == "text"
    assert types["attack_ability"] == "text" and types["ability_to_damage"] == "bool"
    assert types["bundle_amount"] == "int" and types["damage_versatile_die"] == "int"
    # The properties a category stands for are tags: bool stats, so a node can be found by them.
    assert all(types[name] == "bool" for name in types if name.startswith("is_"))


def test_the_game_system_definitions_belong_to_the_dnd5e_layer() -> None:
    seed = load_builtin()

    dnd5e = {d.name for d in seed.definitions if d.layer == "dnd5e"}
    assert {"damage_dice_count", "damage_die", "damage_type", "attack_ability"} <= dnd5e
    assert {"is_finesse", "is_heavy", "uses_ammunition", "is_monk_weapon"} <= dnd5e
    assert len(dnd5e) == 22
    assert not dnd5e & {"own_weight", "price", "armor", "is_container", "is_consumable"}
    # The group is core, so two game systems never both create it.
    assert next(g for g in seed.groups if g.name == "damaging").layer == "core"


def test_a_shield_is_under_armor_and_the_proficiencies_are_mixins_under_one_root_each() -> None:
    seed = load_builtin()

    assert seed.node("shield").parents == ["armor"]
    assert seed.node("container").tags == ["is_container"]
    assert seed.node("dnd5e-martial").parents == ["dnd5e-weapon-proficiency"]
    assert seed.node("dnd5e-weapon-proficiency").parents == []
    forms = {
        "physical-object": [], "weapon": ["physical-object"], "melee-weapon": ["weapon"],
        "ranged-weapon": ["weapon"], "armor": ["physical-object"], "tool": ["physical-object"],
        "container": ["physical-object"], "consumable": ["physical-object"],
        "gear": ["physical-object"],
    }  # fmt: skip
    assert {slug: seed.node(slug).parents for slug in forms} == forms


def test_the_weapon_families_hang_where_their_kind_of_attack_is() -> None:
    seed = load_builtin()

    for family in ("blade", "axe", "hammer", "bludgeon", "spear", "polearm", "whip"):
        assert seed.node(family).parents == ["weapon"], family  # melee or ranged is a mixin apart
    for ranged in ("bow", "crossbow", "sling", "firearm"):
        assert seed.node(ranged).parents == ["ranged-weapon"], ranged  # so they reach far already


def test_ammunition_is_a_consumable_and_the_kinds_of_gear_are_gear() -> None:
    seed = load_builtin()

    assert seed.node("ammunition").parents == ["consumable"]
    assert seed.node("consumable").tags == ["is_consumable"]
    for kind in ("clothing", "climbing", "nautical", "lighting", "writing", "camping", "tack"):
        assert seed.node(kind).parents == ["gear"], kind


def test_every_weapon_property_is_a_node_with_a_tag_and_a_description() -> None:
    seed = load_builtin()

    properties = [n for n in seed.nodes if n.parents == ["dnd5e-weapon-property"]]
    assert len(properties) == 10
    for prop in properties:
        assert len(prop.tags) == 1 and prop.description, prop.slug


def test_the_weight_recipe_sums_own_weight_and_contents() -> None:
    seed = load_builtin()

    by_stat = {r.stat: r for r in seed.recipes}
    assert by_stat["contents_weight"].kind == "contents"
    assert by_stat["contents_weight"].source == "weight"
    assert by_stat["weight"].kind == "sum"
    assert by_stat["weight"].terms == ["own_weight", "contents_weight"]
    assert {r.node for r in seed.recipes} == {"physical-object"}


def test_a_small_valid_seed_loads() -> None:
    assert len(SeedSpec.model_validate(spec_data()).nodes) == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"node": [{"slug": "a", "name": "A", "layer": "core"}] * 2},
            "listed twice",
        ),
        (
            {
                "node": [
                    {"slug": "box", "name": "Box", "layer": "core", "parents": ["thing"]},
                    {"slug": "thing", "name": "Thing", "layer": "core"},
                ]
            },
            "must be listed first",
        ),
        (
            {"node": [{"slug": "has space", "name": "X", "layer": "core"}]},
            "not a valid slug",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "core", "tags": ["weight"]}]},
            "not a bool definition",
        ),
        (
            {"node": [{"slug": "dnd5e-a", "name": "A", "layer": "core"}]},
            "exactly when the layer is dnd5e",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "dnd5e"}]},
            "exactly when the layer is dnd5e",
        ),
        (
            {
                "node": [
                    {"slug": "dnd5e-a", "name": "A", "layer": "dnd5e"},
                    {"slug": "b", "name": "B", "layer": "core", "parents": ["dnd5e-a"]},
                ]
            },
            "has a parent in layer",
        ),
        (
            {"definition": [{"name": "x", "group": "nope", "value_type": "int", "layer": "core"}]},
            "no group",
        ),
        (
            {"recipe": [{"node": "thing", "stat": "weight", "kind": "sum", "layer": "core"}]},
            "sum takes terms",
        ),
        (
            {
                "recipe": [
                    {
                        "node": "thing",
                        "stat": "weight",
                        "kind": "contents",
                        "source": "weight",
                        "terms": ["weight"],
                        "layer": "core",
                    }
                ]
            },
            "contents takes a source",
        ),
        (
            {
                "recipe": [
                    {
                        "node": "gone",
                        "stat": "weight",
                        "kind": "sum",
                        "terms": ["weight"],
                        "layer": "core",
                    }
                ]
            },
            "no node",
        ),
        ({"unknown_key": 1}, "Extra inputs"),
    ],
)
def test_a_broken_seed_is_refused_with_a_reason(change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SeedSpec.model_validate(spec_data(**change))
