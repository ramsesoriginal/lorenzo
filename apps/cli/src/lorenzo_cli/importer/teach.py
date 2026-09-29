"""Teaching the map a value it hasn't met (RFC 0025 R5, ADR 0144), when a person is there to ask.

Each unknown value is asked about once, however many items carry it. What is answered applies in
the same run (as extra rows on top of the map that was read) and is kept as rows to save. The
importer never edits a map file itself: it offers, after a successful import, to append them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from lorenzo_cli.importer.mapping import Mapping
from lorenzo_cli.importer.plan import ImportPlan

# What can be answered. Each is a row of the map (see builtin_map.toml).
CHOICES = (
    "[a]ttach to the form only, [m]ap to parents, [c]reate a category, [s]kip, [f]ail, [l]eave"
)


@dataclass(frozen=True)
class Unknown:
    list_name: str
    attribute: str
    # As the file says it, and the key a row would use (lower-cased).
    shown: str
    key: str
    items: tuple[str, ...]


def unknown_values(plan: ImportPlan) -> list[Unknown]:
    """The classification values no row settles, grouped so each is asked about once."""
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    shown: dict[tuple[str, str, str], str] = {}
    for item in plan.items:
        if item.status != "held":
            continue
        for issue in item.draft.issues:
            if issue.kind != "value":
                continue
            raw = issue.value.strip("'\"")
            key = (item.draft.list_name, issue.attribute, raw.lower())
            grouped[key].append(item.draft.name or item.draft.key)
            shown[key] = raw
    return [
        Unknown(list_name, attribute, shown[(list_name, attribute, key)], key, tuple(names))
        for (list_name, attribute, key), names in sorted(grouped.items())
    ]


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ask(
    unknown: Unknown,
    mapping: Mapping,
    prompt: Callable[[str, str], str],
    say: Callable[[str], None],
) -> str | None:
    """One row for the map, or None to leave the value for review. `prompt(text, default)`."""
    sample = ", ".join(unknown.items[:3]) + (" ..." if len(unknown.items) > 3 else "")
    say(
        f"\n{unknown.list_name}.{unknown.attribute} = {unknown.shown!r} "
        f"({len(unknown.items)} item(s): {sample})"
    )
    say(f"  {CHOICES}")
    choice = prompt("What should it be?", "l").strip().lower()[:1]
    key = _quote(unknown.key)
    if choice == "a":
        return f'{key} = "attach-form-only"'
    if choice == "s":
        return f'{key} = "skip"'
    if choice == "f":
        return f'{key} = "fail"'
    if choice == "m":
        answer = prompt("Parent slugs, separated by commas", "")
        parents = [p.strip() for p in answer.split(",") if p.strip()]
        return f"{key} = [{', '.join(_quote(p) for p in parents)}]"
    if choice == "c":
        roots = mapping.lists[unknown.list_name].roots
        axes = ", ".join(a for a in roots if a != "form") or "form"
        axis = prompt(
            f"Under which axis ({axes})", next(iter(a for a in roots if a != "form"), "form")
        )
        slug = prompt("Slug for the new category (with a prefix that says whose it is, hb-...)", "")
        name = prompt("Its name", unknown.shown.title())
        return (
            f'{key} = {{ disposition = "create-under", axis = {_quote(axis)}, '
            f"slug = {_quote(slug)}, name = {_quote(name)} }}"
        )
    return None


def rows_toml(rows: dict[tuple[str, str], list[str]]) -> str:
    """The answers as TOML, to lay over a map (or to save)."""
    lines: list[str] = []
    for (list_name, attribute), section in sorted(rows.items()):
        lines.append(f"[classify.{list_name}.{attribute}]")
        lines.extend(section)
        lines.append("")
    return "\n".join(lines)
