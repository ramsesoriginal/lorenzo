"""What a library holds that a document can name, read in a few paged requests: its systems, stat
groups and stats, and every entry with its slug, kinds, parents, own values and information (the
entry export of ADR 0262)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    EntityExportPage,
    InformationOut,
    StatDefinitionOut,
    StatGroupOut,
    SystemOut,
    TenantOut,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient

EXPORT_PAGE = 500


@dataclass
class EntryState:
    id: UUID
    slug: str | None
    name: str
    kinds: list[str]
    parent_ids: list[UUID]
    # Own values by stat id; a dice value is its notation.
    values: dict[UUID, Any]
    information: list[InformationOut]

    def description(self) -> InformationOut | None:
        return next((i for i in self.information if i.type == "description"), None)


@dataclass
class LibraryState:
    tenant: TenantOut
    systems: dict[str, SystemOut] = field(default_factory=dict)
    groups: dict[str, StatGroupOut] = field(default_factory=dict)
    stats: dict[str, StatDefinitionOut] = field(default_factory=dict)
    entries: dict[UUID, EntryState] = field(default_factory=dict)
    # Formulas by (entry, stat), as the API writes them; read only for the entries asked for.
    formulas: dict[tuple[UUID, UUID], dict[str, Any]] = field(default_factory=dict)
    formulas_read: set[UUID] = field(default_factory=set)

    def system_of(self, group: StatGroupOut) -> SystemOut | None:
        return next((s for s in self.systems.values() if s.id == group.system_id), None)

    def entry(self, slug: str) -> EntryState | None:
        return next((e for e in self.entries.values() if e.slug == slug), None)

    def slug_of(self, entry_id: UUID) -> str | None:
        found = self.entries.get(entry_id)
        return found.slug if found else None

    def stat_by_id(self, stat_id: UUID) -> StatDefinitionOut | None:
        return next((s for s in self.stats.values() if s.id == stat_id), None)

    def group_by_id(self, group_id: UUID) -> StatGroupOut | None:
        return next((g for g in self.groups.values() if g.id == group_id), None)

    def children(self) -> dict[UUID, list[UUID]]:
        found: dict[UUID, list[UUID]] = {}
        for entry in self.entries.values():
            for parent in entry.parent_ids:
                found.setdefault(parent, []).append(entry.id)
        return found

    def descendants(self, root: UUID) -> set[UUID]:
        """`root` and everything that inherits from it, however far down."""
        below = self.children()
        seen = {root}
        todo = [root]
        while todo:
            for child in below.get(todo.pop(), []):
                if child not in seen:
                    seen.add(child)
                    todo.append(child)
        return seen


def read(client: LorenzoClient, tenant: TenantOut) -> LibraryState:
    path = {"tenant_id": tenant.id}
    state = LibraryState(tenant=tenant)
    for system in all_items(client, ops.LIST_SYSTEMS, path=path, of=SystemOut):
        state.systems[system.slug] = system
    for group in all_items(client, ops.LIST_STAT_GROUPS, path=path, of=StatGroupOut):
        state.groups[group.name] = group
    for stat in all_items(client, ops.LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut):
        state.stats[stat.name] = stat
    cursor: str | None = None
    while True:
        page: EntityExportPage = client.call(
            ops.EXPORT_ENTITIES, path=path, query={"cursor": cursor, "limit": EXPORT_PAGE}
        ).value
        for row in page.items:
            state.entries[row.id] = EntryState(
                id=row.id,
                slug=row.slug,
                name=row.name,
                kinds=[k.value for k in row.kinds],
                parent_ids=list(row.parent_ids),
                values={s.stat_definition_id: s.value for s in row.stats},
                information=list(row.information),
            )
        cursor = page.next_cursor
        if cursor is None:
            return state


def read_formulas(client: LorenzoClient, state: LibraryState, entry_ids: set[UUID]) -> None:
    """The formulas held by these entries, one request each: only the entries a document or an
    export names, never the whole library."""
    for entry_id in sorted(entry_ids):
        if entry_id in state.formulas_read:
            continue
        rows = client.call(
            ops.LIST_ENTITY_COMPUTED_STATS,
            path={"tenant_id": state.tenant.id, "entity_id": entry_id},
        ).value
        for row in rows:
            state.formulas[(entry_id, row.stat_definition_id)] = row.formula.model_dump(
                mode="json", by_alias=True
            )
        state.formulas_read.add(entry_id)


def description_text(information: InformationOut) -> str:
    """The text of a description: its description payloads, in order."""
    parts = []
    for payload in information.payloads:
        dumped = payload.model_dump()
        if dumped.get("kind") == "description":
            parts.append(str(dumped.get("content", "")))
    return "\n\n".join(parts)
