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
        "physical-object", "weapon", "melee-weapon", "ranged-weapon", "armor", "shield", "tool",
        "container", "ammunition", "gear",
    ]  # fmt: skip
    assert len(dnd5e) == 12
    assert all(slug.startswith("dnd5e-") for slug in dnd5e)
    assert {g.name for g in seed.groups} == {
        "physical", "economic", "destroyable", "damaging", "tags", "sourcebook",
    }  # fmt: skip
    assert {d.name: d.value_type for d in seed.definitions} == {
        "own_weight": "float", "weight": "float", "contents_weight": "float",
        "range_normal": "int", "range_long": "int", "price": "int", "armor": "int",
        "is_container": "bool", "sourcebook": "text",
        "damage_dice_count": "int", "damage_die": "int", "damage_type": "text",
    }  # fmt: skip


def test_only_the_damage_dice_belong_to_the_dnd5e_layer_among_the_definitions() -> None:
    seed = load_builtin()

    assert {d.name for d in seed.definitions if d.layer == "dnd5e"} == {
        "damage_dice_count",
        "damage_die",
        "damage_type",
    }
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
        "container": ["physical-object"], "ammunition": ["physical-object"],
        "gear": ["physical-object"],
    }  # fmt: skip
    assert {slug: seed.node(slug).parents for slug in forms} == forms


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
