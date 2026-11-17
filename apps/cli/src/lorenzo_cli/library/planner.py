"""What applying a document to a library would do (ADR 0484): what it creates, changes and, with
`--prune`, removes, in the order the writes depend on one another, and what it cannot do.

A field the document names is set to its value; a field it leaves out is left as the library has
it. Nothing is removed unless pruning, and then only rows of the document's own system.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.library.document import Document, EntryRow, GroupRow, StatRow
from lorenzo_cli.library.state import EntryState, LibraryState, description_text

Verb = Literal["create", "change", "remove"]

# The order writes run in: a level waits for every level before it. Entries are created level by
# level of their depth below what already exists, so a parent is always there first.
SYSTEM, GROUP, STAT, STAT_HINTS, ENTRY = 0, 1, 2, 3, 10
AFTER_ENTRIES, ROOT, REMOVE = 1000, 1001, 2000

GROUP_FIELDS = ("role", "priority", "mandatory", "position")
STAT_FIELDS = (
    "unit",
    "role",
    "min",
    "max",
    "adjustable_in_play",
    "pin",
    "signed",
    "position",
)
HINTS = ("max_hint", "min_hint", "resolved_hint")


@dataclass(frozen=True)
class Action:
    verb: Verb
    kind: str
    key: str
    detail: str = ""
    level: int = 0
    # For a change: the fields to send, as the document names them.
    fields: tuple[tuple[str, Any], ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {"verb": self.verb, "kind": self.kind, "key": self.key, "detail": self.detail}


@dataclass
class Plan:
    document: Document
    tenant: TenantOut
    prune: bool = False
    actions: list[Action] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        found = Counter(a.verb for a in self.actions)
        return {verb: found.get(verb, 0) for verb in ("create", "change", "remove")}

    def levels(self) -> list[list[Action]]:
        by_level: dict[int, list[Action]] = {}
        for action in self.actions:
            by_level.setdefault(action.level, []).append(action)
        return [by_level[level] for level in sorted(by_level)]

    def exit_code(self) -> int:
        """0 nothing to do, 2 changes pending, 1 something it cannot do (ADR 0482)."""
        if self.problems:
            return 1
        return 2 if self.actions else 0


_DICE = re.compile(r"^(\d*)[dw](\d+)(.*)$")


def _dice(text: str) -> tuple[int, int, str] | None:
    """`2d6`, `d6`, `W6` and `1D6` as (count, sides, the rest), the way RFC 0056 reads them."""
    found = _DICE.match(text.strip().lower())
    if found is None:
        return None
    count, sides, rest = found.groups()
    return int(count or 1), int(sides), rest.replace("w", "d")


def same(a: Any, b: Any) -> bool:
    """Whether a value in the library is the value a document names."""
    if isinstance(a, str) and isinstance(b, str):
        dice_a, dice_b = _dice(a), _dice(b)
        if dice_a is not None and dice_b is not None:
            return dice_a == dice_b
        return a.strip().lower() == b.strip().lower()
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or (isinstance(a, bool) and isinstance(b, bool) and a == b)
    if isinstance(a, int | float) and isinstance(b, int | float):
        return float(a) == float(b)
    return bool(a == b)


def is_vocabulary_entry(entry: EntryState, children: dict[UUID, list[UUID]]) -> bool:
    """An entry a document describes: a feature, or one that others inherit from. A leaf item
    (an imported sword, a player's thing) is content, not vocabulary, and is never exported or
    pruned (ADR 0484)."""
    return "feature" in entry.kinds or bool(children.get(entry.id))


class _Planner:
    def __init__(self, doc: Document, state: LibraryState, prune: bool) -> None:
        self.doc = doc
        self.state = state
        self.plan = Plan(document=doc, tenant=state.tenant, prune=prune)
        self.doc_groups = {g.name: g for g in doc.group}
        self.doc_stats = {s.name: s for s in doc.stat}
        self.doc_entries = {e.slug: e for e in doc.entry}

    def add(
        self, verb: Verb, kind: str, key: str, level: int, detail: str = "", **fields: Any
    ) -> None:
        self.plan.actions.append(Action(verb, kind, key, detail, level, tuple(fields.items())))

    def problem(self, text: str) -> None:
        self.plan.problems.append(text)

    # --- references -------------------------------------------------------------------------

    def has_group(self, name: str) -> bool:
        return name in self.doc_groups or name in self.state.groups

    def has_stat(self, name: str) -> bool:
        return name in self.doc_stats or name in self.state.stats

    def has_entry(self, slug: str) -> bool:
        return slug in self.doc_entries or self.state.entry(slug) is not None

    def stat_type(self, name: str) -> str | None:
        if name in self.doc_stats:
            return self.doc_stats[name].type
        found = self.state.stats.get(name)
        return found.value_type.value if found else None

    def group_system_slug(self, name: str) -> str | None:
        """The slug of the system a group belongs to, from the document or the library."""
        if name in self.doc_groups:
            row = self.doc_groups[name]
            if row.system and self.doc.system is not None:
                return self.doc.system.slug
            existing = self.state.groups.get(name)
            if existing is not None and existing.system_id is not None:
                found = self.state.system_of(existing)
                return found.slug if found else None
            return None
        existing = self.state.groups.get(name)
        if existing is None or existing.system_id is None:
            return None
        found = self.state.system_of(existing)
        return found.slug if found else None

    def missing(self, what: str, name: str, where: str) -> None:
        hint = (
            f" (the document requires {', '.join(self.doc.requires)}: apply that first)"
            if self.doc.requires
            else ""
        )
        self.problem(f"{where}: no {what} {name} in this document or the library{hint}.")

    # --- the rows -----------------------------------------------------------------------------

    def system(self) -> None:
        row = self.doc.system
        if row is None:
            return
        existing = self.state.systems.get(row.slug)
        if existing is None:
            self.add("create", "system", row.slug, SYSTEM, row.name)
        elif existing.name != row.name:
            self.add("change", "system", row.slug, SYSTEM, "name", name=row.name)
        if row.root is None:
            return
        if not self.has_entry(row.root):
            self.missing("entry", row.root, f"system {row.slug}'s root")
            return
        root = self.state.entry(row.root)
        if existing is None or root is None or existing.root_entry_id != root.id:
            self.add("change", "root", row.slug, ROOT, f"root {row.root}", root=row.root)

    def roles_held(self) -> None:
        stat_roles = Counter(s.role for s in self.doc.stat if s.role)
        group_roles = Counter(g.role for g in self.doc.group if g.role)
        for stat_role in [r for r, n in stat_roles.items() if n > 1]:
            self.problem(
                f"role {stat_role}: held by more than one stat of the document (ADR 0449)."
            )
        for group_role in [r for r, n in group_roles.items() if n > 1]:
            self.problem(
                f"role {group_role}: held by more than one group of the document (ADR 0449)."
            )

    def group(self, row: GroupRow) -> None:
        existing = self.state.groups.get(row.name)
        if row.role is not None:
            holder = next(
                (
                    g
                    for g in self.state.groups.values()
                    if g.role == row.role and g.name != row.name
                ),
                None,
            )
            if holder is not None:
                self.problem(f"group {row.name}: the role {row.role} is held by {holder.name}.")
        if existing is None:
            detail = f"system {self.doc.system.slug}" if row.system and self.doc.system else ""
            self.add("create", "group", row.name, GROUP, detail)
            return
        changes = {
            f: getattr(row, f)
            for f in GROUP_FIELDS
            if getattr(row, f) is not None and _value(getattr(existing, f)) != getattr(row, f)
        }
        if row.system and self.doc.system is not None:
            current = self.state.system_of(existing)
            if current is None or current.slug != self.doc.system.slug:
                changes["system"] = self.doc.system.slug
        if changes:
            self.add("change", "group", row.name, GROUP, ", ".join(changes), **changes)

    def stat(self, row: StatRow) -> None:
        where = f"stat {row.name}"
        if not self.has_group(row.group):
            self.missing("stat group", row.group, where)
            return
        system = self.group_system_slug(row.group)
        if system is not None and not row.name.startswith(f"{system}_"):
            self.problem(f"{where}: a stat of {row.group} ({system}) is named {system}_something.")
        if system is not None and row.role is not None:
            self.problem(f"{where}: a role is held by a stat of no system (ADR 0449).")
        for hint in HINTS:
            target = getattr(row, hint)
            if target is not None and not self.has_stat(target):
                self.missing("stat", target, f"{where}'s {hint.replace('_', ' ')}")
        if row.role is not None:
            holder = next(
                (s for s in self.state.stats.values() if s.role == row.role and s.name != row.name),
                None,
            )
            if holder is not None:
                self.problem(f"{where}: the role {row.role} is held by {holder.name}.")
        existing = self.state.stats.get(row.name)
        hints = {h: getattr(row, h) for h in HINTS if getattr(row, h) is not None}
        if existing is None:
            self.add("create", "stat", row.name, STAT, f"{row.type} in {row.group}")
            if hints:
                self.add("change", "stat", row.name, STAT_HINTS, ", ".join(hints), **hints)
            return
        if existing.value_type.value != row.type:
            self.problem(
                f"{where}: it is {existing.value_type.value} here, and a stat's type can't change."
            )
        group = self.state.group_by_id(existing.stat_group_id)
        if group is not None and group.name != row.group:
            self.problem(f"{where}: it is in {group.name} here, and a stat can't move group.")
        changes: dict[str, Any] = {}
        for name in STAT_FIELDS:
            wanted = getattr(row, name)
            current = getattr(existing, {"min": "min_value", "max": "max_value"}.get(name, name))
            if wanted is not None and not same(_value(current), wanted):
                changes[name] = wanted
        for hint, target in hints.items():
            current_id = getattr(existing, f"{hint}_id")
            current = self.state.stat_by_id(current_id) if current_id else None
            if current is None or current.name != target:
                changes[hint] = target
        if row.values and list(existing.enum_values) != row.values:
            self.plan.notes.append(f"{where}: its enum values differ here; they are not changed.")
        if changes:
            self.add("change", "stat", row.name, STAT_HINTS, ", ".join(changes), **changes)

    def entries(self) -> None:
        depths: dict[str, int] = {}

        def depth(slug: str, seen: tuple[str, ...] = ()) -> int:
            if slug in depths:
                return depths[slug]
            row = self.doc_entries.get(slug)
            if row is None or self.state.entry(slug) is not None:
                return -1
            if slug in seen:
                self.problem(f"entry {slug}: its parents lead back to it.")
                return 0
            found = 1 + max([depth(p, (*seen, slug)) for p in row.parents] or [-1])
            depths[slug] = found
            return found

        for row in self.doc.entry:
            self.entry(row, depth(row.slug))

    def entry(self, row: EntryRow, level: int) -> None:
        where = f"entry {row.slug}"
        for parent in row.parents:
            if not self.has_entry(parent):
                self.missing("entry", parent, f"{where}'s parent")
        for name in [*row.stats, *row.tags]:
            if not self.has_stat(name):
                self.missing("stat", name, where)
        for name in row.tags:
            if self.stat_type(name) not in (None, "bool"):
                self.problem(f"{where}: {name} is not a tag (a bool stat).")
        existing = self.state.entry(row.slug)
        if existing is None:
            self.add("create", "entry", row.slug, ENTRY + max(level, 0), row.name)
            for name, value in row.stats.items():
                self.add("create", "value", f"{row.slug}: {name}", AFTER_ENTRIES, repr(value))
            for name in row.tags:
                self.add("create", "tag", f"{row.slug}: {name}", AFTER_ENTRIES)
            if row.description:
                self.add("create", "description", row.slug, AFTER_ENTRIES)
            return
        missing_kinds = sorted(set(row.kinds) - set(existing.kinds))
        if missing_kinds:
            self.plan.notes.append(
                f"{where}: is not {', '.join(missing_kinds)} here; kinds are not changed."
            )
        have = {self.state.slug_of(p) for p in existing.parent_ids}
        for parent in row.parents:
            if parent not in have:
                self.add("change", "parents", row.slug, AFTER_ENTRIES, f"+ {parent}", parent=parent)
        for name, value in row.stats.items():
            stat = self.state.stats.get(name)
            if (
                stat is None
                or stat.id not in existing.values
                or not same(existing.values[stat.id], value)
            ):
                self.add("change", "value", f"{row.slug}: {name}", AFTER_ENTRIES, repr(value))
        for name in row.tags:
            stat = self.state.stats.get(name)
            if stat is None or existing.values.get(stat.id) is not True:
                self.add("create", "tag", f"{row.slug}: {name}", AFTER_ENTRIES)
        if row.description:
            held = existing.description()
            if held is None:
                self.add("create", "description", row.slug, AFTER_ENTRIES)
            elif description_text(held).strip() != row.description.strip():
                self.plan.notes.append(
                    f"{where}: its description differs here; apply does not rewrite a description."
                )

    def attach(self) -> None:
        for row in self.doc.attach:
            where = f"attach {row.entry} to {row.parent}"
            if not self.has_entry(row.entry):
                self.missing("entry", row.entry, where)
                continue
            if not self.has_entry(row.parent):
                self.missing("entry", row.parent, where)
                continue
            existing = self.state.entry(row.entry)
            parent = self.state.entry(row.parent)
            if existing is None or parent is None or parent.id not in existing.parent_ids:
                self.add("create", "attach", f"{row.entry}: {row.parent}", AFTER_ENTRIES)

    def prune(self) -> None:
        row = self.doc.system
        if row is None:
            self.problem(
                "--prune removes what a system's document no longer names; this document has no "
                "[system], and the neutral rows of a library are not told apart from its own."
            )
            return
        system = self.state.systems.get(row.slug)
        if system is None:
            return
        groups = [g for g in self.state.groups.values() if g.system_id == system.id]
        named_groups = set(self.doc_groups)
        named_stats = set(self.doc_stats)
        group_ids = {g.id for g in groups}
        for stat in self.state.stats.values():
            if stat.stat_group_id in group_ids and stat.name not in named_stats:
                self.add("remove", "stat", stat.name, REMOVE + 950)
        for group in groups:
            if group.name not in named_groups:
                self.add("remove", "group", group.name, REMOVE + 951)
        if system.root_entry_id is None:
            return
        children = self.state.children()
        under = self.state.descendants(system.root_entry_id)
        going = {
            e
            for e in under
            if (entry := self.state.entries.get(e)) is not None
            and entry.slug not in self.doc_entries
            and e != system.root_entry_id
            and is_vocabulary_entry(entry, children)
        }
        for entry_id in going:
            staying = [c for c in children.get(entry_id, []) if c not in going]
            if staying:
                entry = self.state.entries[entry_id]
                names = ", ".join(sorted(self.state.entries[c].name for c in staying)[:3])
                self.problem(
                    f"--prune: {entry.slug or entry.name} would go, but {names} inherit from it."
                )
        for entry_id in sorted(going, key=lambda e: -_depth(self.state, e)):
            entry = self.state.entries[entry_id]
            self.add(
                "remove",
                "entry",
                entry.slug or str(entry.id),
                REMOVE + 900 - _depth(self.state, entry_id),
            )


def _depth(state: LibraryState, entry_id: UUID, seen: frozenset[UUID] = frozenset()) -> int:
    entry = state.entries.get(entry_id)
    if entry is None or not entry.parent_ids or entry_id in seen:
        return 0
    return 1 + max(_depth(state, p, seen | {entry_id}) for p in entry.parent_ids)


def _value(current: Any) -> Any:
    return current.value if hasattr(current, "value") else current


def make_plan(doc: Document, state: LibraryState, *, prune: bool = False) -> Plan:
    planner = _Planner(doc, state, prune)
    planner.system()
    planner.roles_held()
    for group in doc.group:
        planner.group(group)
    for stat in doc.stat:
        planner.stat(stat)
    planner.entries()
    planner.attach()
    if prune:
        planner.prune()
    return planner.plan
