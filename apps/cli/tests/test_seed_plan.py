"""What `seed` decides from what a tenant already has (ADR 0143), without a network."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from lorenzo_cli.client.models import (
    ComputedStatOut,
    ItemOut,
    ResolvedSlugOut,
    StatDefinitionOut,
    StatGroupOut,
    TenantOut,
)
from lorenzo_cli.seed import load_builtin, make_plan
from lorenzo_cli.seed.plan import TenantState

SPEC = load_builtin()
NOW = datetime(2026, 9, 29, tzinfo=UTC)
TENANT = TenantOut.model_validate(
    {
        "id": uuid.uuid4(),
        "slug": "repo",
        "name": "Repo",
        "description": "",
        "kind": "repository",
        "published_at": None,
        "created_by": None,
        "updated_by": None,
    }
)
ALL = ("core", "dnd5e")


def group(name: str) -> StatGroupOut:
    return StatGroupOut(
        id=uuid.uuid4(), name=name, priority=0, mandatory=False, created_at=NOW, updated_at=NOW
    )


def definition(name: str, group_out: StatGroupOut, value_type: str) -> StatDefinitionOut:
    return StatDefinitionOut.model_validate(
        {
            "id": uuid.uuid4(),
            "name": name,
            "stat_group_id": group_out.id,
            "value_type": value_type,
            "enum_values": [],
            "created_at": NOW,
            "updated_at": NOW,
        }
    )


def node(slug: str, kinds: tuple[str, ...] = ("item",)) -> ResolvedSlugOut:
    return ResolvedSlugOut.model_validate(
        {"slug": slug, "entity_id": uuid.uuid4(), "name": slug, "kinds": list(kinds)}
    )


def item(
    resolved: ResolvedSlugOut, parents: list[uuid.UUID], tags: list[Any] | None = None
) -> ItemOut:
    return ItemOut.model_construct(
        entity_id=resolved.entity_id, prototype_ids=parents, tags=tags or []
    )


def fully_seeded() -> TenantState:
    groups = {g.name: group(g.name) for g in SPEC.groups}
    definitions = {
        d.name: definition(d.name, groups[d.group], d.value_type) for d in SPEC.definitions
    }
    nodes = {n.slug: node(n.slug) for n in SPEC.nodes}
    items = {}
    for spec_node in SPEC.nodes:
        tags = [{"name": t, "value": True} for t in spec_node.tags]
        items[spec_node.slug] = ItemOut.model_construct(
            entity_id=nodes[spec_node.slug].entity_id,
            prototype_ids=[nodes[p].entity_id for p in spec_node.parents],
            tags=[type("Tag", (), t)() for t in tags],
        )
    recipes = {}
    for recipe in SPEC.recipes:
        recipes[(recipe.node, recipe.stat)] = ComputedStatOut.model_construct(
            entity_id=nodes[recipe.node].entity_id,
            stat_definition_id=definitions[recipe.stat].id,
            formula=type("F", (), {"kind": recipe.kind})(),
        )
    return TenantState(groups, definitions, nodes, items, recipes)


def test_an_empty_tenant_gets_everything_in_dependency_order() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ALL)

    kinds = [a.kind for a in plan.actions]
    assert plan.problems == [] and plan.warnings == [] and plan.existing == 0
    # Everything an action needs is planned before it: groups, then definitions, then nodes
    # (parents first, a tag right after its node), and the recipes last.
    order = {(a.kind, a.name): i for i, a in enumerate(plan.actions)}
    last = {kind: max(i for (k, _), i in order.items() if k == kind) for kind in set(kinds)}
    first = {kind: min(i for (k, _), i in order.items() if k == kind) for kind in set(kinds)}
    assert last["group"] < first["definition"] < first["node"]
    assert last["node"] < first["recipe"]
    assert order[("node", "container")] < order[("tag", "container: is_container")]
    assert order[("definition", "is_container")] < order[("tag", "container: is_container")]
    assert kinds.count("group") == 6
    assert kinds.count("definition") == 12
    assert kinds.count("node") == 22
    assert kinds.count("tag") == 1
    assert kinds.count("recipe") == 2
    names = [a.name for a in plan.actions if a.kind == "node"]
    assert names.index("physical-object") < names.index("weapon") < names.index("melee-weapon")


def test_a_seeded_tenant_needs_nothing() -> None:
    plan = make_plan(SPEC, fully_seeded(), TENANT, ALL)

    assert plan.actions == []
    assert plan.problems == [] and plan.warnings == []
    assert plan.existing == 6 + 12 + 22 + 2  # tags on an existing node are not counted twice


def test_only_what_is_missing_is_planned() -> None:
    state = fully_seeded()
    del state.nodes["shield"], state.items["shield"]
    del state.definitions["price"]

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name) for a in plan.actions] == [("definition", "price"), ("node", "shield")]


def test_a_definition_of_the_wrong_type_is_a_problem_naming_it() -> None:
    state = fully_seeded()
    physical = state.groups["physical"]
    state.definitions["weight"] = definition("weight", physical, "int")

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert len(plan.problems) == 1
    assert "'weight' is a int stat" in plan.problems[0]
    assert "needs a float" in plan.problems[0]


def test_a_definition_in_another_group_is_a_problem() -> None:
    state = fully_seeded()
    state.definitions["price"] = definition("price", state.groups["physical"], "int")

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert any("'price' is in another group" in p for p in plan.problems)


def test_the_dnd5e_layer_alone_needs_core_first() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ("dnd5e",))

    assert {a.layer for a in plan.actions} == {"dnd5e"}  # what it can create, it plans
    assert any("the group 'damaging'" in p and "Seed that layer first" in p for p in plan.problems)


def test_the_dnd5e_layer_alone_works_once_core_is_there() -> None:
    state = fully_seeded()
    for slug in [n.slug for n in SPEC.nodes if n.layer == "dnd5e"]:
        del state.nodes[slug], state.items[slug]
    for name in ("damage_dice_count", "damage_die", "damage_type"):
        del state.definitions[name]

    plan = make_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == {"dnd5e"}
    assert len(plan.actions) == 3 + 12


def test_a_slug_held_by_something_else_is_a_problem() -> None:
    state = fully_seeded()
    state.nodes["gear"] = node("gear", kinds=("character",))
    del state.items["gear"]

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert any("'gear' belongs to something that isn't an item" in p for p in plan.problems)


def test_a_node_under_the_wrong_parent_is_left_alone_with_a_warning() -> None:
    state = fully_seeded()
    state.items["shield"] = ItemOut.model_construct(
        entity_id=state.nodes["shield"].entity_id, prototype_ids=[], tags=[]
    )

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert plan.actions == []
    assert any("'shield' exists but is not under armor" in w for w in plan.warnings)


def test_a_different_formula_already_there_is_left_alone_with_a_warning() -> None:
    state = fully_seeded()
    key = ("physical-object", "contents_weight")
    state.recipes[key] = ComputedStatOut.model_construct(
        entity_id=state.nodes["physical-object"].entity_id,
        stat_definition_id=state.definitions["contents_weight"].id,
        formula=type("F", (), {"kind": "linear"})(),
    )

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert plan.actions == []
    assert any("already has a linear formula, not the seed's contents" in w for w in plan.warnings)


def test_the_container_tag_is_planned_when_the_node_lacks_it() -> None:
    state = fully_seeded()
    state.items["container"] = ItemOut.model_construct(
        entity_id=state.nodes["container"].entity_id,
        prototype_ids=state.items["container"].prototype_ids,
        tags=[],
    )

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name) for a in plan.actions] == [("tag", "container: is_container")]


def test_the_plan_names_the_layers_and_the_seed_version() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ("core",))

    assert plan.layers == ("core",)
    assert plan.spec_version == SPEC.version
    assert {a.layer for a in plan.actions} == {"core"}
