"""Reading what a tenant already has and working out what `seed` would create (ADR 0143, 0181).

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
    LIST_ITEMS,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
    RESOLVE_SLUGS,
)
from lorenzo_cli.client.paging import PAGE_SIZE, all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.spec import AttachmentSpec, NodeSpec, SeedSpec, StatValue

ActionKind = Literal[
    "group", "definition", "node", "description", "retitle", "tag", "stat", "attach", "recipe"
]
_RESOLVE_BATCH = 100  # GET .../entities/resolve takes at most this many slugs (ADR 0107)
# A page of the item listing costs about 40 ms and under a millisecond a row; a request for one item
# costs about 30 ms. So the listing reads every node the tenant has in a request or two, and is
# still no dearer than reading them one at a time for a tenant of up to this many pages of items. A
# bigger one (an import of thousands) is read node by node.
_MAX_LISTED_PAGES = 10


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    # A group or definition name, a node slug, or "<slug>: <tag, stat or parent>".
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
    # (node slug, stat name) -> the value the node holds itself, for the stats the seed sets.
    own_stats: dict[tuple[str, str], StatValue] = field(default_factory=dict)


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


def resolve_nodes(
    client: LorenzoClient, tenant_id: UUID, slugs: list[str]
) -> dict[str, ResolvedSlugOut]:
    """The slugs the tenant has, in as few requests as the API allows."""
    found: dict[str, ResolvedSlugOut] = {}
    for start in range(0, len(slugs), _RESOLVE_BATCH):
        batch = slugs[start : start + _RESOLVE_BATCH]
        for hit in client.call(
            RESOLVE_SLUGS, path={"tenant_id": tenant_id}, query={"slug": batch}
        ).value:
            found[hit.slug] = hit
    return found


def read_items(
    client: LorenzoClient, tenant_id: UUID, wanted: dict[str, UUID]
) -> dict[str, ItemOut]:
    """The items of these nodes (slug -> entity id), from the tenant's item listing where that is
    cheaper than asking for each, which it is for every tenant but one with a great many items.

    Whatever the listing doesn't hold (it lists only what the caller may see) is asked for by id,
    as it always was, so the answer is the same either way."""
    path = {"tenant_id": tenant_id}
    by_id = {entity_id: slug for slug, entity_id in wanted.items()}
    found: dict[str, ItemOut] = {}
    if wanted:
        page = client.call(LIST_ITEMS, path=path, query={"page": 1, "size": PAGE_SIZE}).value
        if page.pages <= _MAX_LISTED_PAGES:
            for number in range(1, page.pages + 1):
                if number > 1:
                    query = {"page": number, "size": PAGE_SIZE}
                    page = client.call(LIST_ITEMS, path=path, query=query).value
                for listed in page.items:
                    if listed.entity_id in by_id:
                        found[by_id[listed.entity_id]] = listed
    for slug, entity_id in wanted.items():
        if slug not in found:
            found[slug] = client.call(GET_ITEM, path={**path, "entity_id": entity_id}).value
    return {slug: found[slug] for slug in wanted}


def read_state(client: LorenzoClient, tenant_id: UUID, spec: SeedSpec) -> TenantState:
    path = {"tenant_id": tenant_id}
    groups = {g.name: g for g in all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)}
    definitions = {
        d.name: d for d in all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }

    nodes = resolve_nodes(client, tenant_id, [node.slug for node in spec.nodes])

    items = read_items(
        client,
        tenant_id,
        {
            slug: found.entity_id
            for slug, found in nodes.items()
            if "item" in {kind.value for kind in found.kinds}
        },
    )
    retitles: dict[str, tuple[UUID, str]] = {}
    for slug, read in items.items():
        if read.title == descriptions.PLACEHOLDER_TITLE:
            # Its title is the description's, so the row may be the placeholder: look.
            detail = client.call(
                GET_ENTITY, path={**path, "entity_id": nodes[slug].entity_id}
            ).value
            stale = descriptions.placeholder_description(detail)
            if stale is not None:
                retitles[slug] = (stale.id, detail.name)

    own_stats: dict[tuple[str, str], StatValue] = {}
    for node in spec.nodes:
        if node.stats and node.slug in items:
            held = client.call(GET_ENTITY, path={**path, "entity_id": nodes[node.slug].entity_id})
            own_stats.update(
                {(node.slug, stat.name): stat.value for stat in held.value.stats if stat.own}
            )

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
    return TenantState(groups, definitions, nodes, items, recipes, retitles, own_stats)


def _layer_flags(layers: list[str]) -> str:
    return " ".join(f"`--layer {layer}`" for layer in layers)


def is_attached(state: TenantState, attachment: AttachmentSpec) -> bool:
    """Whether the child has the parent among its parents in the tenant."""
    child = state.items.get(attachment.child)
    parent = state.nodes.get(attachment.parent)
    return child is not None and parent is not None and parent.entity_id in child.prototype_ids


def holds_layer(spec: SeedSpec, state: TenantState, layer: str) -> bool:
    """Whether the tenant has at least one of the layer's categories or stat definitions, or, for
    a layer made of attachments, one of them."""
    return (
        any(n.slug in state.nodes for n in spec.nodes if n.layer == layer)
        or any(d.name in state.definitions for d in spec.definitions if d.layer == layer)
        or any(is_attached(state, a) for a in spec.attachments if a.layer == layer)
    )


def make_plan(
    spec: SeedSpec,
    state: TenantState,
    tenant: TenantOut,
    layers: tuple[str, ...],
    *,
    explicit: bool = True,
) -> SeedPlan:
    """`explicit` says the layers were named (`--layer`). A bare seed of a tenant that holds one
    layer and none of another is a problem, not a quiet addition of the other (ADR 0166)."""
    plan = SeedPlan(tenant=tenant, layers=layers, spec_version=spec.version)
    if not explicit:
        held = [layer for layer in layers if holds_layer(spec, state, layer)]
        absent = [layer for layer in layers if layer not in held]
        if held and absent:
            plan.problems.append(
                f"This tenant holds the {' and '.join(held)} layer and none of "
                f"{' and '.join(absent)}. A bare seed would add {' and '.join(absent)}. Name "
                f"the layers you mean: {_layer_flags(held)} to check or complete what it holds, "
                f"or {_layer_flags(absent)} to add that layer."
            )
            return plan
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
    definitions_by_name = {d.name: d for d in spec.definitions}

    def label_of(node: NodeSpec) -> str:
        return f"The node {node.slug!r}"

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
            # What the seed's attachments add to it (ADR 0181) is a parent it may have too.
            attached = {
                state.nodes[a.parent].entity_id
                for a in spec.attachments
                if a.child == node.slug and a.parent in state.nodes
            }
            actual = set(item.prototype_ids)
            if (expected - actual or actual - expected - attached) and len(expected) == len(
                node.parents
            ):
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
                missing("the definition", tag, definitions_by_name[tag].layer, label_of(node))
                continue
            already = exists and any(
                t.name == tag and t.value is True for t in state.items[node.slug].tags
            )
            if not already:
                plan.actions.append(Action("tag", f"{node.slug}: {tag}", node.layer))
        for stat, value in node.stats.items():
            if stat not in have_definitions:
                missing("the definition", stat, definitions_by_name[stat].layer, label_of(node))
                continue
            own = state.own_stats.get((node.slug, stat)) if exists else None
            if own is None:
                plan.actions.append(Action("stat", f"{node.slug}: {stat}", node.layer, str(value)))
            elif own != value:
                plan.warnings.append(
                    f"{node.slug!r} has {stat} {own}, not the seed's {value}. It is left as it is."
                )

    # What the attachments need that the tenant lacks, by the layer that makes them and the layer
    # it is in: a problem each, not one per attachment.
    lacking: dict[str, dict[str, list[str]]] = {}
    for attachment in (a for a in spec.attachments if a.layer in layers):
        label = f"{attachment.child}: {attachment.parent}"
        absent_ends = [e for e in (attachment.child, attachment.parent) if e not in have_nodes]
        for end in absent_ends:
            slugs = lacking.setdefault(attachment.layer, {}).setdefault(spec.node(end).layer, [])
            if end not in slugs:
                slugs.append(end)
        if absent_ends:
            continue
        if attachment.child in state.nodes and attachment.child not in state.items:
            plan.problems.append(
                f"The slug {attachment.child!r} belongs to something that isn't an item in this "
                f"tenant, and the attachment {label!r} needs it."
            )
        elif is_attached(state, attachment):
            plan.existing += 1
        else:
            plan.actions.append(Action("attach", label, attachment.layer))
    for attaching, by_layer in lacking.items():
        what = "; ".join(
            f"{', '.join(slugs[:3])}{' ...' if len(slugs) > 3 else ''} (layer {layer})"
            for layer, slugs in by_layer.items()
        )
        plan.problems.append(
            f"The attachments of the {attaching} layer need categories this tenant doesn't have: "
            f"{what}. Seed {' and '.join(by_layer)} first."
        )

    for recipe in (r for r in spec.recipes if r.layer in layers):
        label = f"{recipe.node}: {recipe.stat}"
        if recipe.node not in have_nodes:
            missing("the node", recipe.node, spec.node(recipe.node).layer, f"The recipe {label!r}")
            continue
        needed = [recipe.stat, *([recipe.source] if recipe.source else recipe.terms)]
        absent = [name for name in needed if name not in have_definitions]
        if absent:
            missing(
                "the definition",
                absent[0],
                definitions_by_name[absent[0]].layer,
                f"The recipe {label!r}",
            )
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
