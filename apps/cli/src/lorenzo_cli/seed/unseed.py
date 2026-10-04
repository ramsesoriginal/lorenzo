"""Taking a layer of the seed out of a tenant again (ADR 0168).

It finds what the seed made the way `seed` does, by slug and name, so it can only ever touch what
the built-in seed names. Categories go first, then stat definitions, then stat groups. A category
that something outside the layer inherits from stops it before anything is deleted; whether a
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
    Op,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.plan import resolve_nodes
from lorenzo_cli.seed.spec import SeedSpec

TargetKind = Literal["node", "definition", "group"]


@dataclass(frozen=True)
class Target:
    kind: TargetKind
    # A node's slug, a definition's or a group's name.
    name: str
    layer: str
    id: UUID
    # A node's own name.
    detail: str = ""


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

    held: dict[str, list[str]] = {}
    for node in nodes:
        outside = [e.name for e in state.inheritors.get(node.slug, []) if e.id not in going]
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
        return plan

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
    """Categories, then definitions, then groups. A refusal is kept and the rest goes on."""
    tenant = {"tenant_id": plan.tenant.id}
    result = UnseedResult()
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
