"""The MPMB importer: `inspect`, `plan` and `apply` (RFC 0025, ADR 0144, 0182)."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from lorenzo_cli import console
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.evalworker import EvalRequest, read_sources
from lorenzo_cli.importer.apply import ApplyOptions, ApplyReport, apply_import
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.mapping import Part
from lorenzo_cli.importer.plan import ImportPlan, Options
from lorenzo_cli.importer.review import (
    apply_json,
    plan_json,
    proposed_map,
    write_review_queue,
)
from lorenzo_cli.importer.run import prepare
from lorenzo_cli.importer.teach import ask, rows_toml, unknown_values
from lorenzo_cli.report import (
    import_exit_code,
    print_evaluation,
    print_import_plan,
)
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _out,
    _reporting_errors,
    may_write,
)

app = typer.Typer()


@app.command("inspect")
def inspect_files(
    ctx: typer.Context,
    files: FilesArgument = None,
    base: BaseOption = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the whole evaluation as JSON.")
    ] = False,
) -> None:
    """Show what the JavaScript host reads from MPMB files, without touching any tenant.

    Name MPMB files, the sheet's own data with --base, or both: --base alone shows what the
    sheet ships.
    """
    runtime: Runtime = ctx.obj
    if not files and not base:
        raise typer.BadParameter("Name at least one file, or the sheet's own data with --base.")
    with _reporting_errors():
        request = EvalRequest(base=read_sources(base or []), files=read_sources(files or []))
        result = runtime.engine.evaluate(request)
    if as_json:
        console.emit(result.model_dump(mode="json"))
    else:
        print_evaluation(_out, result)
    if not result.ok:
        _err.print(f"[red]✗ {result.error}[/red]")
    if not result.ok or any(f.status != "ok" for f in result.files):
        raise typer.Exit(1)


FilesArgument = Annotated[
    list[Path] | None,
    typer.Argument(
        exists=True,
        dir_okay=False,
        help="MPMB .js files, in order: a later one wins. None is fine with --base.",
    ),
]
BaseOption = Annotated[
    list[Path] | None,
    typer.Option(
        "--base",
        exists=True,
        dir_okay=False,
        help="The sheet's own data (Lists*.js), evaluated first; the lists start from it.",
    ),
]
MapOption = Annotated[
    Path | None,
    typer.Option("--map", "-m", exists=True, dir_okay=False, help="Your mapping file."),
]
StrictOption = Annotated[
    bool,
    typer.Option("--strict", help="Never ask; treat attributes no rule mentions as unresolved."),
]
AllowPlayOption = Annotated[
    bool,
    typer.Option(
        "--allow-play-tenant", help="Write to a play tenant, whose content can't be published."
    ),
]
StateOption = Annotated[
    Path | None, typer.Option("--state", help="The run manifest (default: under XDG_STATE_HOME).")
]
ReviewOption = Annotated[
    Path, typer.Option("--review-queue", help="Where to write what needs a decision.")
]
ProposedOption = Annotated[
    Path, typer.Option("--proposed-map", help="Where to write map rows to consider.")
]


TeachOption = Annotated[
    bool,
    typer.Option(
        "--teach",
        help="At a terminal, ask about each value the map doesn't know, once, and use the answer.",
    ),
]


class PartChoice(StrEnum):
    neutral = "neutral"
    system = "system"


PartOption = Annotated[
    PartChoice | None,
    typer.Option(
        "--part",
        help="Only one half of each item (ADR 0182): `neutral`, what is true anywhere, for the "
        "common equipment; `system`, D&D's, as a prototype attached to the item the neutral pass "
        "made. Without it both halves go onto one item.",
    ),
]


def _part(choice: PartChoice | None) -> Part | None:
    if choice is None:
        return None
    return "neutral" if choice is PartChoice.neutral else "system"


@dataclass(frozen=True)
class ImportArgs:
    """What `plan` and `apply` share."""

    tenant: str
    files: list[Path] | None
    base: list[Path] | None
    map_file: Path | None
    allow_play_tenant: bool
    options: Options
    state: Path | None
    teach: bool


def _write_review_files(plan: ImportPlan, review: Path, proposed: Path) -> None:
    unresolved = plan.held or plan.unmapped() or plan.pack_unresolved()
    written = write_review_queue(review, plan) if unresolved else 0
    if written:
        proposed.write_text(proposed_map(plan), encoding="utf-8")
        _err.print(f"{written} thing(s) need a decision: see {review} and {proposed}.")


def _prepare_plan(
    runtime: Runtime, client: LorenzoClient, args: ImportArgs
) -> tuple[ImportPlan, Manifest, dict[tuple[str, str], list[str]]]:
    """Plan, asking about unknown values first when asked to and someone is there to answer."""
    inputs = _inputs(args.files, args.base)
    map_text = args.map_file.read_text(encoding="utf-8") if args.map_file else None
    taught: dict[tuple[str, str], list[str]] = {}
    asked: set[tuple[str, str, str]] = set()
    while True:
        plan, manifest = prepare(
            client,
            runtime.engine,
            runtime.env,
            tenant_ref=args.tenant,
            files=inputs,
            base=args.base or [],
            map_text=map_text,
            taught=rows_toml(taught),
            allow_play_tenant=args.allow_play_tenant,
            options=args.options,
            state_path=args.state,
        )
        if not (args.teach and runtime.interactive):
            return plan, manifest, taught
        fresh = [u for u in unknown_values(plan) if (u.list_name, u.attribute, u.key) not in asked]
        answered = False
        for unknown in fresh:
            asked.add((unknown.list_name, unknown.attribute, unknown.key))
            with console.paused():
                row = ask(
                    unknown,
                    plan.loaded.mapping,
                    lambda text, default: typer.prompt(
                        text, default=default, show_default=bool(default)
                    ),
                    _out.print,
                )
            if row is not None:
                taught.setdefault((unknown.list_name, unknown.attribute), []).append(row)
                answered = True
        if not answered:
            return plan, manifest, taught


def _save_taught(
    runtime: Runtime,
    taught: dict[tuple[str, str], list[str]],
    map_file: Path | None,
    proposed: Path,
) -> None:
    """Keep what was answered: always as a snippet, and, if asked, appended to the map."""
    if not taught:
        return
    text = rows_toml(taught)
    proposed.write_text(text, encoding="utf-8")
    _out.print(f"The rows you chose are in {proposed}.")
    if map_file is None or not runtime.interactive:
        return
    with console.paused():
        append = typer.confirm(f"Append them to {map_file}?")
    if not append:
        return
    combined = map_file.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + text
    try:
        tomllib.loads(combined)
    except tomllib.TOMLDecodeError:
        _err.print(
            f"[yellow]⚠ Not appended: {map_file} already has one of those tables, so the result "
            f"wouldn't be valid TOML. Paste the rows from {proposed} under it.[/yellow]"
        )
        return
    map_file.write_text(combined, encoding="utf-8")
    _out.print(f"Appended to {map_file}.")


@app.command()
def plan(
    ctx: typer.Context,
    tenant: TenantOption,
    files: FilesArgument = None,
    base: BaseOption = None,
    map_file: MapOption = None,
    strict: StrictOption = False,
    allow_play_tenant: AllowPlayOption = False,
    accept_moves: Annotated[
        bool, typer.Option("--accept-moves", help="Create items whose namespace changed.")
    ] = False,
    reconcile: Annotated[
        bool, typer.Option("--reconcile", help="Count changed parents as pending changes.")
    ] = False,
    part: PartOption = None,
    teach: TeachOption = False,
    state: StateOption = None,
    review_queue: ReviewOption = Path("review-queue.json"),
    proposed_map_file: ProposedOption = Path("proposed.map.toml"),
    as_json: Annotated[bool, typer.Option("--json", help="Print the plan as JSON.")] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write the plan JSON.")
    ] = None,
) -> None:
    """Work out what importing these files would do, and change nothing.

    Exit codes: 0 nothing to do, 2 changes pending, 1 something unresolved.
    """
    runtime: Runtime = ctx.obj
    args = ImportArgs(
        tenant, files, base, map_file, allow_play_tenant,
        Options(accept_moves=accept_moves, reconcile=reconcile, part=_part(part)), state, teach,
    )  # fmt: skip
    with _reporting_errors(), _client(runtime) as client:
        result, _, taught = _prepare_plan(runtime, client, args)
    document = json.dumps(plan_json(result), indent=2, ensure_ascii=False)
    if output is not None:
        output.write_text(document + "\n", encoding="utf-8")
    if as_json:
        typer.echo(document)
    else:
        print_import_plan(_out, result, strict=strict)
    _write_review_files(result, review_queue, proposed_map_file)
    _save_taught(runtime, taught, None, proposed_map_file)
    raise typer.Exit(import_exit_code(result, strict=strict, reconcile=reconcile))


@app.command()
def apply(
    ctx: typer.Context,
    tenant: TenantOption,
    files: FilesArgument = None,
    base: BaseOption = None,
    map_file: MapOption = None,
    strict: StrictOption = False,
    allow_play_tenant: AllowPlayOption = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    accept_moves: Annotated[
        bool, typer.Option("--accept-moves", help="Create items whose namespace changed.")
    ] = False,
    reconcile: Annotated[
        bool, typer.Option("--reconcile", help="Also re-parent items the map now files elsewhere.")
    ] = False,
    public_catalog: Annotated[
        bool,
        typer.Option(
            "--public-catalog",
            help="Let players list the imported items too (not with --part system: a prototype "
            "is never public).",
        ),
    ] = False,
    part: PartOption = None,
    teach: TeachOption = False,
    state: StateOption = None,
    review_queue: ReviewOption = Path("review-queue.json"),
    proposed_map_file: ProposedOption = Path("proposed.map.toml"),
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Print one JSON document: the plan, what was written, what failed. Never asks, "
            "so it needs --yes to write.",
        ),
    ] = False,
) -> None:
    """Import these files: what the plan says, and nothing it holds back for review.

    Safe to run again, and unattended with --yes. Exit codes: 0 done, 1 something was left
    unresolved or failed.
    """
    runtime: Runtime = ctx.obj
    if as_json and teach:
        raise typer.BadParameter("--json never asks, so it can't be used with --teach.")
    if public_catalog and part is PartChoice.system:
        raise typer.BadParameter(
            "--public-catalog is for the neutral pass: the system's prototypes are never public."
        )
    args = ImportArgs(
        tenant, files, base, map_file, allow_play_tenant,
        Options(accept_moves=accept_moves, reconcile=reconcile, part=_part(part)), state, teach,
    )  # fmt: skip

    def emit(plan: ImportPlan, report: ApplyReport | None, unresolved: bool) -> None:
        if as_json:
            typer.echo(
                json.dumps(apply_json(plan, report, unresolved), indent=2, ensure_ascii=False)
            )

    with _reporting_errors(), _client(runtime, writes=True) as client:
        result, manifest, taught = _prepare_plan(runtime, client, args)
        if not as_json:
            print_import_plan(_out, result, strict=strict)
        _write_review_files(result, review_queue, proposed_map_file)
        if result.problems:
            emit(result, None, True)
            raise typer.Exit(1)
        unresolved = import_exit_code(result, strict=strict, reconcile=False) == 1
        if not result.pending and not (reconcile and result.reparent_count):
            emit(result, None, unresolved)
            raise typer.Exit(1 if unresolved else 0)
        if not yes and (as_json or not runtime.interactive):
            emit(result, None, unresolved)
        may_write(runtime, yes=yes, question="Import these?")
        writing = sum(1 for i in result.items if i.status in ("create", "complete", "retitle"))
        with console.counting("Importing", writing) as steps:

            def step(line: str) -> None:
                steps.describe(line.split(" ", 1)[-1])
                steps.advance()

            report = apply_import(
                client,
                result,
                manifest,
                ApplyOptions(reconcile=reconcile, public_catalog=public_catalog),
                progress=step,
            )
        manifest.save()
    failed = bool(unresolved or report.failures)
    if as_json:
        emit(result, report, unresolved)
        for failure in report.failures:
            _err.print(f"[red]✗ {failure}[/red]")
        raise typer.Exit(1 if failed else 0)
    attached = f"attached {report.attached}, " if result.part == "system" else ""
    _out.print(
        f"Created {report.created}, finished {report.completed}, {attached}"
        f"retitled {report.retitled}, re-parented {report.reparented}; "
        f"{report.categories} new categories, {report.definitions} new stat definitions."
    )
    for failure in report.failures:
        _err.print(f"[red]✗ {failure}[/red]")
    if not report.failures:
        _save_taught(runtime, taught, map_file, proposed_map_file)
    raise typer.Exit(1 if failed else 0)


def _inputs(files: list[Path] | None, base: list[Path] | None) -> list[Path]:
    if not files and not base:
        raise typer.BadParameter(
            "Give some .js files to import, or --base files (the sheet's own)."
        )
    return files or []
