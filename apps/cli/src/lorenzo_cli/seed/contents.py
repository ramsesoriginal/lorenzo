"""What a repository tenant holds, and how much of each seed layer it has (ADR 0169).

The seed layers are found the way `seed` and `unseed` find them, by slug and name, so what this
reports agrees with what `seed --dry-run` would do. Only what the seed names is matched; the rest
is counted as beyond the seed.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

from lorenzo_cli import repos
from lorenzo_cli.client.models import (
    PageItemOut,
    StatDefinitionOut,
    StatGroupOut,
    SubscriptionOut,
    TenantOut,
)
from lorenzo_cli.client.ops import LIST_ITEMS, LIST_STAT_DEFINITIONS, LIST_STAT_GROUPS
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed.plan import resolve_nodes
from lorenzo_cli.seed.spec import LAYERS, SeedSpec

Holds = Literal["complete", "partly", "not there"]


@dataclass(frozen=True)
class Part:
    """How many of a layer's entries of one kind the tenant has, out of how many the seed has."""

    present: int
    in_seed: int


@dataclass(frozen=True)
class LayerHolding:
    layer: str
    groups: Part
    definitions: Part
    categories: Part

    @property
    def holds(self) -> Holds:
        parts = (self.groups, self.definitions, self.categories)
        if sum(p.present for p in parts) == 0:
            return "not there"
        if all(p.present == p.in_seed for p in parts):
            return "complete"
        return "partly"


@dataclass(frozen=True)
class Contents:
    tenant: TenantOut
    granted_to: int
    # The repositories it has copied: what it is built on (ADR 0120).
    built_on: list[SubscriptionOut]
    stat_groups: int
    stat_definitions: int
    # Every item, the categories the seed made included.
    items: int
    seed_version: str
    layers: list[LayerHolding]
    # What the seed doesn't name.
    other_stat_groups: int
    other_stat_definitions: int
    other_items: int


def holdings(
    spec: SeedSpec,
    *,
    groups: Collection[str],
    definitions: Collection[str],
    categories: Collection[str],
) -> list[LayerHolding]:
    """Each seed layer against the stat group names, stat definition names and category slugs a
    tenant has."""
    return [
        LayerHolding(
            layer=layer,
            groups=Part(
                sum(g.name in groups for g in spec.groups if g.layer == layer),
                sum(g.layer == layer for g in spec.groups),
            ),
            definitions=Part(
                sum(d.name in definitions for d in spec.definitions if d.layer == layer),
                sum(d.layer == layer for d in spec.definitions),
            ),
            categories=Part(
                sum(n.slug in categories for n in spec.nodes if n.layer == layer),
                sum(n.layer == layer for n in spec.nodes),
            ),
        )
        for layer in LAYERS
    ]


def read_contents(client: LorenzoClient, repository: TenantOut, spec: SeedSpec) -> Contents:
    path = {"tenant_id": repository.id}
    groups = {g.name for g in all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)}
    definitions = {
        d.name for d in all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }
    nodes = resolve_nodes(client, repository.id, [node.slug for node in spec.nodes])
    seed_items = sum("item" in {kind.value for kind in found.kinds} for found in nodes.values())
    # One request for the total, however many items there are.
    page: PageItemOut = client.call(LIST_ITEMS, path=path, query={"page": 1, "size": 1}).value
    subscribers = repos.list_subscribers(client, repository.id)
    built_on = [row for row in repos.list_repositories(client, repository.id) if row.copied_at]
    return Contents(
        tenant=repository,
        granted_to=len(subscribers),
        built_on=built_on,
        stat_groups=len(groups),
        stat_definitions=len(definitions),
        items=page.total,
        seed_version=spec.version,
        layers=holdings(spec, groups=groups, definitions=definitions, categories=nodes.keys()),
        other_stat_groups=len(groups - {g.name for g in spec.groups}),
        other_stat_definitions=len(definitions - {d.name for d in spec.definitions}),
        other_items=max(0, page.total - seed_items),
    )
