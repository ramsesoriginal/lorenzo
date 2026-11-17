"""`lorenzo plan`, `apply`, `export system|neutral` and `starter` (ADR 0484): a library document
planned against a library, applied to it, and written back from it."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.text import Text

from lorenzo_cli import console, starters
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.library import document as documents
from lorenzo_cli.library.document import Document, DocumentError
from lorenzo_cli.library.exporter import ExportError, chosen, export, to_toml
from lorenzo_cli.library.planner import Plan, make_plan
from lorenzo_cli.library.render import counts_line, plan_json, print_plan, print_result
from lorenzo_cli.library.state import LibraryState, read, read_formulas, read_prerequisites
from lorenzo_cli.library.writer import apply as write_plan
from lorenzo_cli.runtime import Runtime, _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant

app = typer.Typer(help="Plan or apply a library document.", no_args_is_help=True)
export_app = typer.Typer(help="Write a system or the neutral vocabulary as a document.")
starter_app = typer.Typer(help="The documents that ship with the CLI.", no_args_is_help=True)

FileArgument = Annotated[
    Path | None,
    typer.Argument(dir_okay=False, help="A library document (TOML). Or name a --starter."),
]
StarterOption = Annotated[
    str | None, typer.Option("--starter", help="A document that ships with the CLI, by name.")
]
PruneOption = Annotated[
    bool,
    typer.Option(
        "--prune",
        help="Also remove what the document's system no longer names (shown first; ADR 0484).",
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print the plan as one JSON document.")]


def _document(file: Path | None, starter: str | None) -> Document:
    if (file is None) == (starter is None):
        raise typer.BadParameter("Name a document file or a --starter, one of them.")
    try:
        return starters.load(starter) if starter is not None else documents.load(file)  # type: ignore[arg-type]
    except DocumentError as exc:
        raise SelfServiceError(str(exc)) from exc


def read_formulas_for(
    client: LorenzoClient, state: LibraryState, doc: Document, *, prune: bool
) -> None:
    """The formulas the plan compares: on the entries the document's formulas name, and, when
    pruning a system, on its vocabulary entries."""
    wanted = {e.id for f in doc.formula if (e := state.entry(f.on)) is not None}
    if prune and doc.system is not None and doc.system.slug in state.systems:
        wanted |= {e.id for e in chosen(state, doc.system.slug)}
    read_formulas(client, state, wanted)
    features = {
        e.id
        for row in doc.entry
        if row.prerequisites is not None and (e := state.entry(row.slug)) is not None
    }
    read_prerequisites(client, state, features)


def _planned(
    runtime: Runtime, tenant: str, doc: Document, *, prune: bool, writes: bool
) -> tuple[Plan, LibraryState]:
    with _client(runtime, writes=writes) as client:
        target = resolve_tenant(client, tenant)
        with console.waiting(f"Reading {target.slug}"):
            state = read(client, target)
            read_formulas_for(client, state, doc, prune=prune)
    return make_plan(doc, state, prune=prune), state


@app.command("plan")
def plan_command(
    ctx: typer.Context,
    tenant: TenantOption,
    file: FileArgument = None,
    starter: StarterOption = None,
    prune: PruneOption = False,
    as_json: JsonOption = False,
) -> None:
    """Work out what applying a document would do, and change nothing.

    Exit codes: 0 nothing to do, 2 changes pending, 1 something it cannot do.
    """
    with _reporting_errors():
        doc = _document(file, starter)
        plan, _ = _planned(ctx.obj, tenant, doc, prune=prune, writes=False)
    if as_json:
        console.emit(plan_json(plan))
    else:
        print_plan(plan)
    raise typer.Exit(plan.exit_code())


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    tenant: TenantOption,
    file: FileArgument = None,
    starter: StarterOption = None,
    prune: PruneOption = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan and write nothing (as `plan`).")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    as_json: JsonOption = False,
) -> None:
    """Apply a document: create what the library lacks and set what the document names.

    It never deletes, unless --prune; a second apply finds what the first made. Exit codes: 0 done
    or nothing to do, 2 not written (asked, declined, or --dry-run with changes), 1 refused or
    failed.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors():
        doc = _document(file, starter)
        with _client(runtime, writes=not dry_run) as client:
            target = resolve_tenant(client, tenant)
            with console.waiting(f"Reading {target.slug}"):
                state = read(client, target)
                read_formulas_for(client, state, doc, prune=prune)
            plan = make_plan(doc, state, prune=prune)
            if not as_json:
                print_plan(plan)
            if plan.problems or dry_run or not plan.actions:
                if as_json:
                    console.emit(plan_json(plan))
                raise typer.Exit(plan.exit_code())
            if not yes and as_json:
                console.emit(plan_json(plan))
            may_write(runtime, yes=yes, question=f"Apply {doc.name}: {counts_line(plan)}?")
            with console.counting("Writing", len(plan.actions)) as steps:
                result = write_plan(
                    client, plan, state, advance=steps.advance, describe=steps.describe
                )
    if as_json:
        console.emit(plan_json(plan, result))
    else:
        print_result(result)
        if result.done:
            console.notice(f"Check what it wrote: lorenzo check -t {plan.tenant.slug}")
    raise typer.Exit(1 if result.failed else 0)


def _export(ctx: typer.Context, tenant: str, system: str | None, output: Path | None) -> None:
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        with console.waiting(f"Reading {target.slug}"):
            state = read(client, target)
        try:
            entries = chosen(state, system)
            read_formulas(client, state, {e.id for e in entries})
            read_prerequisites(client, state, {e.id for e in entries if "feature" in e.kinds})
            text = to_toml(export(state, system))
        except ExportError as exc:
            raise SelfServiceError(str(exc)) from exc
    if output is None:
        console.out.file.write(text)
        return
    output.write_text(text, encoding="utf-8")
    console.notice(f"Wrote {output}.")


OutputOption = Annotated[
    Path | None, typer.Option("--output", "-o", dir_okay=False, help="Write it to this file.")
]


@export_app.command("system")
def export_system(
    ctx: typer.Context,
    system: Annotated[str, typer.Argument(help="The system's slug.")],
    tenant: TenantOption,
    output: OutputOption = None,
) -> None:
    """A system as a document: its groups and stats, and the entries under its root that others
    inherit from or that are features. `lorenzo export SLUG` is the same."""
    _export(ctx, tenant, system, output)


@export_app.command("neutral")
def export_neutral(ctx: typer.Context, tenant: TenantOption, output: OutputOption = None) -> None:
    """The neutral vocabulary as a document: the groups of no system, their stats, and the
    entries outside every system that others inherit from."""
    _export(ctx, tenant, None, output)


@starter_app.command("list")
def starter_list(
    as_json: Annotated[bool, typer.Option("--json", help="Print one JSON document.")] = False,
) -> None:
    """The documents that ship with the CLI. Needs no login."""
    found: list[dict[str, Any]] = []
    for name in starters.names():
        doc = starters.load(name)
        found.append(
            {
                "name": name,
                "system": doc.system.slug if doc.system else None,
                "requires": doc.requires,
                "stats": len(doc.stat),
                "entries": len(doc.entry),
            }
        )
    if as_json:
        console.emit({"starters": found})
        return
    if not found:
        console.out.print("No starters ship with this version.")
        return
    for row in found:
        system = f"system {row['system']}" if row["system"] else "neutral"
        needs = f", requires {', '.join(row['requires'])}" if row["requires"] else ""
        console.out.print(
            Text(f"{row['name']}  {system}: {row['stats']} stats, {row['entries']} entries{needs}")
        )


@starter_app.command("show")
def starter_show(name: Annotated[str, typer.Argument(help="The starter's name.")]) -> None:
    """Print a starter as it ships, to read or to save and change. Needs no login."""
    try:
        console.out.file.write(starters.text(name))
    except DocumentError as exc:
        console.error(str(exc))
        raise typer.Exit(1) from exc
