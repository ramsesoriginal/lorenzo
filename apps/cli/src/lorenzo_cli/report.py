"""Showing what the JavaScript host read from a set of files (`lorenzo inspect`)."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.table import Table

from lorenzo_cli.evalworker import STANDARD_LISTS, EvalResult
from lorenzo_cli.importer.plan import ImportPlan
from lorenzo_cli.seed import SeedPlan


def print_evaluation(console: Console, result: EvalResult) -> None:
    files = Table("file", "role", "result", title="Files", title_justify="left")
    for file in result.files:
        status = "[green]ok[/green]" if file.status == "ok" else f"[red]{file.error}[/red]"
        files.add_row(file.name, file.role, status)
    console.print(files)

    lists = Table("list", "entries", "from", title="Lists", title_justify="left")
    for name in STANDARD_LISTS:
        origins = Counter(result.origins.get(name, {}).values())
        sources = ", ".join(f"{file or '?'} ({count})" for file, count in origins.most_common())
        lists.add_row(name, str(result.counts.get(name, 0)), sources)
    console.print(lists)

    others = {
        name: count for name, count in result.counts.items() if name not in STANDARD_LISTS and count
    }
    if others:
        console.print(
            "Read but not imported (RFC 0025 is standard items only): "
            + ", ".join(f"{name} {count}" for name, count in sorted(others.items()))
        )
    if result.stubs:
        console.print(
            "Names the sheet supplies that were stubbed: "
            + ", ".join(f"{s.name} ({s.calls})" for s in result.stubs)
        )
    if result.stubs_in_data:
        console.print(
            f"[yellow]{len(result.stubs_in_data)} value(s) came from a stubbed sheet call and "
            "are unknown; the first is "
            f"{result.stubs_in_data[0].path}.[/yellow]"
        )


def seed_plan_json(plan: SeedPlan) -> dict[str, object]:
    """The plan as plain data for `--json`: what a script would chain on."""
    return {
        "tenant": {
            "id": str(plan.tenant.id),
            "slug": plan.tenant.slug,
            "kind": plan.tenant.kind.value,
            "published": plan.tenant.published_at is not None,
        },
        "seed_version": plan.spec_version,
        "layers": list(plan.layers),
        "existing": plan.existing,
        "actions": [
            {"kind": a.kind, "name": a.name, "layer": a.layer, "detail": a.detail}
            for a in plan.actions
        ],
        "problems": plan.problems,
        "warnings": plan.warnings,
    }


def print_seed_plan(console: Console, plan: SeedPlan, *, applied: bool = False) -> None:
    tenant = plan.tenant
    published = " (published: subscribers will see these changes)" if tenant.published_at else ""
    console.print(
        f"Tenant [bold]{tenant.slug}[/bold], a {tenant.kind.value} tenant{published}. "
        f"Layers: {', '.join(plan.layers)}. Seed version {plan.spec_version}."
    )
    if plan.actions:
        table = Table(
            "what",
            "name",
            "layer",
            "",
            title="Done" if applied else "To create",
            title_justify="left",
        )
        for action in plan.actions:
            table.add_row(action.kind, action.name, action.layer, action.detail)
        console.print(table)
    console.print(f"Already there: {plan.existing}. To create: {len(plan.actions)}.")
    for warning in plan.warnings:
        console.print(f"[yellow]{warning}[/yellow]")
    for problem in plan.problems:
        console.print(f"[red]{problem}[/red]")


def import_exit_code(plan: ImportPlan, *, strict: bool, reconcile: bool) -> int:
    """0 nothing to do, 2 changes pending, 1 something unresolved (RFC 0025 R6)."""
    unexplained = plan.unmapped() or plan.pack_unresolved()
    if plan.problems or plan.held or plan.file_errors or (strict and unexplained):
        return 1
    if plan.pending or (reconcile and plan.reparent_count):
        return 2
    return 0


def print_import_plan(console: Console, plan: ImportPlan, *, strict: bool) -> None:
    tenant = plan.tenant
    published = " (published: subscribers will see these changes)" if tenant.published_at else ""
    console.print(
        f"Tenant [bold]{tenant.slug}[/bold], a {tenant.kind.value} tenant{published}. "
        f"Map: built-in {plan.loaded.builtin_version}"
        f"{', project ' + plan.loaded.user_map_sha256[:8] if plan.loaded.user_map_sha256 else ''}."
    )
    table = Table("what", "items", title="Plan", title_justify="left")
    for label, count in (
        ("to create", plan.count("create")),
        ("to finish (created, not complete)", plan.count("complete")),
        ("already there", plan.count("exists")),
        ("held for review", plan.count("held")),
        ("moved to another namespace", plan.count("moved")),
        ("not items (skipped)", plan.count("skipped")),
        ("would change parents (with --reconcile)", plan.reparent_count),
        ("new categories", len(plan.categories)),
        ("new stat definitions", len(plan.definitions)),
    ):
        if count:
            table.add_row(label, str(count))
    console.print(table)
    for line in plan.file_errors:
        console.print(f"[red]A file stopped part-way: {line}[/red]")
    for override in plan.overrides:
        console.print(
            f"{override['list']} {override['key']!r}: {override['by_file']} replaces "
            f"{override['replaced_file']}"
        )
    unlinked = plan.pack_unresolved()
    if unlinked:
        style = "red" if strict else "yellow"
        console.print(
            f"[{style}]In a pack but not a catalog item here (plain text in its contents): "
            + ", ".join(sorted({f"{m.name} ({i.draft.key})" for i, m in unlinked}))
            + f"[/{style}]"
        )
    unmapped = plan.unmapped()
    if unmapped:
        style = "red" if strict else "yellow"
        console.print(
            f"[{style}]Attributes no rule mentions: "
            + ", ".join(f"{a} ({lst}, {n})" for (lst, a), n in unmapped.items())
            + f"[/{style}]"
        )
    for problem in plan.problems:
        console.print(f"[red]{problem}[/red]")
    held: dict[tuple[str, str, str], int] = {}
    for item in plan.items:
        if item.status == "held":
            for issue in item.draft.issues:
                held_key = (item.draft.list_name, issue.attribute or issue.kind, issue.reason)
                held[held_key] = held.get(held_key, 0) + 1
    for (list_name, attribute, reason), count in sorted(held.items()):
        console.print(f"[red]{count} x {list_name}.{attribute}: {reason}[/red]")
