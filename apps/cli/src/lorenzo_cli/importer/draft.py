"""From one MPMB entry to what Lorenzo would hold for it (RFC 0025 §2, R5, ADR 0144): its name,
its parents, its stats, its description, and everything that needs a person to decide.

A draft is a pure function of the entry and the mapping. It reads nothing from a tenant, so a plan
is reproducible, and it never guesses: a value with no row, or a price it can't read, is an
`Issue` that holds the item back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from lorenzo_cli.importer.mapping import DEFAULT_SYSTEM_LABEL, Mapping, NameRule, Part, Row
from lorenzo_cli.importer.packs import PackLine, Resolution, Unresolved
from lorenzo_cli.importer.parts import Parts, issue_part, part_of_axis
from lorenzo_cli.importer.transforms import (
    Context,
    Effect,
    InfoDraft,
    Issue,
    StatValue,
    apply_rule,
)
from lorenzo_cli.seed import SeedSpec, load_builtin

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
    # How many units the entry stands for (a coil of 50 feet of rope), or 1: a pack counts in units.
    bundle: int = 1
    # Every name the item goes by (a pack's contents are found by them).
    names: list[str] = field(default_factory=list)
    # A pack's contents once linked, and the entries nothing could be linked to.
    pack_lines: list[PackLine] = field(default_factory=list)
    pack_unresolved: list[Unresolved] = field(default_factory=list)
    # What each of a pack's entries refers to, decided before slugs exist.
    pack_resolution: Resolution | None = None
    # The pack an item was made for, when the source has no entry of its own for it.
    made_for: str | None = None
    # Entries of their own to write on the item (other names, special rules...), by type.
    information: list[InfoDraft] = field(default_factory=list)
    # ADR 0182. The namespaces of the neutral item and of the system's prototype, and the label the
    # prototype's name carries; the seed decides the part of its own stats and categories, so these
    # are only what the map's rows said for the rest.
    neutral_namespace: str = ""
    system_namespace: str = ""
    system_label: str = DEFAULT_SYSTEM_LABEL
    stat_parts: dict[str, Part] = field(default_factory=dict)
    parent_parts: dict[str, Part] = field(default_factory=dict)
    description_part: Part = "neutral"
    aliases_part: Part = "neutral"
    # The neutral item's name, in the system pass, where `name` is the prototype's.
    neutral_name: str | None = None


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


_DEFAULT_PARTS: list[Parts] = []


def default_parts() -> Parts:
    """The parts of the built-in seed, read once."""
    if not _DEFAULT_PARTS:
        _DEFAULT_PARTS.append(Parts(load_builtin()))
    return _DEFAULT_PARTS[0]


def part_view(draft: ItemDraft, part: Part, parts: Parts) -> ItemDraft:
    """One half of a draft (ADR 0182): what the neutral pass or the system pass writes of the item.

    A stat has the part of its definition's layer, a parent the part of its category's, a minted
    category the part of its axis; the rest is what a row said. The system's view is the
    prototype: named for the item and the system, in the system's namespace, and with nothing to
    write at all where nothing of the item is the system's."""

    def stat_part(stat: str) -> Part:
        return parts.stat(stat) or draft.stat_parts.get(stat, "neutral")

    minted = {c.slug: part_of_axis(c.axis) for c in draft.categories}

    def parent_part(slug: str) -> Part:
        return parts.node(slug) or minted.get(slug) or draft.parent_parts.get(slug, "neutral")

    stats = {s: v for s, v in draft.stats.items() if stat_part(s) == part}
    view = replace(
        draft,
        stats=stats,
        stat_types={s: t for s, t in draft.stat_types.items() if stat_part(s) == part},
        stat_groups={s: g for s, g in draft.stat_groups.items() if stat_part(s) == part},
        parents=[p for p in draft.parents if parent_part(p) == part],
        categories=[c for c in draft.categories if part_of_axis(c.axis) == part],
        description=draft.description if draft.description_part == part else None,
        information=[i for i in draft.information if i.part == part],
        issues=[i for i in draft.issues if i.part in (None, part)],
        uncategorised=draft.uncategorised and part == "neutral",
    )
    if part == "neutral":
        return view
    view.pack_items, view.pack_lines = None, []
    view.pack_unresolved, view.pack_resolution = [], None
    view.neutral_name = draft.name
    view.name = f"{draft.name} ({draft.system_label})" if draft.name else None
    view.namespace = draft.system_namespace
    if not (view.stats or view.parents or view.description or view.information or view.categories):
        view.skip_reason = draft.skip_reason or "nothing of it is the system's"
    return view


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
    for attribute, attribute_rules in mapping.attributes.get(list_name, {}).items():
        classifies = any(r.transform == "classify" for r in attribute_rules)
        if not classifies or entry.get(attribute) in (None, ""):
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
            if row.part:
                draft.parent_parts.update(dict.fromkeys(row.parents, row.part))
    return parents, replace_form, explicit_reach


def draft_item(
    list_name: str,
    key: str,
    entry: dict[str, Any],
    file: str,
    mapping: Mapping,
    ancestry: Ancestry,
    parts: Parts | None = None,
) -> ItemDraft:
    parts = parts or default_parts()
    namespace = mapping.namespace_for(file)
    draft = ItemDraft(
        list_name,
        key,
        file,
        namespace,
        neutral_namespace=namespace,
        system_namespace=mapping.system_namespace_for(file),
        system_label=mapping.system_label,
    )
    context = Context(list_name, mapping.currencies, entry)
    rules = mapping.attributes.get(list_name, {})

    parents: set[str] = set()
    aliases: list[str] = []
    # The map's order, so "the last name wins" is stable.
    for attribute, attribute_rules in rules.items():
        if attribute not in entry:
            continue
        for rule in attribute_rules:
            effect: Effect = apply_rule(rule, attribute, entry[attribute], context)
            draft.name = effect.name or draft.name
            if effect.description:
                draft.description = effect.description
                draft.description_part = rule.part or "neutral"
            for stat, value in effect.stats.items():
                if stat not in draft.stats and rule.part:
                    draft.stat_parts[stat] = rule.part
                draft.stats.setdefault(stat, value)  # first_of and friends: the first to say wins
            draft.stat_types.update(effect.stat_types)
            draft.stat_groups.update(effect.stat_groups)
            parents |= effect.parents
            if effect.aliases:
                aliases.extend(effect.aliases)
                draft.aliases_part = rule.part or "neutral"
            draft.information.extend(effect.information)
            draft.notes.extend(effect.notes)
            draft.issues.extend(
                replace(issue, part=issue_part(rule, issue, parts)) for issue in effect.issues
            )
            if effect.pack_items is not None:
                draft.pack_items = effect.pack_items
    draft.unmapped = [attribute for attribute in entry if attribute not in rules]

    if draft.name is None and not any(i.kind == "name" for i in draft.issues):
        draft.issues.append(Issue("name", "name", "", "the entry has no name to give the item"))
    amount = entry.get("amount")
    if isinstance(amount, int) and not isinstance(amount, bool) and amount > 1:
        draft.bundle = amount
    draft.names = sorted(
        {
            n
            for n in (entry.get("name"), entry.get("invName"), draft.name)
            if isinstance(n, str) and n.strip()
        }
    )
    alias_entry = _aliases_entry(draft, aliases)
    if alias_entry is not None:
        draft.information.append(alias_entry)
        draft.names = sorted({*draft.names, *aliases})

    classified, replace_form, explicit_reach = _classify(list_name, entry, mapping, draft)
    parents |= classified
    parents |= _text_rule_parents(list_name, entry, draft, mapping)

    spec = mapping.lists.get(list_name)
    reaches = parents | {a for p in parents for a in ancestry.ancestors(p)}
    needs_reach = spec is not None and spec.reach_required and not (reaches & MELEE_OR_RANGED)
    if needs_reach and not explicit_reach and draft.skip_reason is None:
        draft.issues.append(
            Issue(
                "reach",
                "list",
                repr(entry.get("list")),
                "can't tell whether it is melee or ranged: no `list`, and no reach in the range",
                f"[classify.{list_name}.list]\n"
                '"..." = ["melee-weapon"]   # or ["ranged-weapon"], or []',
                "neutral",  # reach is a form: the system's half doesn't need it
            )
        )
    if spec is not None and not replace_form:
        parents.update(spec.form)
    for category in draft.categories:
        ancestry.add(category.slug, category.parent)
    draft.parents = ancestry.reduce(parents)
    return draft


_WORD = re.compile(r"[a-z0-9][a-z0-9'-]*")


def _matches(rule: NameRule, text: str) -> bool:
    words = set(_WORD.findall(text))
    return (
        any(text.startswith(prefix) for prefix in rule.starts_with)
        or any(fragment in text for fragment in rule.contains)
        or any(word in words for word in rule.words)
    )


def _text_rule_parents(
    list_name: str, entry: dict[str, Any], draft: ItemDraft, mapping: Mapping
) -> set[str]:
    """Parents from what the name (or another text attribute) says. Every rule that matches
    applies, except that of the rules sharing a group only the first does."""
    parents: set[str] = set()
    used: set[str] = set()
    for rule in mapping.name_rules:
        if rule.in_list != list_name or (rule.group and rule.group in used):
            continue
        source = draft.name if rule.attribute == "name" else entry.get(rule.attribute)
        text = source.lower() if isinstance(source, str) else ""
        if text and _matches(rule, text):
            parents.update(rule.parents)
            if rule.part:
                draft.parent_parts.update(dict.fromkeys(rule.parents, rule.part))
            if rule.group:
                used.add(rule.group)
    return parents


def _aliases_entry(draft: ItemDraft, given: list[str]) -> InfoDraft | None:
    """One "Also known as" entry: the names the source gives, and the other names it uses for the
    item, without the one the item is called."""
    seen = {(draft.name or "").lower()}
    names: list[str] = []
    for name in [*given, *draft.names]:
        if name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return (
        InfoDraft("alias", "Also known as", "\n".join(names), draft.aliases_part) if names else None
    )
