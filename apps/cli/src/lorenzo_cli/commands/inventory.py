"""`lorenzo import inventory` and `lorenzo export inventory` (ADR 0193, 0226, 0232)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.text import Text
from rich.tree import Tree

from lorenzo_cli import console
from lorenzo_cli.commands.common import ItemTenant
from lorenzo_cli.inventory import preprocess as inventory_preprocess
from lorenzo_cli.inventory.apply import apply as apply_inventory
from lorenzo_cli.inventory.apply import total as inventory_total
from lorenzo_cli.inventory.export import export_inventory
from lorenzo_cli.inventory.format import parse as parse_inventory
from lorenzo_cli.inventory.format import render_json, render_markdown
from lorenzo_cli.inventory.plan import Plan, Step, build_plan
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _out,
    _reporting_errors,
    may_write,
)
from lorenzo_cli.self_service import (
    resolve_owner,
)
from lorenzo_cli.tenants import (
    resolve_tenant,
)

app = typer.Typer(
    help="Bring a character's inventory in from a LorenzoLedger file, or write it out as one.",
    no_args_is_help=True,
)
inventory_app = app


def _inventory_summary(plan: Plan) -> None:
    makes = plan.makes
    by_how: dict[str, int] = {}
    for step in makes:
        by_how[step.match.via] = by_how.get(step.match.via, 0) + 1
    matched = len(makes) - len(plan.placeholders)
    _out.print(f"For {plan.owner_name} in {plan.tenant.slug}:", highlight=False)
    _out.print(f"  {len(makes)} to make, {matched} matched to an item", highlight=False)
    for how, label in (
        ("id", "by id"),
        ("slug", "by slug"),
        ("title", "by title"),
        ("spelling", "by another spelling"),
    ):
        if by_how.get(how):
            _out.print(f"    {by_how[how]} {label}", highlight=False)
    if plan.placeholders:
        _out.print(
            f"  {len(plan.placeholders)} unsorted, for your GM to match to an item:",
            highlight=False,
        )
        for step in plan.placeholders[:25]:
            _out.print(f"    {step.line.name}", highlight=False)
        if len(plan.placeholders) > 25:
            _out.print(f"    … and {len(plan.placeholders) - 25} more", highlight=False)
    if plan.moves:
        _out.print(
            f"  {len(plan.moves)} existing to move to where the file puts them", highlight=False
        )
    if plan.replace:
        _out.print(
            f"  {len(plan.deleting)} to delete first: everything {plan.owner_name} owns now"
            if plan.deleting
            else f"  nothing to delete: {plan.owner_name} owns nothing yet",
            highlight=False,
            style="bold" if plan.deleting else None,
        )
        if plan.keeping:
            _out.print(
                f"  {len(plan.keeping)} left alone, since they are tied up with what is someone "
                "else's:",
                highlight=False,
            )
            for kept in plan.keeping[:25]:
                _out.print(f"    {kept.name}: {kept.why}", highlight=False)
            if len(plan.keeping) > 25:
                _out.print(f"    … and {len(plan.keeping) - 25} more", highlight=False)


def _inventory_tree(plan: Plan) -> Tree:
    """What an import would make, as the nesting the file asks for, each line saying how it was
    matched (ADR 0232)."""
    root = Tree(Text(f"{plan.owner_name} in {plan.tenant.slug}", style="bold"))
    shown = {step.section for step in plan.steps}  # an empty section is left out
    sections = {
        key: root.add(heading)
        for key, heading in (("equipped", "Equipped"), ("not_carried", "Not carried"))
        if key in shown
    }
    nodes: dict[int, Tree] = {}

    def label(step: Step) -> Text:
        line, how = step.line, step.match
        text = Text(f"{line.quantity} x {line.name}" if line.quantity > 1 else line.name)
        if how.via == "placeholder":
            text.append("  unsorted", style="yellow")
        elif how.via == "instance":
            text.append("  moves the one it names", style="dim")
        elif how.item is not None:
            text.append(f"  {how.via}: {how.item.title}", style="dim")
        return text

    for step in plan.steps:  # a container comes before what is in it
        parent = nodes[id(step.parent)] if step.parent is not None else sections[step.section]
        nodes[id(step)] = parent.add(label(step))
    return root


@inventory_app.command("import")
def inventory_import(
    ctx: typer.Context,
    file: Annotated[
        Path, typer.Argument(help="The ledger file (Markdown or JSON), or - for stdin.")
    ],
    tenant: ItemTenant,
    owner: Annotated[
        str | None,
        typer.Option(
            "--owner", help="The character (id or name); the file's owner: line otherwise."
        ),
    ] = None,
    add: Annotated[
        bool,
        typer.Option(
            "--add",
            help="For a character who already has things: add, and move what the file names.",
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Say what would be made, and make nothing.")
    ] = False,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help="Delete what the character owns first, then make what the file lists.",
        ),
    ] = False,
    backup: Annotated[
        Path | None,
        typer.Option(
            "--backup", help="With --replace: first write what is there to this file, as a ledger."
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    spellings: Annotated[
        Path | None,
        typer.Option(
            "--preprocess", help="A table of other spellings (TOML), added to the built-in one."
        ),
    ] = None,
) -> None:
    """Make the things a file lists, for a character, or for any being a GM may list.

    Each line is matched to an item by id, slug, title or a known other spelling, and what matches
    nothing becomes an unsorted item your GM can match later. Nothing is made if any line cannot be
    made as written; with --dry-run nothing is made at all, and the plan is shown as a tree.

    --replace starts the being's inventory over: what it owns is deleted, then the file's things
    are made. The whole file is checked before anything is deleted.
    """
    if add and replace:
        raise typer.BadParameter("--add and --replace are alternatives: choose one.")
    if backup is not None and not replace:
        raise typer.BadParameter("--backup goes with --replace.")
    runtime: Runtime = ctx.obj
    text = runtime.stdin.read() if str(file) == "-" else file.read_text("utf-8")
    inventory = parse_inventory(text)
    table = inventory_preprocess.load(spellings)
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        plan = build_plan(
            client, target, inventory, owner=owner, add=add, table=table, replace=replace
        )
        for remark in plan.warnings:
            _err.print(f"[yellow]⚠ {remark}[/yellow]", highlight=False)
        if plan.problems:
            for remark in plan.problems:
                _err.print(f"[red]✗ {remark}[/red]", highlight=False)
            raise typer.Exit(1)
        _inventory_summary(plan)
        if dry_run:
            _out.print(_inventory_tree(plan))
            return
        if not plan.steps and not plan.deleting:
            return
        question = (
            f"Delete {len(plan.deleting)} and make {len(plan.makes)}?"
            if plan.replace
            else "Make these?"
        )
        may_write(runtime, yes=yes, question=question)
        if backup is not None and plan.deleting:
            saved = export_inventory(client, target.id, plan.owner_id, plan.owner_name, target.slug)
            text = render_json(saved) if backup.suffix == ".json" else render_markdown(saved)
            backup.write_text(text, encoding="utf-8")
            _err.print(f"Saved what {plan.owner_name} has now to {backup}.", highlight=False)
        with console.counting("Starting", inventory_total(plan)) as steps:
            done = apply_inventory(client, plan, before=steps.describe, after=steps.advance)
    if done.stopped:
        _err.print(
            f"[red]✗ Stopped before making anything: {len(done.failed)} could not be deleted.[/red]"
            " Run the command again to delete the rest and then make.",
            highlight=False,
        )
    else:
        _out.print(
            (f"Deleted {done.deleted}, made" if plan.replace else "Made")
            + f" {done.made} ({done.placeholders} unsorted)"
            + (f", moved {done.moved}" if done.moved else "")
            + ".",
            highlight=False,
        )
    for remark in done.failed:
        _err.print(f"[red]✗ {remark}[/red]", highlight=False)
    if done.failed:
        raise typer.Exit(1)


@inventory_app.command("export")
def inventory_export(
    ctx: typer.Context,
    tenant: ItemTenant,
    owner: Annotated[
        str | None,
        typer.Option(
            "--owner", help="The character (id or name); your only one when you leave it out."
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Write the JSON form.")] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write to this file, not the terminal.")
    ] = None,
) -> None:
    """Write a character's inventory as a LorenzoLedger: what they own, where, what is noted."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        owner_id, owner_name = resolve_owner(client, target.id, owner)
        inventory = export_inventory(client, target.id, owner_id, owner_name, target.slug)
    text = render_json(inventory) if as_json else render_markdown(inventory)
    if output is None:
        typer.echo(text, nl=False)
        return
    output.write_text(text, encoding="utf-8")
    _out.print(f"Wrote {output}.", highlight=False)


# Register the vocabulary and read surfaces separately from the import workflows.
