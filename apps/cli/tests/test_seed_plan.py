"""What `seed` decides from what a tenant already has (ADR 0143, 0181), without a network."""

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
from lorenzo_cli.seed import LAYERS, load_builtin, make_plan
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
ALL = LAYERS


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


def fully_seeded(*, attached: bool = True) -> TenantState:
    """A tenant with the whole seed. Without `attached`, the equipment's forms don't have the
    parents the dnd5e-equipment layer adds."""
    groups = {g.name: group(g.name) for g in SPEC.groups}
    definitions = {
        d.name: definition(d.name, groups[d.group], d.value_type) for d in SPEC.definitions
    }
    nodes = {n.slug: node(n.slug) for n in SPEC.nodes}
    items = {}
    for spec_node in SPEC.nodes:
        tags = [{"name": t, "value": True} for t in spec_node.tags]
        added = [a.parent for a in SPEC.attachments if a.child == spec_node.slug and attached]
        items[spec_node.slug] = ItemOut.model_construct(
            entity_id=nodes[spec_node.slug].entity_id,
            descriptions=[object()] if spec_node.description else [],
            prototype_ids=[nodes[p].entity_id for p in [*spec_node.parents, *added]],
            tags=[type("Tag", (), t)() for t in tags],
        )
    recipes = {}
    for recipe in SPEC.recipes:
        recipes[(recipe.node, recipe.stat)] = ComputedStatOut.model_construct(
            entity_id=nodes[recipe.node].entity_id,
            stat_definition_id=definitions[recipe.stat].id,
            formula=type("F", (), {"kind": recipe.kind})(),
        )
    own_stats = {(n.slug, stat): value for n in SPEC.nodes for stat, value in n.stats.items()}
    return TenantState(groups, definitions, nodes, items, recipes, own_stats=own_stats)


def test_an_empty_tenant_gets_everything_in_dependency_order() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ALL)

    kinds = [a.kind for a in plan.actions]
    assert plan.problems == [] and plan.warnings == [] and plan.existing == 0
    # Everything an action needs is planned before it: groups, then definitions, then nodes
    # (parents first, a tag right after its node), the attachments, and the recipes last.
    order = {(a.kind, a.name): i for i, a in enumerate(plan.actions)}
    last = {kind: max(i for (k, _), i in order.items() if k == kind) for kind in set(kinds)}
    first = {kind: min(i for (k, _), i in order.items() if k == kind) for kind in set(kinds)}
    assert last["group"] < first["definition"] < first["node"]
    assert last["node"] < first["attach"] <= last["attach"] < first["recipe"]
    assert order[("node", "container")] < order[("tag", "container: is_container")]
    assert order[("definition", "is_container")] < order[("tag", "container: is_container")]
    assert order[("node", "consumable")] < order[("node", "ammunition")]
    # A value is set once its node and its definition exist.
    assert (
        order[("node", "dnd5e-economic-object")] < order[("stat", "dnd5e-economic-object: price")]
    )
    assert order[("definition", "price")] < order[("stat", "dnd5e-economic-object: price")]
    # An attachment is made once both categories exist, in the layer that makes it.
    assert (
        order[("node", "dnd5e-economic-object")]
        < order[("attach", "weapon: dnd5e-economic-object")]
    )
    assert order[("node", "weapon")] < order[("attach", "weapon: dnd5e-economic-object")]
    # A description is written once its node exists.
    assert order[("node", "dnd5e-finesse")] < order[("description", "dnd5e-finesse")]
    assert kinds.count("group") == 6
    assert kinds.count("definition") == len(SPEC.definitions) == 40
    assert kinds.count("node") == len(SPEC.nodes) == 64
    assert kinds.count("tag") == sum(len(n.tags) for n in SPEC.nodes) == 14
    assert kinds.count("description") == sum(1 for n in SPEC.nodes if n.description) == 21
    assert kinds.count("stat") == sum(len(n.stats) for n in SPEC.nodes) == 1
    assert kinds.count("attach") == len(SPEC.attachments) == 6
    assert kinds.count("recipe") == 2
    assert [(a.kind, a.layer) for a in plan.actions if a.kind == "attach"] == [
        ("attach", "dnd5e-equipment")
    ] * 6
    names = [a.name for a in plan.actions if a.kind == "node"]
    assert names.index("physical-object") < names.index("weapon") < names.index("melee-weapon")


def test_a_seeded_tenant_needs_nothing() -> None:
    plan = make_plan(SPEC, fully_seeded(), TENANT, ALL)

    assert plan.actions == []
    assert plan.problems == [] and plan.warnings == []
    assert (
        plan.existing == 6 + len(SPEC.definitions) + len(SPEC.nodes) + 6 + 2
    )  # tags, values and descriptions are not counted twice


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
    assert any("the group 'tags'" in p and "Seed that layer first" in p for p in plan.problems)


def test_the_dnd5e_layer_alone_works_once_core_is_there() -> None:
    state = layers_held(fully_seeded(), "core")

    plan = make_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == {"dnd5e"}
    layer_nodes = [n for n in SPEC.nodes if n.layer == "dnd5e"]
    expected = (
        len([g for g in SPEC.groups if g.layer == "dnd5e"])
        + len([d for d in SPEC.definitions if d.layer == "dnd5e"])
        + len(layer_nodes)
        + sum(len(n.tags) for n in layer_nodes)
        + sum(len(n.stats) for n in layer_nodes)
        + sum(1 for n in layer_nodes if n.description)
    )
    # Groups, definitions, categories, tags, values, descriptions.
    assert len(plan.actions) == expected == 3 + 30 + 30 + 10 + 1 + 14


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

    plan = make_plan(SPEC, state, TENANT, ("equipment",))

    assert [(a.kind, a.name) for a in plan.actions] == [("retitle", "crossbow")]
    assert make_plan(SPEC, state, TENANT, ("core",)).actions == []


# --- a bare seed and the layers a tenant holds (ADR 0166) -------------------------------------


def layers_held(state: TenantState, *layers: str) -> TenantState:
    """Only what the given layers hold of a fully seeded tenant. The equipment's forms have the
    parents the dnd5e-equipment layer adds only when that layer is one of them."""
    nodes = {n.slug for n in SPEC.nodes if n.layer in layers}
    definitions = {d.name for d in SPEC.definitions if d.layer in layers}
    groups = {g.name for g in SPEC.groups if g.layer in layers}
    items = {}
    for slug, held in state.items.items():
        if slug in nodes:
            drop = {state.nodes[a.parent].entity_id for a in SPEC.attachments if a.child == slug}
            keep = [p for p in held.prototype_ids if p not in drop or "dnd5e-equipment" in layers]
            items[slug] = ItemOut.model_construct(
                entity_id=held.entity_id,
                prototype_ids=keep,
                tags=held.tags,
                descriptions=held.descriptions,
            )
    return TenantState(
        {name: g for name, g in state.groups.items() if name in groups},
        {name: d for name, d in state.definitions.items() if name in definitions},
        {slug: n for slug, n in state.nodes.items() if slug in nodes},
        items,
        {key: r for key, r in state.recipes.items() if key[0] in nodes},
        own_stats={key: v for key, v in state.own_stats.items() if key[0] in nodes},
    )


def test_a_bare_seed_of_a_tenant_that_holds_one_layer_is_a_problem_naming_both() -> None:
    state = layers_held(fully_seeded(), "core")

    plan = make_plan(SPEC, state, TENANT, ALL, explicit=False)

    assert plan.actions == []
    [problem] = plan.problems
    assert "holds the core layer and none of equipment and dnd5e and dnd5e-equipment" in problem
    assert "`--layer core`" in problem and "`--layer dnd5e`" in problem


def test_a_bare_seed_of_the_other_layer_alone_is_refused_the_same_way() -> None:
    state = layers_held(fully_seeded(), "dnd5e")

    [problem] = make_plan(SPEC, state, TENANT, ALL, explicit=False).problems

    assert "holds the dnd5e layer and none of core and equipment and dnd5e-equipment" in problem


def test_a_bare_seed_of_a_tenant_without_the_attachments_is_refused_too() -> None:
    state = layers_held(fully_seeded(), "core", "equipment", "dnd5e")

    [problem] = make_plan(SPEC, state, TENANT, ALL, explicit=False).problems

    assert "holds the core and equipment and dnd5e layer and none of dnd5e-equipment" in problem


def test_a_bare_seed_of_an_empty_tenant_seeds_every_layer() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ALL, explicit=False)

    assert plan.problems == []
    assert {a.layer for a in plan.actions} == set(ALL)


def test_a_bare_seed_of_a_tenant_that_holds_every_layer_completes_them() -> None:
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


# --- values and attachments (ADR 0181) ---------------------------------------------------------


def test_a_value_the_node_lacks_is_planned_and_the_one_it_has_is_left_alone() -> None:
    state = fully_seeded()
    del state.own_stats[("dnd5e-economic-object", "price")]

    plan = make_plan(SPEC, state, TENANT, ALL)

    assert [(a.kind, a.name, a.detail) for a in plan.actions] == [
        ("stat", "dnd5e-economic-object: price", "0")
    ]

    state.own_stats[("dnd5e-economic-object", "price")] = 5
    plan = make_plan(SPEC, state, TENANT, ALL)

    assert plan.actions == []
    assert any("has price 5, not the seed's 0" in w for w in plan.warnings)


def test_a_value_waits_for_its_definition() -> None:
    plan = make_plan(SPEC, layers_held(fully_seeded(), "core"), TENANT, ("dnd5e",))

    order = [(a.kind, a.name) for a in plan.actions]
    assert order.index(("definition", "price")) < order.index(
        ("stat", "dnd5e-economic-object: price")
    )


def test_the_attachments_alone_need_the_categories_they_join() -> None:
    plan = make_plan(SPEC, TenantState(), TENANT, ("dnd5e-equipment",))

    assert plan.actions == []
    [problem] = plan.problems
    assert "The attachments of the dnd5e-equipment layer need categories" in problem
    assert "weapon, armor, tool ... (layer equipment)" in problem
    assert "dnd5e-economic-object (layer dnd5e)" in problem
    assert "Seed equipment and dnd5e first." in problem


def test_the_attachments_are_planned_once_both_layers_are_there() -> None:
    state = layers_held(fully_seeded(), "core", "equipment", "dnd5e")

    plan = make_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert plan.problems == [] and plan.warnings == []
    assert [(a.kind, a.name, a.layer) for a in plan.actions] == [
        ("attach", f"{form}: dnd5e-economic-object", "dnd5e-equipment")
        for form in ("weapon", "armor", "tool", "container", "consumable", "gear")
    ]


def test_an_attachment_already_there_is_counted_and_not_planned() -> None:
    state = fully_seeded()

    plan = make_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert plan.actions == [] and plan.existing == 6


def test_an_ordinary_edge_counts_as_much_as_an_attachment() -> None:
    # Seeded into one tenant with every layer, the same edges are ordinary ones (ADR 0181).
    state = layers_held(fully_seeded(), "core", "equipment", "dnd5e")
    weapon = state.items["weapon"]
    state.items["weapon"] = ItemOut.model_construct(
        entity_id=weapon.entity_id,
        prototype_ids=[*weapon.prototype_ids, state.nodes["dnd5e-economic-object"].entity_id],
        tags=weapon.tags,
        descriptions=weapon.descriptions,
    )

    plan = make_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert plan.existing == 1
    assert [a.name for a in plan.actions][:1] == ["armor: dnd5e-economic-object"]
    assert len(plan.actions) == 5


def test_a_form_with_the_parents_the_attachments_add_is_not_under_the_wrong_parent() -> None:
    plan = make_plan(SPEC, fully_seeded(), TENANT, ("equipment",))

    assert plan.actions == [] and plan.warnings == []


def test_a_form_with_a_parent_the_seed_does_not_have_still_gets_the_warning() -> None:
    state = fully_seeded()
    weapon = state.items["weapon"]
    state.items["weapon"] = ItemOut.model_construct(
        entity_id=weapon.entity_id,
        prototype_ids=[*weapon.prototype_ids, uuid.uuid4()],
        tags=weapon.tags,
        descriptions=weapon.descriptions,
    )

    plan = make_plan(SPEC, state, TENANT, ("equipment",))

    assert any("'weapon' exists but is not under physical-object" in w for w in plan.warnings)


def test_a_parentless_axis_root_from_an_older_seed_is_left_with_a_warning() -> None:
    # A tenant seeded by version 1 has the axis roots under nothing (ADR 0181).
    state = fully_seeded()
    root = state.items["dnd5e-armor-tier"]
    state.items["dnd5e-armor-tier"] = ItemOut.model_construct(
        entity_id=root.entity_id, prototype_ids=[], tags=[], descriptions=root.descriptions
    )

    plan = make_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.actions == []
    assert any(
        "'dnd5e-armor-tier' exists but is not under dnd5e-system" in w for w in plan.warnings
    )


def test_an_attachment_to_something_that_is_not_an_item_is_a_problem() -> None:
    state = fully_seeded()
    state.nodes["weapon"] = node("weapon", kinds=("character",))
    del state.items["weapon"]

    plan = make_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert any("'weapon' belongs to something that isn't an item" in p for p in plan.problems)
