"""The `lorenzo` command line (ADR 0137); commands arrive with the RFC 0025 slices."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, TextIO

import httpx
import typer
from rich.console import Console
from rich.table import Table

from lorenzo_cli.auth import store as credentials
from lorenzo_cli.auth.login import LoginError, run_login
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.auth.tokens import NotLoggedInError, resolve_token_source
from lorenzo_cli.client.errors import (
    LorenzoApiError,
    LorenzoConnectionError,
    LorenzoResponseError,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.config import ConfigError, Settings, load_settings
from lorenzo_cli.evalworker import Engine, EvalError, EvalRequest, WorkerEngine, read_sources
from lorenzo_cli.importer.apply import ApplyOptions, apply_import
from lorenzo_cli.importer.give import PackError, entity_id_of, give_pack
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.mapping import MappingError
from lorenzo_cli.importer.plan import ImportPlan, Options
from lorenzo_cli.importer.review import plan_json, proposed_map, write_review_queue
from lorenzo_cli.importer.run import prepare
from lorenzo_cli.importer.teach import ask, rows_toml, unknown_values
from lorenzo_cli.report import (
    import_exit_code,
    print_evaluation,
    print_import_plan,
    print_seed_plan,
    seed_plan_json,
)
from lorenzo_cli.seed import LAYERS, apply_plan, load_builtin, make_plan, read_state
from lorenzo_cli.tenants import (
    TenantNotFoundError,
    WrongTenantKindError,
    require_repository,
    resolve_tenant,
)

app = typer.Typer(
    name="lorenzo",
    help="The Lorenzo command line.",
    no_args_is_help=True,
    add_completion=False,
)
tenant_app = typer.Typer(help="Read a tenant.", no_args_is_help=True)
app.add_typer(tenant_app, name="tenant")
pack_app = typer.Typer(help="Hand out an imported pack.", no_args_is_help=True)
app.add_typer(pack_app, name="pack")

_out = Console()
_err = Console(stderr=True)


@dataclass
class Runtime:
    """What a command runs against. Tests hand one in instead of the real environment."""

    env: Mapping[str, str]
    stdin: TextIO
    store: CredentialsFile
    transport: httpx.BaseTransport | None = None
    # Whether someone can be asked; None means: whether stdin is a terminal.
    interactive_override: bool | None = None
    # Evaluates MPMB files; the worker subprocess unless a test hands in another.
    engine: Engine = field(default_factory=WorkerEngine)
    api_url: str | None = None
    token_stdin: bool = False

    @property
    def interactive(self) -> bool:
        if self.interactive_override is not None:
            return self.interactive_override
        return self.stdin.isatty()

    @property
    def settings(self) -> Settings:
        return load_settings(self.env, api_url=self.api_url)


def default_runtime() -> Runtime:
    env = dict(os.environ)
    return Runtime(
        env=env,
        stdin=sys.stdin,
        store=CredentialsFile(Path(credentials.default_path(env))),
    )


@app.callback()
def main(
    ctx: typer.Context,
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="The API's base URL (or LORENZO_API_URL).")
    ] = None,
    token_stdin: Annotated[
        bool,
        typer.Option("--token-stdin", help="Read the access token from the first line of stdin."),
    ] = False,
) -> None:
    if ctx.obj is None:
        ctx.obj = default_runtime()
    runtime: Runtime = ctx.obj
    if api_url is not None:
        runtime.api_url = api_url
    if token_stdin:
        runtime.token_stdin = True


@contextmanager
def _reporting_errors() -> Iterator[None]:
    """Show an expected failure as one line on stderr and exit 1, not as a traceback."""
    try:
        yield
    except (
        ConfigError,
        NotLoggedInError,
        LoginError,
        EvalError,
        MappingError,
        PackError,
        WrongTenantKindError,
        TenantNotFoundError,
        LorenzoConnectionError,
        LorenzoResponseError,
    ) as exc:
        _err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except LorenzoApiError as exc:
        _err.print(f"[red]{exc} (HTTP {exc.status})[/red]")
        raise typer.Exit(1) from exc


@contextmanager
def _client(runtime: Runtime) -> Iterator[LorenzoClient]:
    base_url = runtime.settings.require_api_url()
    with httpx.Client(transport=runtime.transport, timeout=30.0) as auth_http:
        tokens = resolve_token_source(
            token_stdin=runtime.token_stdin,
            stdin=runtime.stdin,
            env=runtime.env,
            store=runtime.store,
            http=auth_http,
        )
        with LorenzoClient(base_url, tokens, transport=runtime.transport) as client:
            yield client


@tenant_app.command("show")
def tenant_show(
    ctx: typer.Context,
    tenant: Annotated[str, typer.Argument(help="The tenant's id or slug.")],
    as_json: Annotated[bool, typer.Option("--json", help="Print the tenant as JSON.")] = False,
) -> None:
    """Show one tenant: its kind, and whether it is published."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        found = resolve_tenant(client, tenant)
    if as_json:
        typer.echo(found.model_dump_json(indent=2))
        return
    table = Table(show_header=False, box=None)
    table.add_row("id", str(found.id))
    table.add_row("slug", found.slug)
    table.add_row("name", found.name)
    table.add_row("kind", found.kind.value)
    table.add_row("published", str(found.published_at) if found.published_at else "no")
    _out.print(table)


@app.command()
def login(
    ctx: typer.Context,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser", help="Print the address and paste the redirect back (WSL, SSH)."
        ),
    ] = False,
) -> None:
    """Sign in and store the login."""
    runtime: Runtime = ctx.obj
    with (
        _reporting_errors(),
        httpx.Client(transport=runtime.transport, timeout=30.0) as http_client,
    ):
        run_login(
            runtime.settings,
            no_browser=no_browser,
            http_client=http_client,
            store=runtime.store,
            echo=_out.print,
            read_line=lambda prompt: typer.prompt(prompt, prompt_suffix=""),
        )
    _out.print("Signed in.")


@app.command()
def logout(ctx: typer.Context) -> None:
    """Forget the stored login."""
    runtime: Runtime = ctx.obj
    removed = runtime.store.delete()
    _out.print("Signed out." if removed else "There was no stored login.")


@app.command("inspect")
def inspect_files(
    ctx: typer.Context,
    files: Annotated[
        list[Path],
        typer.Argument(exists=True, dir_okay=False, help="MPMB additional-content .js files."),
    ],
    base: Annotated[
        list[Path] | None,
        typer.Option(
            "--base",
            exists=True,
            dir_okay=False,
            help="The sheet's own data (Lists*.js), evaluated first; the lists start from it.",
        ),
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the whole evaluation as JSON.")
    ] = False,
) -> None:
    """Show what the JavaScript host reads from MPMB files, without touching any tenant."""
    runtime: Runtime = ctx.obj
    with _reporting_errors():
        request = EvalRequest(base=read_sources(base or []), files=read_sources(files))
        result = runtime.engine.evaluate(request)
    if as_json:
        typer.echo(result.model_dump_json(indent=2))
    else:
        print_evaluation(_out, result)
    if not result.ok:
        _err.print(f"[red]{result.error}[/red]")
    if not result.ok or any(f.status != "ok" for f in result.files):
        raise typer.Exit(1)


@app.command()
def seed(
    ctx: typer.Context,
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant", "-t", envvar="LORENZO_TENANT", help="The repository tenant's id or slug."
        ),
    ],
    layers: Annotated[
        list[str] | None,
        typer.Option("--layer", help=f"Only these layers of the seed ({', '.join(LAYERS)})."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be created; exit 2 if anything.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    allow_play_tenant: Annotated[
        bool,
        typer.Option(
            "--allow-play-tenant", help="Write to a play tenant, whose content can't be published."
        ),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the plan as JSON.")] = False,
) -> None:
    """Create the item taxonomy and the stat definitions in a tenant; safe to run again.

    Finds or creates by name and slug, and never changes or removes anything. Exit codes: 0 done
    or nothing to do, 2 with --dry-run when there is something to create, 1 on a problem.
    """
    runtime: Runtime = ctx.obj
    chosen = tuple(layers) if layers else LAYERS
    unknown = [layer for layer in chosen if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(LAYERS)}")
    spec = load_builtin()
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        require_repository(target, allow_play=allow_play_tenant)
        state = read_state(client, target.id, spec)
        plan = make_plan(spec, state, target, chosen)
        if as_json:
            typer.echo(json.dumps(seed_plan_json(plan), indent=2))
        else:
            print_seed_plan(_out, plan)
        if plan.problems:
            raise typer.Exit(1)
        if dry_run:
            raise typer.Exit(2 if plan.actions else 0)
        if not plan.actions:
            return
        if not yes:
            if not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
                raise typer.Exit(1)
            if not typer.confirm("Create these?"):
                raise typer.Exit(1)
        apply_plan(client, spec, plan, state)
    if not as_json:
        _out.print(
            f"Created {len(plan.actions)}. Run it again to check: it should find nothing to do."
        )


TenantOption = Annotated[
    str,
    typer.Option(
        "--tenant", "-t", envvar="LORENZO_TENANT", help="The repository tenant's id or slug."
    ),
]
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
    if not typer.confirm(f"Append them to {map_file}?"):
        return
    combined = map_file.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + text
    try:
        tomllib.loads(combined)
    except tomllib.TOMLDecodeError:
        _err.print(
            f"[yellow]Not appended: {map_file} already has one of those tables, so the result "
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
        Options(accept_moves=accept_moves, reconcile=reconcile), state, teach,
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
        bool, typer.Option("--public-catalog", help="Let players list the imported items too.")
    ] = False,
    teach: TeachOption = False,
    state: StateOption = None,
    review_queue: ReviewOption = Path("review-queue.json"),
    proposed_map_file: ProposedOption = Path("proposed.map.toml"),
) -> None:
    """Import these files: what the plan says, and nothing it holds back for review.

    Safe to run again, and unattended with --yes. Exit codes: 0 done, 1 something was left
    unresolved or failed.
    """
    runtime: Runtime = ctx.obj
    args = ImportArgs(
        tenant, files, base, map_file, allow_play_tenant,
        Options(accept_moves=accept_moves, reconcile=reconcile), state, teach,
    )  # fmt: skip
    with _reporting_errors(), _client(runtime) as client:
        result, manifest, taught = _prepare_plan(runtime, client, args)
        print_import_plan(_out, result, strict=strict)
        _write_review_files(result, review_queue, proposed_map_file)
        if result.problems:
            raise typer.Exit(1)
        unresolved = import_exit_code(result, strict=strict, reconcile=False) == 1
        if not result.pending and not (reconcile and result.reparent_count):
            raise typer.Exit(1 if unresolved else 0)
        if not yes:
            if not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
                raise typer.Exit(1)
            if not typer.confirm("Import these?"):
                raise typer.Exit(1)
        report = apply_import(
            client,
            result,
            manifest,
            ApplyOptions(reconcile=reconcile, public_catalog=public_catalog),
            progress=lambda line: _err.print(line, highlight=False, style="dim"),
        )
        manifest.save()
    _out.print(
        f"Created {report.created}, finished {report.completed}, re-parented {report.reparented}; "
        f"{report.categories} new categories, {report.definitions} new stat definitions."
    )
    for failure in report.failures:
        _err.print(f"[red]{failure}[/red]")
    if not report.failures:
        _save_taught(runtime, taught, map_file, proposed_map_file)
    raise typer.Exit(1 if (unresolved or report.failures) else 0)


def _inputs(files: list[Path] | None, base: list[Path] | None) -> list[Path]:
    if not files and not base:
        raise typer.BadParameter(
            "Give some .js files to import, or --base files (the sheet's own)."
        )
    return files or []


@pack_app.command("give")
def pack_give(
    ctx: typer.Context,
    pack: Annotated[str, typer.Argument(help="The pack's slug or id, as imported.")],
    tenant: TenantOption,
    owner: Annotated[
        str | None,
        typer.Option("--owner", help="The character (slug or id) who gets it. Default: nobody."),
    ] = None,
    into: Annotated[
        str | None,
        typer.Option("--into", help="A container (slug or id) to put it in. Default: none."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Say what would be created, and create nothing.")
    ] = False,
) -> None:
    """Create a pack's contents in a tenant: its container, then what is inside, with quantities.

    The contents are read from the pack's description, where the importer put them.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        owner_id = entity_id_of(client, target.id, owner, "character") if owner else None
        into_id = entity_id_of(client, target.id, into, "container") if into else None
        given = give_pack(
            client,
            target.id,
            pack,
            owner=owner_id,
            into=into_id,
            dry_run=dry_run,
            say=_out.print,
        )
    verb = "Would create" if dry_run else "Created"
    _out.print(f"{verb} {sum(g.created for g in given)} item(s).")
