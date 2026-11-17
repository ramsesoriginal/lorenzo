"""What a repository tenant holds (ADR 0169, ADR 0492): whether it is published and to whom it is
granted, what it is built on, its systems and templates, its stats by system, the roles they hold,
and how much of each other kind of row it holds. Read from the API, not from a file shipped with
the CLI."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from lorenzo_cli import repos
from lorenzo_cli.client.models import (
    EntityDetailOut,
    StatDefinitionOut,
    StatGroupOut,
    SubscriptionOut,
    SystemOut,
    TemplateSummaryOut,
    TenantOut,
)
from lorenzo_cli.client.ops import (
    GET_ENTITY,
    LIST_ATTACHMENTS,
    LIST_ENTITIES,
    LIST_GRANT_RULES,
    LIST_ITEMS,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
    LIST_SYSTEMS,
    LIST_TEMPLATES,
    Op,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient

# What a row with no system is counted under.
NEUTRAL = "neutral"


@dataclass(frozen=True)
class SystemRow:
    slug: str
    name: str
    # The root entry's slug, or its name when it has none; None when the system has no root.
    root: str | None


@dataclass(frozen=True)
class Role:
    role: str
    # "stat" or "stat group"
    holder: str
    name: str
    system: str


@dataclass(frozen=True)
class Contents:
    tenant: TenantOut
    granted_to: int
    # The repositories it has copied: what it is built on (ADR 0120).
    built_on: list[SubscriptionOut]
    systems: list[SystemRow]
    templates: list[TemplateSummaryOut]
    # Stat groups and stat definitions per system slug, NEUTRAL for those of none.
    stat_groups_by_system: dict[str, int]
    stat_definitions_by_system: dict[str, int]
    roles: list[Role]
    entries: int
    # Every item, the categories included.
    items: int
    features: int
    grant_rules: int
    # The parents it adds to items copied from elsewhere (ADR 0172, 0174).
    attachments: int

    @property
    def stat_groups(self) -> int:
        return sum(self.stat_groups_by_system.values())

    @property
    def stat_definitions(self) -> int:
        return sum(self.stat_definitions_by_system.values())


def _total(client: LorenzoClient, op: Op[Any], path: dict[str, object], **query: Any) -> int:
    """A list's total in one request, however many rows there are."""
    return int(client.call(op, path=path, query={**query, "page": 1, "size": 1}).value.total)


def read_contents(client: LorenzoClient, repository: TenantOut) -> Contents:
    path: dict[str, object] = {"tenant_id": repository.id}
    reads: dict[str, Callable[[], Any]] = {
        "groups": lambda: list(all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)),
        "definitions": lambda: list(
            all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
        ),
        "systems": lambda: list(all_items(client, LIST_SYSTEMS, path=path, of=SystemOut)),
        "templates": lambda: list(
            all_items(client, LIST_TEMPLATES, path=path, of=TemplateSummaryOut)
        ),
        "entries": lambda: _total(client, LIST_ENTITIES, path),
        "items": lambda: _total(client, LIST_ITEMS, path),
        "features": lambda: _total(client, LIST_ENTITIES, path, kind=["feature"]),
        "grant_rules": lambda: _total(client, LIST_GRANT_RULES, path),
        "attachments": lambda: _total(client, LIST_ATTACHMENTS, path),
        "subscribers": lambda: repos.list_subscribers(client, repository.id),
        "built_on": lambda: [
            row for row in repos.list_repositories(client, repository.id) if row.copied_at
        ],
    }
    # Independent reads, four at a time (ADR 0483).
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {name: pool.submit(read) for name, read in reads.items()}
        got = {name: future.result() for name, future in futures.items()}

    systems: list[SystemOut] = got["systems"]
    slug_of = {system.id: system.slug for system in systems}
    groups: list[StatGroupOut] = got["groups"]
    system_of = {
        g.id: slug_of.get(g.system_id, NEUTRAL) if g.system_id else NEUTRAL for g in groups
    }
    definitions: list[StatDefinitionOut] = got["definitions"]
    roles = [
        Role(g.role.value, "stat group", g.name, system_of[g.id]) for g in groups if g.role
    ] + [
        Role(d.role.value, "stat", d.name, system_of.get(d.stat_group_id, NEUTRAL))
        for d in definitions
        if d.role
    ]
    return Contents(
        tenant=repository,
        granted_to=len(got["subscribers"]),
        built_on=got["built_on"],
        systems=[_system_row(client, repository.id, s) for s in systems],
        templates=got["templates"],
        stat_groups_by_system=_count(system_of[g.id] for g in groups),
        stat_definitions_by_system=_count(
            system_of.get(d.stat_group_id, NEUTRAL) for d in definitions
        ),
        roles=sorted(roles, key=lambda r: (r.system, r.role, r.name)),
        entries=got["entries"],
        items=got["items"],
        features=got["features"],
        grant_rules=got["grant_rules"],
        attachments=got["attachments"],
    )


def _count(keys: Any) -> dict[str, int]:
    return dict(sorted(Counter(keys).items()))


def _system_row(client: LorenzoClient, tenant_id: UUID, system: SystemOut) -> SystemRow:
    root = None
    if system.root_entry_id is not None:
        entry: EntityDetailOut = client.call(
            GET_ENTITY, path={"tenant_id": tenant_id, "entity_id": system.root_entry_id}
        ).value
        root = entry.slug or entry.name
    return SystemRow(system.slug, system.name, root)
