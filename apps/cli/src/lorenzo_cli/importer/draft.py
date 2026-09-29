"""From one MPMB entry to what Lorenzo would hold for it (RFC 0025 §2, R5, ADR 0144): its name,
its parents, its stats, its description, and everything that needs a person to decide.

A draft is a pure function of the entry and the mapping. It reads nothing from a tenant, so a plan
is reproducible, and it never guesses: a value with no row, or a price it can't read, is an
`Issue` that holds the item back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lorenzo_cli.importer.mapping import Mapping, Row
from lorenzo_cli.importer.transforms import Context, Effect, Issue, StatValue, apply_rule
from lorenzo_cli.seed import SeedSpec

MELEE_OR_RANGED = frozenset({"melee-weapon", "ranged-weapon"})


@dataclass(frozen=True)
class NewCategory:
    """A category a map row mints under an axis root (`create-under`)."""

    slug: str
    name: str
    parent: str
    axis: str


@dataclass
class ItemDraft:
    list_name: str
    key: str
    file: str
    namespace: str
    name: str | None = None
    parents: list[str] = field(default_factory=list)
    stats: dict[str, StatValue] = field(default_factory=dict)
    stat_types: dict[str, str] = field(default_factory=dict)
    stat_groups: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    categories: list[NewCategory] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    skip_reason: str | None = None
    uncategorised: bool = False
    pack_items: list[Any] | None = None


class Ancestry:
    """Which taxonomy slugs are ancestors of which, so a parent that another parent already
    implies (`weapon`, when `melee-weapon` is there) can be dropped."""

    def __init__(self, seed: SeedSpec) -> None:
        self._parents = {node.slug: list(node.parents) for node in seed.nodes}

    def add(self, slug: str, parent: str) -> None:
        self._parents[slug] = [parent]

    def ancestors(self, slug: str) -> set[str]:
        found: set[str] = set()
        stack = list(self._parents.get(slug, []))
        while stack:
            parent = stack.pop()
            if parent not in found:
                found.add(parent)
                stack.extend(self._parents.get(parent, []))
        return found

    def reduce(self, parents: set[str]) -> list[str]:
        implied = set().union(*(self.ancestors(p) for p in parents)) if parents else set()
        return sorted(parents - implied)


def _suggestion(list_name: str, attribute: str, value: Any) -> str:
    key = str(value).strip().lower().replace('"', '\\"')
    return (
        f"[classify.{list_name}.{attribute}]\n"
        f'"{key}" = "attach-form-only"   # or ["parent-slug"], "skip", "fail", or\n'
        f'# {{ disposition = "create-under", axis = "...", slug = "hb-...", name = "..." }}'
    )


def _classify(
    list_name: str, entry: dict[str, Any], mapping: Mapping, draft: ItemDraft
) -> tuple[set[str], bool, bool]:
    """Parents from the classification attributes; whether the list's form is replaced; and whether
    a row explicitly settled the reach (weapons)."""
    parents: set[str] = set()
    replace_form = False
    explicit_reach = False
    roots = mapping.lists[list_name].roots if list_name in mapping.lists else {}
    for attribute, rule in mapping.attributes.get(list_name, {}).items():
        if rule.transform != "classify" or entry.get(attribute) in (None, ""):
            continue
        raw = entry[attribute]
        rows = mapping.classify[list_name][attribute]
        row: Row | None = rows.get(str(raw).strip().lower()) or rows.get("*")
        if row is None:
            draft.issues.append(
                Issue(
                    "value",
                    attribute,
                    repr(raw),
                    f"the map has no row for this {list_name} {attribute}",
                    _suggestion(list_name, attribute, raw),
                )
            )
            continue
        if attribute == "list":
            explicit_reach = True
        if row.disposition == "skip":
            # The first reason stands: `type` says Cantrip before `list` says spell.
            draft.skip_reason = draft.skip_reason or (
                f"{attribute} is {raw!r}, which the map says isn't an item"
            )
        elif row.disposition == "fail":
            draft.issues.append(
                Issue("fail", attribute, repr(raw), "the map says to refuse this value")
            )
        elif row.disposition == "attach-form-only":
            draft.uncategorised = True
        elif row.disposition == "create-under":
            assert row.axis and row.slug and row.name
            draft.categories.append(NewCategory(row.slug, row.name, roots[row.axis], row.axis))
            parents.add(row.slug)
        else:
            parents.update(row.parents)
            replace_form = replace_form or row.replace_form
    return parents, replace_form, explicit_reach


def draft_item(
    list_name: str,
    key: str,
    entry: dict[str, Any],
    file: str,
    mapping: Mapping,
    ancestry: Ancestry,
) -> ItemDraft:
    draft = ItemDraft(list_name, key, file, mapping.namespace_for(file))
    context = Context(list_name, mapping.currencies, entry)
    rules = mapping.attributes.get(list_name, {})

    parents: set[str] = set()
    for attribute, rule in rules.items():  # the map's order, so "the last name wins" is stable
        if attribute not in entry:
            continue
        effect: Effect = apply_rule(rule, attribute, entry[attribute], context)
        draft.name = effect.name or draft.name
        draft.description = effect.description or draft.description
        for stat, value in effect.stats.items():
            draft.stats.setdefault(stat, value)  # first_of and friends: the first to say wins
        draft.stat_types.update(effect.stat_types)
        draft.stat_groups.update(effect.stat_groups)
        parents |= effect.parents
        draft.notes.extend(effect.notes)
        draft.issues.extend(effect.issues)
        if effect.pack_items is not None:
            draft.pack_items = effect.pack_items
    draft.unmapped = [attribute for attribute in entry if attribute not in rules]

    if draft.name is None and not any(i.kind == "name" for i in draft.issues):
        draft.issues.append(Issue("name", "name", "", "the entry has no name to give the item"))

    classified, replace_form, explicit_reach = _classify(list_name, entry, mapping, draft)
    parents |= classified
    lowered = (draft.name or "").lower()
    for name_rule in mapping.name_rules:
        if name_rule.in_list == list_name and any(
            lowered.startswith(s) for s in name_rule.starts_with
        ):
            parents.update(name_rule.parents)
            break

    spec = mapping.lists.get(list_name)
    needs_reach = spec is not None and spec.reach_required and not (parents & MELEE_OR_RANGED)
    if needs_reach and not explicit_reach and draft.skip_reason is None:
        draft.issues.append(
            Issue(
                "reach",
                "list",
                repr(entry.get("list")),
                "can't tell whether it is melee or ranged: no `list`, and no reach in the range",
                f"[classify.{list_name}.list]\n"
                '"..." = ["melee-weapon"]   # or ["ranged-weapon"], or []',
            )
        )
    if spec is not None and not replace_form:
        parents.update(spec.form)
    for category in draft.categories:
        ancestry.add(category.slug, category.parent)
    draft.parents = ancestry.reduce(parents)
    return draft
