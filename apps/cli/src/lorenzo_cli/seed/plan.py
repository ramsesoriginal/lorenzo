"""Reading what a tenant already has and working out what `seed` would create (ADR 0143).

Everything here is find-or-create by name or slug: nothing is ever changed or removed, so a seed
is safe to run again and to run over a tenant that already has some of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli import descriptions
from lorenzo_cli.client.models import (
    ComputedStatOut,
    ItemOut,
    ResolvedSlugOut,
    StatDefinitionOut,
    StatGroupOut,
    TenantOut,
)
from lorenzo_cli.client.ops import (
    GET_ENTITY,
    GET_ITEM,
    LIST_ENTITY_COMPUTED_STATS,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
    RESOLVE_SLUGS,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.spec import SeedSpec

ActionKind = Literal["group", "definition", "node", "description", "retitle", "tag", "recipe"]
_RESOLVE_BATCH = 100  # GET .../entities/resolve takes at most this many slugs (ADR 0107)


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    # A group or definition name, a node slug, or "<slug>: <tag or stat>".
    name: str
    layer: str
    detail: str = ""


@dataclass(frozen=True)
class TenantState:
    """What the tenant already holds of the seed."""

    groups: dict[str, StatGroupOut] = field(default_factory=dict)
    definitions: dict[str, StatDefinitionOut] = field(default_factory=dict)
    nodes: dict[str, ResolvedSlugOut] = field(default_factory=dict)
    items: dict[str, ItemOut] = field(default_factory=dict)
    # (node slug, stat name) -> its computed stat.
    recipes: dict[tuple[str, str], ComputedStatOut] = field(default_factory=dict)
    # node slug -> (its description, the node's name) where the description still has the
    # placeholder title the seed used to give every one (ADR 0165).
    retitles: dict[str, tuple[UUID, str]] = field(default_factory=dict)


@dataclass
class SeedPlan:
    tenant: TenantOut
    layers: tuple[str, ...]
    spec_version: str
    actions: list[Action] = field(default_factory=list)
    existing: int = 0
    # Something that would leave the tenant wrong or half-seeded: nothing is written.
    problems: list[str] = field(default_factory=list)
    # Something worth knowing that the seed leaves alone.
    warnings: list[str] = field(default_factory=list)


def read_state(client: LorenzoClient, tenant_id: UUID, spec: SeedSpec) -> TenantState:
    path = {"tenant_id": tenant_id}
    groups = {g.name: g for g in all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)}
    definitions = {
        d.name: d for d in all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }

    slugs = [node.slug for node in spec.nodes]
    nodes: dict[str, ResolvedSlugOut] = {}
    for start in range(0, len(slugs), _RESOLVE_BATCH):
        batch = slugs[start : start + _RESOLVE_BATCH]
        for found in client.call(RESOLVE_SLUGS, path=path, query={"slug": batch}).value:
            nodes[found.slug] = found

    items: dict[str, ItemOut] = {}
    retitles: dict[str, tuple[UUID, str]] = {}
    for slug, found in nodes.items():
        if "item" in {kind.value for kind in found.kinds}:
            items[slug] = client.call(GET_ITEM, path={**path, "entity_id": found.entity_id}).value
            if items[slug].title == descriptions.PLACEHOLDER_TITLE:
                # Its title is the description's, so the row may be the placeholder: look.
                detail = client.call(GET_ENTITY, path={**path, "entity_id": found.entity_id}).value
                stale = descriptions.placeholder_description(detail)
                if stale is not None:
                    retitles[slug] = (stale.id, detail.name)

    definition_names = {d.id: d.name for d in definitions.values()}
    recipes: dict[tuple[str, str], ComputedStatOut] = {}
    for node_slug in {recipe.node for recipe in spec.recipes} & items.keys():
        computed = client.call(
            LIST_ENTITY_COMPUTED_STATS, path={**path, "entity_id": nodes[node_slug].entity_id}
        ).value
        for stat in computed:
            name = definition_names.get(stat.stat_definition_id)
            if name is not None:
                recipes[(node_slug, name)] = stat
    return TenantState(groups, definitions, nodes, items, recipes, retitles)


def make_plan(
    spec: SeedSpec, state: TenantState, tenant: TenantOut, layers: tuple[str, ...]
) -> SeedPlan:
    plan = SeedPlan(tenant=tenant, layers=layers, spec_version=spec.version)
    have_groups = set(state.groups)
    have_definitions = set(state.definitions)
    have_nodes = set(state.nodes)

    def missing(what: str, needed: str, layer: str, by: str) -> None:
        plan.problems.append(
            f"{by} needs {what} {needed!r} (layer {layer}), which this tenant doesn't have. "
            f"Seed that layer first."
        )

    for group in (g for g in spec.groups if g.layer in layers):
        if group.name in state.groups:
            plan.existing += 1
        else:
            plan.actions.append(Action("group", group.name, group.layer))
            have_groups.add(group.name)

    groups_by_name = {g.name: g for g in spec.groups}
    for definition in (d for d in spec.definitions if d.layer in layers):
        present = state.definitions.get(definition.name)
        if present is not None:
            if present.value_type.value != definition.value_type:
                plan.problems.append(
                    f"The definition {definition.name!r} is a {present.value_type.value} stat "
                    f"in this tenant, and the seed needs a {definition.value_type}. A stat's "
                    f"type can't be changed, so rename or remove that stat by hand first."
                )
                continue
            tenant_group = state.groups.get(definition.group)
            if tenant_group is not None and present.stat_group_id != tenant_group.id:
                plan.problems.append(
                    f"The definition {definition.name!r} is in another group than "
                    f"{definition.group!r} in this tenant. A stat can't be moved between groups."
                )
                continue
            plan.existing += 1
            continue
        if definition.group not in have_groups:
            missing(
                "the group",
                definition.group,
                groups_by_name[definition.group].layer,
                f"The definition {definition.name!r}",
            )
            continue
        plan.actions.append(
            Action("definition", definition.name, definition.layer, definition.value_type)
        )
        have_definitions.add(definition.name)

    for node in (n for n in spec.nodes if n.layer in layers):
        parents_ok = True
        for parent in node.parents:
            if parent not in have_nodes:
                missing("the parent", parent, spec.node(parent).layer, f"The node {node.slug!r}")
                parents_ok = False
        exists = node.slug in state.nodes
        if exists:
            item = state.items.get(node.slug)
            if item is None:
                plan.problems.append(
                    f"The slug {node.slug!r} belongs to something that isn't an item in this "
                    f"tenant, and the seed needs it for {node.name!r}."
                )
                continue
            expected = {state.nodes[p].entity_id for p in node.parents if p in state.nodes}
            if expected != set(item.prototype_ids) and len(expected) == len(node.parents):
                plan.warnings.append(
                    f"{node.slug!r} exists but is not under {', '.join(node.parents) or 'nothing'} "
                    f"as the seed has it. It is left as it is."
                )
            plan.existing += 1
        elif parents_ok:
            plan.actions.append(Action("node", node.slug, node.layer, node.name))
            have_nodes.add(node.slug)
        else:
            continue
        if node.description:
            written = exists and bool(state.items[node.slug].descriptions)
            if not written:
                plan.actions.append(Action("description", node.slug, node.layer))
        if node.slug in state.retitles:
            plan.actions.append(
                Action("retitle", node.slug, node.layer, state.retitles[node.slug][1])
            )
        for tag in node.tags:
            if tag not in have_definitions:
                missing("the definition", tag, "core", f"The node {node.slug!r}")
                continue
            already = exists and any(
                t.name == tag and t.value is True for t in state.items[node.slug].tags
            )
            if not already:
                plan.actions.append(Action("tag", f"{node.slug}: {tag}", node.layer))

    for recipe in (r for r in spec.recipes if r.layer in layers):
        label = f"{recipe.node}: {recipe.stat}"
        if recipe.node not in have_nodes:
            missing("the node", recipe.node, spec.node(recipe.node).layer, f"The recipe {label!r}")
            continue
        needed = [recipe.stat, *([recipe.source] if recipe.source else recipe.terms)]
        absent = [name for name in needed if name not in have_definitions]
        if absent:
            missing("the definition", absent[0], "core", f"The recipe {label!r}")
            continue
        present_recipe = state.recipes.get((recipe.node, recipe.stat))
        if present_recipe is None:
            plan.actions.append(Action("recipe", label, recipe.layer, recipe.kind))
        else:
            if present_recipe.formula.kind != recipe.kind:
                plan.warnings.append(
                    f"{label!r} already has a {present_recipe.formula.kind} formula, not the "
                    f"seed's {recipe.kind}. It is left as it is."
                )
            plan.existing += 1
    return plan
