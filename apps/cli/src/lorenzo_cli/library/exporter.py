"""A library's system, or its neutral vocabulary, written back as a document (ADR 0484).

A system's document holds its row, its groups and their stats, and the entries under its root that
are vocabulary: features and what others inherit from, not the leaf items imported under it. The
neutral document holds the groups of no system, their stats, and the vocabulary entries under no
system's root. Applying an export to an empty library and exporting again gives the same document.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lorenzo_cli.client.models import StatDefinitionOut, StatGroupOut
from lorenzo_cli.library.document import Document, EntryRow, GroupRow, StatRow, SystemRow
from lorenzo_cli.library.planner import is_vocabulary_entry
from lorenzo_cli.library.state import EntryState, LibraryState, description_text

NEUTRAL = "neutral"


class ExportError(Exception):
    """What was asked for is not in the library."""


def _value(current: Any) -> Any:
    return current.value if hasattr(current, "value") else current


def _group_row(group: StatGroupOut, *, of_system: bool) -> GroupRow:
    return GroupRow(
        name=group.name,
        system=of_system,
        role=_value(group.role),
        priority=group.priority or None,
        mandatory=group.mandatory or None,
        position=group.position,
    )


def _stat_row(stat: StatDefinitionOut, group: StatGroupOut, state: LibraryState) -> StatRow:
    def hint(stat_id: UUID | None) -> str | None:
        found = state.stat_by_id(stat_id) if stat_id else None
        return found.name if found else None

    return StatRow(
        name=stat.name,
        group=group.name,
        type=stat.value_type.value,
        values=list(stat.enum_values) or None,
        unit=stat.unit,
        role=_value(stat.role),
        min=stat.min_value,
        max=stat.max_value,
        max_hint=hint(stat.max_hint_id),
        min_hint=hint(stat.min_hint_id),
        resolved_hint=hint(stat.resolved_hint_id),
        adjustable_in_play=stat.adjustable_in_play or None,
        pin=stat.pin or None,
        signed=stat.signed or None,
        position=stat.position,
    )


def _entry_row(entry: EntryState, state: LibraryState) -> EntryRow:
    stats: dict[str, Any] = {}
    tags: list[str] = []
    for stat_id, value in entry.values.items():
        stat = state.stat_by_id(stat_id)
        if stat is None:
            continue
        group = state.group_by_id(stat.stat_group_id)
        if value is True and group is not None and _value(group.role) == "tags":
            tags.append(stat.name)
        else:
            stats[stat.name] = value
    held = entry.description()
    return EntryRow(
        slug=entry.slug or str(entry.id),
        name=entry.name,
        kinds=[k for k in entry.kinds if k in ("item", "being", "fact", "event", "feature")]
        or ["item"],
        parents=[slug for p in entry.parent_ids if (slug := state.slug_of(p)) is not None],
        stats=dict(sorted(stats.items())),
        tags=sorted(tags),
        description=description_text(held) if held is not None else None,
    )


def _ordered(entries: list[EntryState], state: LibraryState) -> list[EntryState]:
    """Parents before children, then by slug, so the document reads top down and is stable."""
    chosen = {e.id for e in entries}
    placed: list[EntryState] = []
    done: set[UUID] = set()

    def place(entry: EntryState) -> None:
        if entry.id in done:
            return
        done.add(entry.id)
        for parent in entry.parent_ids:
            if parent in chosen:
                place(state.entries[parent])
        placed.append(entry)

    for entry in sorted(entries, key=lambda e: e.slug or str(e.id)):
        place(entry)
    return placed


def export(state: LibraryState, system_slug: str | None) -> Document:
    """The document of `system_slug`, or of the neutral vocabulary when it is None."""
    children = state.children()
    roots = {s.root_entry_id for s in state.systems.values() if s.root_entry_id is not None}
    under_systems: set[UUID] = set()
    for root in roots:
        under_systems |= state.descendants(root)

    if system_slug is None:
        groups = [g for g in state.groups.values() if g.system_id is None]
        entries = [
            e
            for e in state.entries.values()
            if e.id not in under_systems and is_vocabulary_entry(e, children)
        ]
        system_row = None
        name = NEUTRAL
    else:
        system = state.systems.get(system_slug)
        if system is None:
            known = ", ".join(sorted(state.systems)) or "none"
            raise ExportError(f"No system {system_slug} in this library (it has: {known}).")
        groups = [g for g in state.groups.values() if g.system_id == system.id]
        under = state.descendants(system.root_entry_id) if system.root_entry_id else set()
        entries = [
            state.entries[e]
            for e in under
            if e in state.entries
            and (e == system.root_entry_id or is_vocabulary_entry(state.entries[e], children))
        ]
        root_entry = state.entries.get(system.root_entry_id) if system.root_entry_id else None
        system_row = SystemRow(
            slug=system.slug, name=system.name, root=root_entry.slug if root_entry else None
        )
        name = system.slug

    group_ids = {g.id for g in groups}
    groups.sort(key=lambda g: (g.position, g.name))
    stats = sorted(
        (s for s in state.stats.values() if s.stat_group_id in group_ids),
        key=lambda s: (s.position, s.name),
    )
    by_group = {g.id: g for g in groups}
    ordered = _ordered(entries, state)
    doc_entries = [_entry_row(e, state) for e in ordered]

    # What the document refers to and does not hold comes from another document.
    named_stats = {s.name for s in stats}
    named_entries = {e.slug for e in doc_entries}
    outside = any(n not in named_stats for e in doc_entries for n in (*e.stats, *e.tags)) or any(
        p not in named_entries for e in doc_entries for p in e.parents
    )
    requires = [NEUTRAL] if system_slug is not None and outside else []

    return Document(
        format=1,
        name=name,
        requires=requires,
        system=system_row,
        group=[_group_row(g, of_system=system_slug is not None) for g in groups],
        stat=[_stat_row(s, by_group[s.stat_group_id], state) for s in stats],
        entry=doc_entries,
    )


def to_toml(doc: Document) -> str:
    """The document as TOML: only the fields that say something, in the document's order."""
    import tomli_w

    data = doc.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    data = {"format": doc.format, "name": doc.name, **data}
    for entry in data.get("entry", []):
        if entry.get("kinds") == ["item"]:
            entry.pop("kinds")
    return str(tomli_w.dumps(data, multiline_strings=True))
