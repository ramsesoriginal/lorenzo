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
        "npcs_shared_with_gms": True,
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
            descriptions=[object()] if spec_node.description else [],
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
    assert order[("node", "consumable")] < order[("node", "ammunition")]
    # A description is written once its node exists.
    assert order[("node", "dnd5e-finesse")] < order[("description", "dnd5e-finesse")]
    assert kinds.count("group") == 6
    assert kinds.count("definition") == len(SPEC.definitions) == 40
    assert kinds.count("node") == len(SPEC.nodes) == 61
    assert kinds.count("tag") == sum(len(n.tags) for n in SPEC.nodes) == 14
    assert kinds.count("description") == sum(1 for n in SPEC.nodes if n.description) == 18
    assert kinds.count("recipe") == 2
    names = [a.name for a in plan.actions if a.kind == "node"]
    assert names.index("physical-object") < names.index("weapon") < names.index("melee-weapon")


def test_a_seeded_tenant_needs_nothing() -> None:
    plan = make_plan(SPEC, fully_seeded(), TENANT, ALL)

    assert plan.actions == []
    assert plan.problems == [] and plan.warnings == []
    assert (
        plan.existing == 6 + len(SPEC.definitions) + len(SPEC.nodes) + 2
    )  # tags and descriptions are not counted twice


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
    for definition_ in [d for d in SPEC.definitions if d.layer == "dnd5e"]:
        del state.definitions[definition_.name]

    plan = make_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == {"dnd5e"}
    layer_nodes = [n for n in SPEC.nodes if n.layer == "dnd5e"]
    expected = (
        len([d for d in SPEC.definitions if d.layer == "dnd5e"])
        + len(layer_nodes)
        + sum(len(n.tags) for n in layer_nodes)
        + sum(1 for n in layer_nodes if n.description)
    )
    assert len(plan.actions) == expected == 22 + 28 + 10 + 12


def test_a_slug_held_by_something_else_is_a_problem() -> None:
    state = fully_seeded()
    state.nodes["gear"] = node("gear", kinds=("character",))
    del state.items["gear"]

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert any("'gear' belongs to something that isn't an item" in p for p in plan.problems)


def test_a_node_under_the_wrong_parent_is_left_alone_with_a_warning() -> None:
    state = fully_seeded()
    state.items["shield"] = ItemOut.model_construct(
        entity_id=state.nodes["shield"].entity_id, prototype_ids=[], tags=[], descriptions=[]
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
        descriptions=state.items["container"].descriptions,
    )

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name) for a in plan.actions] == [("tag", "container: is_container")]


def test_the_plan_names_the_layers_and_the_seed_version() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ("core",))

    assert plan.layers == ("core",)
    assert plan.spec_version == SPEC.version
    assert {a.layer for a in plan.actions} == {"core"}


def test_a_node_without_its_description_gets_one_written() -> None:
    state = fully_seeded()
    state.items["dnd5e-heavy"] = ItemOut.model_construct(
        entity_id=state.nodes["dnd5e-heavy"].entity_id,
        prototype_ids=state.items["dnd5e-heavy"].prototype_ids,
        tags=state.items["dnd5e-heavy"].tags,
        descriptions=[],
    )

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name) for a in plan.actions] == [("description", "dnd5e-heavy")]


def test_a_description_with_the_placeholder_title_is_retitled_with_its_nodes_name() -> None:
    state = fully_seeded()
    information_id = uuid.uuid4()
    state.retitles["dnd5e-heavy"] = (information_id, "Heavy (D&D 5e)")

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name, a.detail) for a in plan.actions] == [
        ("retitle", "dnd5e-heavy", "Heavy (D&D 5e)")
    ]


def test_only_the_layers_asked_for_are_retitled() -> None:
    state = fully_seeded()
    state.retitles["dnd5e-heavy"] = (uuid.uuid4(), "Heavy (D&D 5e)")
    state.retitles["crossbow"] = (uuid.uuid4(), "Crossbow")

    plan = make_plan(SPEC, state, TENANT, ("core",))

    assert [(a.kind, a.name) for a in plan.actions] == [("retitle", "crossbow")]


# --- a bare seed and the layers a tenant holds (ADR 0166) -------------------------------------


def layers_held(state: TenantState, *layers: str) -> TenantState:
    """Only what the given layers hold of a fully seeded tenant."""
    nodes = {n.slug for n in SPEC.nodes if n.layer in layers}
    definitions = {d.name for d in SPEC.definitions if d.layer in layers}
    return TenantState(
        {name: g for name, g in state.groups.items() if name in {g.name for g in SPEC.groups}},
        {name: d for name, d in state.definitions.items() if name in definitions},
        {slug: n for slug, n in state.nodes.items() if slug in nodes},
        {slug: i for slug, i in state.items.items() if slug in nodes},
        {key: r for key, r in state.recipes.items() if key[0] in nodes},
    )


def test_a_bare_seed_of_a_tenant_that_holds_one_layer_is_a_problem_naming_both() -> None:
    state = layers_held(fully_seeded(), "core")

    plan = make_plan(SPEC, state, TENANT, ALL, explicit=False)

    assert plan.actions == []
    [problem] = plan.problems
    assert "holds the core layer and none of dnd5e" in problem
    assert "`--layer core`" in problem and "`--layer dnd5e`" in problem


def test_a_bare_seed_of_the_other_layer_alone_is_refused_the_same_way() -> None:
    state = layers_held(fully_seeded(), "dnd5e")

    [problem] = make_plan(SPEC, state, TENANT, ALL, explicit=False).problems

    assert "holds the dnd5e layer and none of core" in problem


def test_a_bare_seed_of_an_empty_tenant_seeds_every_layer() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ALL, explicit=False)

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == set(ALL)


def test_a_bare_seed_of_a_tenant_that_holds_both_layers_completes_them() -> None:
    state = fully_seeded()
    del state.nodes["dnd5e-heavy"], state.items["dnd5e-heavy"]

    plan = make_plan(SPEC, state, TENANT, ALL, explicit=False)

    assert plan.problems == []
    assert [(a.kind, a.name) for a in plan.actions][:1] == [("node", "dnd5e-heavy")]


def test_naming_the_layer_is_never_refused() -> None:
    state = layers_held(fully_seeded(), "core")

    plan = make_plan(SPEC, state, TENANT, ("dnd5e",), explicit=True)

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == {"dnd5e"}
