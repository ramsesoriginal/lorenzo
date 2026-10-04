"""Showing what the JavaScript host read from a set of files (`lorenzo inspect`)."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from lorenzo_cli.evalworker import STANDARD_LISTS, EvalResult
from lorenzo_cli.importer.plan import ImportPlan
from lorenzo_cli.seed import SeedPlan, SeedSpec, UnseedPlan, UnseedResult
from lorenzo_cli.seed.spec import NodeSpec, RecipeSpec


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


def unseed_plan_json(plan: UnseedPlan) -> dict[str, object]:
    return {
        "tenant": {
            "id": str(plan.tenant.id),
            "slug": plan.tenant.slug,
            "kind": plan.tenant.kind.value,
            "published": plan.tenant.published_at is not None,
        },
        "seed_version": plan.spec_version,
        "layers": list(plan.layers),
        "targets": [
            {"kind": t.kind, "name": t.name, "layer": t.layer, "detail": t.detail}
            for t in plan.targets
        ],
        "problems": plan.problems,
    }


def unseed_result_json(result: UnseedResult) -> dict[str, object]:
    return {
        "deleted": [{"kind": t.kind, "name": t.name, "layer": t.layer} for t in result.deleted],
        "kept": [{"kind": k.kind, "name": k.name, "reason": k.reason} for k in result.kept],
    }


def unseed_counts(plan: UnseedPlan) -> str:
    """ "28 categories, 22 stat definitions and 0 stat groups", with "6 attachments, " in front
    where the plan takes some out."""
    counts = (
        f"{len(plan.of('node'))} categories, {len(plan.of('definition'))} stat definitions and "
        f"{len(plan.of('group'))} stat groups"
    )
    attachments = plan.of("attachment")
    return f"{len(attachments)} attachments, {counts}" if attachments else counts


def print_unseed_plan(console: Console, plan: UnseedPlan) -> None:
    tenant = plan.tenant
    published = " (published: subscribers will see these changes)" if tenant.published_at else ""
    console.print(
        f"Tenant [bold]{tenant.slug}[/bold], a {tenant.kind.value} tenant{published}. "
        f"Layers: {', '.join(plan.layers)}. Seed version {plan.spec_version}."
    )
    if plan.targets:
        table = Table("what", "name", "layer", "", title="To remove", title_justify="left")
        for target in plan.targets:
            table.add_row(target.kind, target.name, target.layer, target.detail)
        console.print(table)
    console.print(f"To remove: {unseed_counts(plan)}.")
    for problem in plan.problems:
        console.print(f"[red]{problem}[/red]")


def print_unseed_result(console: Console, result: UnseedResult) -> None:
    console.print(
        f"Removed {len(result.deleted)}"
        + (f"; kept {len(result.kept)}." if result.kept else ". Run it again to check.")
    )
    for kept in result.kept:
        console.print(f"[red]Kept {kept.kind} {kept.name}: {kept.reason}[/red]")


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
        ("to retitle (description titled “Description”)", plan.retitle_count),
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


def _recipe_text(recipe: RecipeSpec) -> str:
    inside = recipe.source if recipe.kind == "contents" else ", ".join(recipe.terms)
    return f"{recipe.kind}({inside})"


def seed_list_json(spec: SeedSpec, layers: tuple[str, ...]) -> dict[str, object]:
    """The built-in seed as plain data for `--json`, the layers asked for."""
    groups = {g.name: g for g in spec.groups}
    return {
        "seed_version": spec.version,
        "layers": {
            layer: {
                "stat_groups": [g.name for g in spec.groups if g.layer == layer],
                "stat_definitions": [
                    {
                        "name": d.name,
                        "stat_group": groups[d.group].name,
                        "value_type": d.value_type,
                    }
                    for d in spec.definitions
                    if d.layer == layer
                ],
                "categories": [
                    {
                        "slug": n.slug,
                        "name": n.name,
                        "parents": n.parents,
                        "tags": n.tags,
                        "stats": n.stats,
                        "description": n.description,
                    }
                    for n in spec.nodes
                    if n.layer == layer
                ],
                "attachments": [
                    {"child": a.child, "parent": a.parent}
                    for a in spec.attachments
                    if a.layer == layer
                ],
                "recipes": [
                    {"node": r.node, "stat": r.stat, "kind": r.kind, "of": _recipe_of(r)}
                    for r in spec.recipes
                    if r.layer == layer
                ],
            }
            for layer in layers
        },
    }


def _recipe_of(recipe: RecipeSpec) -> list[str]:
    return [recipe.source] if recipe.source else list(recipe.terms)


def _category_tree(nodes: list[NodeSpec]) -> list[tuple[int, NodeSpec]]:
    """The layer's categories, each right after the first parent it has in the same layer, with its
    depth. A category's other parents are shown on its line."""
    slugs = {n.slug for n in nodes}
    children: dict[str | None, list[NodeSpec]] = {}
    for node in nodes:
        first = next((p for p in node.parents if p in slugs), None)
        children.setdefault(first, []).append(node)
    ordered: list[tuple[int, NodeSpec]] = []

    def walk(parent: str | None, depth: int) -> None:
        for child in children.get(parent, []):
            ordered.append((depth, child))
            walk(child.slug, depth + 1)

    walk(None, 0)
    return ordered


def _category_line(depth: int, node: NodeSpec) -> str:
    # Where the tree already shows the first same-layer parent, name only the rest.
    line = f"{'  ' * (depth + 1)}{node.slug}  {escape(node.name)}"
    shown = node.parents[0] if depth else None
    others = [p for p in node.parents if p != shown]
    if others:
        line += f"  [dim]under {', '.join(others)}[/dim]"
    sets = [*node.tags, *(f"{stat} {value}" for stat, value in node.stats.items())]
    if sets:
        line += f"  [dim]sets {escape(', '.join(sets))}[/dim]"
    return line


def print_seed_list(console: Console, spec: SeedSpec, layers: tuple[str, ...]) -> None:
    console.print(f"The built-in seed, version {spec.version}.")
    for layer in layers:
        groups = [g for g in spec.groups if g.layer == layer]
        definitions = [d for d in spec.definitions if d.layer == layer]
        nodes = [n for n in spec.nodes if n.layer == layer]
        attachments = [a for a in spec.attachments if a.layer == layer]
        recipes = [r for r in spec.recipes if r.layer == layer]
        described = sum(1 for n in nodes if n.description)
        console.print(
            f"\n[bold]{layer}[/bold]: {len(groups)} stat groups, {len(definitions)} stat "
            f"definitions, {len(nodes)} categories ({described} with a description), "
            f"{len(attachments)} attachments, {len(recipes)} recipes"
        )
        if groups:
            console.print("Stat groups: " + ", ".join(g.name for g in groups), highlight=False)
        if definitions:
            table = Table("name", "group", "type", title="Stat definitions", title_justify="left")
            for d in definitions:
                table.add_row(d.name, d.group, d.value_type)
            console.print(table)
        if nodes:
            console.print("Categories:")
            for depth, node in _category_tree(nodes):
                console.print(_category_line(depth, node), highlight=False, soft_wrap=True)
        if attachments:
            table = Table("category", "gets the parent", title="Attachments", title_justify="left")
            for a in attachments:
                table.add_row(a.child, a.parent)
            console.print(table)
        if recipes:
            table = Table("on", "stat", "computed as", title="Recipes", title_justify="left")
            for r in recipes:
                table.add_row(r.node, r.stat, _recipe_text(r))
            console.print(table)
