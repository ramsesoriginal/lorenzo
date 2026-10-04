from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from lorenzo_cli.seed import load_builtin
from lorenzo_cli.seed.spec import LAYERS, SeedSpec, available


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


EQUIPMENT = [
    "weapon", "melee-weapon", "ranged-weapon", "blade", "axe", "hammer", "bludgeon", "spear",
    "polearm", "whip", "bow", "crossbow", "sling", "firearm", "armor", "shield", "tool",
    "container", "consumable", "ammunition", "gear", "clothing", "climbing", "nautical",
    "lighting", "writing", "camping", "tack", "medicine", "material", "silvered", "adamantine",
]  # fmt: skip
# What RFC 0033 moved from core to D&D 5e: their meanings are D&D's (ADR 0175).
THE_EIGHT = {
    "price", "armor", "armor_formula", "strength_required", "stealth_disadvantage", "adds_modifier",
    "range_normal", "range_long",
}  # fmt: skip


def test_the_seed_is_four_layers_in_dependency_order() -> None:
    seed = load_builtin()

    assert LAYERS == ("core", "equipment", "dnd5e", "dnd5e-equipment")
    assert seed.version == "2"
    assert [n.layer for n in seed.nodes] == sorted((n.layer for n in seed.nodes), key=LAYERS.index)
    counts = {
        layer: (
            sum(g.layer == layer for g in seed.groups),
            sum(d.layer == layer for d in seed.definitions),
            sum(n.layer == layer for n in seed.nodes),
            sum(a.layer == layer for a in seed.attachments),
            sum(r.layer == layer for r in seed.recipes),
        )
        for layer in LAYERS
    }
    # Groups, definitions, categories, attachments, recipes.
    assert counts == {
        "core": (3, 10, 1, 0, 2),
        "equipment": (0, 0, 32, 0, 0),
        "dnd5e": (3, 30, 30, 0, 0),
        "dnd5e-equipment": (0, 0, 0, 6, 0),
    }


def test_core_is_what_can_be_said_of_a_thing_in_any_system() -> None:
    seed = load_builtin()

    assert [g.name for g in seed.groups if g.layer == "core"] == ["physical", "tags", "sourcebook"]
    assert {d.name for d in seed.definitions if d.layer == "core"} == {
        "own_weight", "weight", "contents_weight", "bundle_amount", "is_container", "is_consumable",
        "is_magical", "is_silvered", "is_adamantine", "sourcebook",
    }  # fmt: skip
    assert [n.slug for n in seed.nodes if n.layer == "core"] == ["physical-object"]
    assert {r.node for r in seed.recipes if r.layer == "core"} == {"physical-object"}
    types = {d.name: d.value_type for d in seed.definitions}
    assert types["own_weight"] == "float" and types["bundle_amount"] == "int"


def test_the_equipment_layer_is_the_forms_and_the_materials_with_bare_slugs() -> None:
    seed = load_builtin()

    assert [n.slug for n in seed.nodes if n.layer == "equipment"] == EQUIPMENT
    assert not any(slug.startswith("dnd5e-") for slug in EQUIPMENT)
    # The materials' tags are core's, so the forms that use them are in the layer built on it.
    assert seed.node("silvered").tags == ["is_silvered"]
    assert seed.node("adamantine").tags == ["is_adamantine"]


def test_the_dnd5e_layer_has_the_rules_and_the_eight_stats_that_were_core() -> None:
    seed = load_builtin()

    dnd5e = {d.name for d in seed.definitions if d.layer == "dnd5e"}
    assert {"damage_dice_count", "damage_die", "damage_type", "attack_ability"} <= dnd5e
    assert {"is_finesse", "is_heavy", "uses_ammunition", "is_monk_weapon"} <= dnd5e
    assert dnd5e >= THE_EIGHT
    assert len(dnd5e) == 30
    assert not dnd5e & {"own_weight", "weight", "is_container", "is_consumable", "sourcebook"}
    assert [g.name for g in seed.groups if g.layer == "dnd5e"] == [
        "economic", "destroyable", "damaging",
    ]  # fmt: skip
    types = {d.name: d.value_type for d in seed.definitions}
    assert len(types) == 40
    assert types["price"] == "int" and types["armor"] == "int" and types["armor_formula"] == "text"
    assert types["attack_ability"] == "text" and types["ability_to_damage"] == "bool"
    assert types["damage_versatile_die"] == "int"
    # The properties a category stands for are tags: bool stats, so a node can be found by them.
    assert all(types[name] == "bool" for name in types if name.startswith("is_"))
    nodes = [n.slug for n in seed.nodes if n.layer == "dnd5e"]
    assert len(nodes) == 30 and all(slug.startswith("dnd5e-") for slug in nodes)


def test_belonging_to_the_system_is_having_its_root_as_an_ancestor() -> None:
    seed = load_builtin()

    assert seed.node("dnd5e-system").parents == [] and seed.node("dnd5e-system").name == "D&D 5e"
    axes = (
        "dnd5e-weapon-proficiency", "dnd5e-armor-tier", "dnd5e-tool-proficiency",
        "dnd5e-weapon-property", "dnd5e-spellcasting-focus", "dnd5e-economic-object",
    )  # fmt: skip
    for slug in axes:
        assert seed.node(slug).parents == ["dnd5e-system"], slug
    # Nothing else of the layer is parentless, so every category of it is under the root.
    assert [n.slug for n in seed.nodes if n.layer == "dnd5e" and not n.parents] == ["dnd5e-system"]


def test_the_economic_object_carries_a_price_of_zero_and_nothing_else_does() -> None:
    seed = load_builtin()

    assert seed.node("dnd5e-economic-object").stats == {"price": 0}
    assert [n.slug for n in seed.nodes if n.stats] == ["dnd5e-economic-object"]


def test_the_economic_object_is_attached_to_the_six_forms_that_get_a_price() -> None:
    seed = load_builtin()

    assert [(a.child, a.parent, a.layer) for a in seed.attachments] == [
        (form, "dnd5e-economic-object", "dnd5e-equipment")
        for form in ("weapon", "armor", "tool", "container", "consumable", "gear")
    ]
    # Not on the root of the forms, which is also a mountain.
    assert "physical-object" not in {a.child for a in seed.attachments}


def test_a_shield_is_under_armor_and_the_proficiencies_are_mixins_under_one_root_each() -> None:
    seed = load_builtin()

    assert seed.node("shield").parents == ["armor"]
    assert seed.node("container").tags == ["is_container"]
    assert seed.node("dnd5e-martial").parents == ["dnd5e-weapon-proficiency"]
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
            "only slugs of a layer with a prefix",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "dnd5e"}]},
            "slugs of layer dnd5e start with 'dnd5e-'",
        ),
        (
            {
                "node": [
                    {"slug": "dnd5e-a", "name": "A", "layer": "dnd5e"},
                    {"slug": "b", "name": "B", "layer": "core", "parents": ["dnd5e-a"]},
                ]
            },
            "which is in layer 'dnd5e'",
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


def layered_data(**overrides: Any) -> dict[str, Any]:
    """A small seed with all four layers, to break one thing at a time (ADR 0175)."""
    data: dict[str, Any] = {
        "schema": 1,
        "version": "t",
        "group": [
            {"name": "physical", "layer": "core"},
            {"name": "economic", "layer": "dnd5e"},
        ],
        "definition": [
            {"name": "weight", "group": "physical", "value_type": "float", "layer": "core"},
            {"name": "price", "group": "economic", "value_type": "int", "layer": "dnd5e"},
        ],
        "node": [
            {"slug": "thing", "name": "Thing", "layer": "core"},
            {"slug": "weapon", "name": "Weapon", "layer": "equipment", "parents": ["thing"]},
            {"slug": "dnd5e-system", "name": "D&D 5e", "layer": "dnd5e"},
            {
                "slug": "dnd5e-economic",
                "name": "Economic",
                "layer": "dnd5e",
                "parents": ["dnd5e-system"],
                "stats": {"price": 0},
            },
        ],
        "attachment": [{"child": "weapon", "parent": "dnd5e-economic", "layer": "dnd5e-equipment"}],
        "recipe": [],
    }
    data.update(overrides)
    return data


def test_a_small_four_layer_seed_loads() -> None:
    seed = SeedSpec.model_validate(layered_data())

    assert [a.layer for a in seed.attachments] == ["dnd5e-equipment"]
    assert seed.node("dnd5e-economic").stats == {"price": 0}


def test_a_seed_without_attachments_loads() -> None:
    assert SeedSpec.model_validate(spec_data()).attachments == []


def test_a_layer_may_name_the_layers_it_is_built_on_however_far_down() -> None:
    assert available("core") == {"core"}
    assert available("equipment") == {"core", "equipment"}
    assert available("dnd5e") == {"core", "dnd5e"}
    assert available("dnd5e-equipment") == {"core", "equipment", "dnd5e", "dnd5e-equipment"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # A sibling layer is never named: equipment and dnd5e are both built on core only.
        (
            {
                "node": [
                    {"slug": "dnd5e-a", "name": "A", "layer": "dnd5e"},
                    {"slug": "b", "name": "B", "layer": "equipment", "parents": ["dnd5e-a"]},
                ]
            },
            "which is in layer 'dnd5e'",
        ),
        (
            {
                "node": [
                    {"slug": "a", "name": "A", "layer": "equipment"},
                    {"slug": "dnd5e-b", "name": "B", "layer": "dnd5e", "parents": ["a"]},
                ]
            },
            "which is in layer 'equipment'",
        ),
        # Nodes are listed in layer dependency order.
        (
            {
                "node": [
                    {"slug": "dnd5e-a", "name": "A", "layer": "dnd5e"},
                    {"slug": "b", "name": "B", "layer": "equipment"},
                ]
            },
            "listed after a later layer's",
        ),
        (
            {
                "definition": [
                    {"name": "x", "group": "economic", "value_type": "int", "layer": "core"}
                ]
            },
            "which is in layer 'dnd5e'",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "equipment", "stats": {"price": 0}}]},
            "which is in layer 'dnd5e'",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "core", "stats": {"nope": 0}}]},
            "no definition 'nope'",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "core", "stats": {"weight": "heavy"}}]},
            "'weight' is a float stat",
        ),
        (
            {"node": [{"slug": "a", "name": "A", "layer": "core", "stats": {"weight": True}}]},
            "'weight' is a float stat",
        ),
        (
            {"node": [{"slug": "dnd5e-a", "name": "A", "layer": "dnd5e", "stats": {"price": 1.5}}]},
            "'price' is a int stat",
        ),
        (
            {"attachment": [{"child": "gone", "parent": "thing", "layer": "dnd5e-equipment"}]},
            "no node 'gone'",
        ),
        (
            {"attachment": [{"child": "thing", "parent": "gone", "layer": "dnd5e-equipment"}]},
            "no node 'gone'",
        ),
        # The layer that makes an attachment is built on the layers of both its categories.
        (
            {"attachment": [{"child": "weapon", "parent": "dnd5e-economic", "layer": "dnd5e"}]},
            "which is in layer 'equipment'",
        ),
        (
            {"attachment": [{"child": "weapon", "parent": "dnd5e-economic", "layer": "equipment"}]},
            "which is in layer 'dnd5e'",
        ),
        (
            {"attachment": [{"child": "weapon", "parent": "weapon", "layer": "dnd5e-equipment"}]},
            "can't be its own parent",
        ),
        (
            {"attachment": [{"child": "weapon", "parent": "thing", "layer": "dnd5e-equipment"}]},
            "has it as a parent already",
        ),
        (
            {
                "attachment": [
                    {"child": "weapon", "parent": "dnd5e-economic", "layer": "dnd5e-equipment"}
                ]
                * 2
            },
            "listed twice",
        ),
        (
            {"attachment": [{"child": "weapon", "parent": "thing", "layer": "no-such-layer"}]},
            "Input should be",
        ),
    ],
)
def test_a_broken_four_layer_seed_is_refused_with_a_reason(
    change: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        SeedSpec.model_validate(layered_data(**change))
