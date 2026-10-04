"""Taking a layer of the seed out of a tenant again (ADR 0168, 0181).

It finds what the seed made the way `seed` does, by slug and name, so it can only ever touch what
the built-in seed names. A layer's attachments go first (the parent is dropped from the child's
parents and nothing else of the child is touched), then categories, then stat definitions, then
stat groups. A category that something outside the layer inherits from stops it before anything is
deleted, unless the thing is the child of an attachment that is going in the same call; whether a
stat definition is used is only known to the API, so each one is tried and a refusal is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import (
    EntitySummary,
    ResolvedSlugOut,
    SetPrototypesRequest,
    StatDefinitionOut,
    StatGroupOut,
    TenantOut,
)
from lorenzo_cli.client.ops import (
    DELETE_ITEM,
    DELETE_STAT_DEFINITION,
    DELETE_STAT_GROUP,
    GET_ENTITY,
    GET_ITEM,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
    REPLACE_ITEM_PROTOTYPES,
    Op,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.plan import resolve_nodes
from lorenzo_cli.seed.spec import SeedSpec

TargetKind = Literal["attachment", "node", "definition", "group"]


@dataclass(frozen=True)
class Target:
    kind: TargetKind
    # A node's slug, a definition's or a group's name, an attachment's "<child>: <parent>".
    name: str
    layer: str
    # An attachment's is its child's.
    id: UUID
    # A node's own name.
    detail: str = ""
    # An attachment's parent.
    parent_id: UUID | None = None


@dataclass(frozen=True)
class Kept:
    """Something the API refused to delete, with its reason."""

    kind: TargetKind
    name: str
    reason: str


@dataclass
class UnseedState:
    nodes: dict[str, ResolvedSlugOut] = field(default_factory=dict)
    # node slug -> the entities that have it as a prototype.
    inheritors: dict[str, list[EntitySummary]] = field(default_factory=dict)
    definitions: dict[str, StatDefinitionOut] = field(default_factory=dict)
    groups: dict[str, StatGroupOut] = field(default_factory=dict)
    # The slugs an attachment's child and parent have, of the attachments that matter here.
    attachments: dict[str, ResolvedSlugOut] = field(default_factory=dict)
    # The (child slug, parent slug) of those attachments that the tenant has.
    attached: set[tuple[str, str]] = field(default_factory=set)


@dataclass
class UnseedPlan:
    tenant: TenantOut
    layers: tuple[str, ...]
    spec_version: str
    targets: list[Target] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def of(self, kind: TargetKind) -> list[Target]:
        return [t for t in self.targets if t.kind == kind]


@dataclass
class UnseedResult:
    deleted: list[Target] = field(default_factory=list)
    kept: list[Kept] = field(default_factory=list)


def read_unseed_state(
    client: LorenzoClient, tenant_id: UUID, spec: SeedSpec, layers: tuple[str, ...]
) -> UnseedState:
    path = {"tenant_id": tenant_id}
    slugs = [n.slug for n in spec.nodes if n.layer in layers]
    state = UnseedState(nodes=resolve_nodes(client, tenant_id, slugs))
    for slug, found in state.nodes.items():
        detail = client.call(GET_ENTITY, path={**path, "entity_id": found.entity_id}).value
        state.inheritors[slug] = detail.instances
    # An attachment's two ends are mostly in other layers, so they are looked up by themselves: the
    # layers' own attachments, and the others' that point at a category going out with the layers.
    going = {n.slug for n in spec.nodes if n.layer in layers}
    relevant = [a for a in spec.attachments if a.layer in layers or a.parent in going]
    ends = sorted({end for a in relevant for end in (a.child, a.parent)})
    state.attachments = resolve_nodes(client, tenant_id, ends)
    for child in {a.child for a in relevant if a.child in state.attachments}:
        found = state.attachments[child]
        detail = client.call(GET_ENTITY, path={**path, "entity_id": found.entity_id}).value
        has = {p.id for p in detail.prototypes}
        state.attached |= {
            (a.child, a.parent)
            for a in relevant
            if a.child == child
            and a.parent in state.attachments
            and state.attachments[a.parent].entity_id in has
        }
    state.definitions = {
        d.name: d for d in all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }
    state.groups = {
        g.name: g for g in all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)
    }
    return state


def make_unseed_plan(
    spec: SeedSpec, state: UnseedState, tenant: TenantOut, layers: tuple[str, ...]
) -> UnseedPlan:
    plan = UnseedPlan(tenant=tenant, layers=layers, spec_version=spec.version)
    nodes = [n for n in spec.nodes if n.layer in layers and n.slug in state.nodes]
    going = {state.nodes[n.slug].entity_id for n in nodes}
    attachments = [a for a in spec.attachments if (a.child, a.parent) in state.attached]
    # What an attachment of the layers gives a child is taken from it first, so the child doesn't
    # hold the parent's category here any more.
    detaching = {
        (state.attachments[a.child].entity_id, state.attachments[a.parent].entity_id)
        for a in attachments
        if a.layer in layers
    }

    held: dict[str, list[str]] = {}
    for node in nodes:
        node_id = state.nodes[node.slug].entity_id
        outside = [
            e.name
            for e in state.inheritors.get(node.slug, [])
            if e.id not in going and (e.id, node_id) not in detaching
        ]
        if outside:
            held[node.slug] = outside
    if held:
        things = {name for names in held.values() for name in names}
        by_category = ", ".join(f"{slug} ({len(names)})" for slug, names in held.items())
        sample = ", ".join(sorted(things)[:3]) + (" ..." if len(things) > 3 else "")
        plan.problems.append(
            f"Things outside the {' and '.join(layers)} layer have these categories as parents, so "
            f"nothing was deleted: {by_category}. That is {len(things)} thing(s), among them "
            f"{sample}. Taking the categories out would take their parent away: remove or "
            "re-parent them first."
        )
        # The seed's own attachments are the easy case: they go with the layer that makes them.
        makers = sorted(
            {a.layer for a in attachments if a.parent in held and a.layer not in layers}
        )
        if makers:
            flags = " ".join(f"--layer {layer}" for layer in (*layers, *makers))
            plan.problems.append(
                f"Some of them are the seed's own attachments, which the {' and '.join(makers)} "
                f"layer makes: take that layer out in the same call ({flags})."
            )
        return plan

    for attachment in attachments:
        if attachment.layer in layers:
            plan.targets.append(
                Target(
                    "attachment",
                    f"{attachment.child}: {attachment.parent}",
                    attachment.layer,
                    state.attachments[attachment.child].entity_id,
                    parent_id=state.attachments[attachment.parent].entity_id,
                )
            )
    for node in nodes:
        plan.targets.append(
            Target("node", node.slug, node.layer, state.nodes[node.slug].entity_id, node.name)
        )
    for definition in spec.definitions:
        if definition.layer in layers and definition.name in state.definitions:
            plan.targets.append(
                Target(
                    "definition",
                    definition.name,
                    definition.layer,
                    state.definitions[definition.name].id,
                )
            )
    for group in spec.groups:
        if group.layer in layers and group.name in state.groups:
            plan.targets.append(
                Target("group", group.name, group.layer, state.groups[group.name].id)
            )
    return plan


def apply_unseed(client: LorenzoClient, plan: UnseedPlan) -> UnseedResult:
    """Attachments, then categories, then definitions, then groups. A refusal is kept and the rest
    goes on."""
    tenant = {"tenant_id": plan.tenant.id}
    result = UnseedResult()
    for target in plan.of("attachment"):
        path = {**tenant, "entity_id": target.id}
        try:
            current = client.call(GET_ITEM, path=path)
            keep = [p for p in current.value.prototype_ids if p != target.parent_id]
            if len(keep) != len(current.value.prototype_ids):
                client.call(
                    REPLACE_ITEM_PROTOTYPES,
                    path=path,
                    body=SetPrototypesRequest(prototype_ids=keep),
                    if_match=current.etag,
                )
        except LorenzoApiError as exc:
            if exc.status != 404:  # already gone is as good as detached
                result.kept.append(Kept("attachment", target.name, str(exc)))
                continue
        result.deleted.append(target)
    for target in plan.of("node"):
        path = {**tenant, "entity_id": target.id}
        try:
            current = client.call(GET_ITEM, path=path)
            client.call(DELETE_ITEM, path=path, if_match=current.etag)
        except LorenzoApiError as exc:
            if exc.status != 404:  # already gone is as good as deleted
                result.kept.append(Kept("node", target.name, str(exc)))
                continue
        result.deleted.append(target)
    for target in plan.of("definition"):
        _delete(
            client,
            DELETE_STAT_DEFINITION,
            {**tenant, "stat_definition_id": target.id},
            target,
            result,
        )
    for target in plan.of("group"):
        _delete(client, DELETE_STAT_GROUP, {**tenant, "stat_group_id": target.id}, target, result)
    return result


def _delete(
    client: LorenzoClient,
    op: Op[None],
    path: dict[str, object],
    target: Target,
    result: UnseedResult,
) -> None:
    try:
        client.call(op, path=path)
    except LorenzoApiError as exc:
        if exc.status != 404:
            result.kept.append(Kept(target.kind, target.name, str(exc)))
            return
    result.deleted.append(target)
