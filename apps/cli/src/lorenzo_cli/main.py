"""The `lorenzo` command line (ADR 0137); commands arrive with the RFC 0025 slices."""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import tomllib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated, TextIO
from urllib.parse import urlsplit

import httpx
import typer
from rich.console import Console
from rich.table import Table

from lorenzo_cli import rawapi, repo_report, repos
from lorenzo_cli.auth import store as credentials
from lorenzo_cli.auth.login import LoginError, run_login
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.auth.tokens import NotLoggedInError, resolve_token_source
from lorenzo_cli.client.errors import (
    LorenzoApiError,
    LorenzoConnectionError,
    LorenzoResponseError,
)
from lorenzo_cli.client.models import (
    PublishRequest,
    TenantCreate,
    TenantKind,
    TenantOut,
    TenantSummaryOut,
)
from lorenzo_cli.client.ops import (
    CREATE_TENANT,
    DELETE_TENANT,
    GET_ME,
    GRANT_REPOSITORY,
    LIST_REPOSITORY_UPDATES,
    LIST_TENANTS,
    PLAN_REPOSITORY_COPY,
    PUBLISH_REPOSITORY,
    REVOKE_REPOSITORY,
    UNPUBLISH_REPOSITORY,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.config import (
    ConfigError,
    Settings,
    SettingsFile,
    default_config_path,
    load_settings,
)
from lorenzo_cli.evalworker import Engine, EvalError, EvalRequest, WorkerEngine, read_sources
from lorenzo_cli.importer.apply import ApplyOptions, ApplyReport, apply_import
from lorenzo_cli.importer.give import (
    PackError,
    count_instances,
    give_pack,
    tree_lines,
)
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.mapping import MappingError, Part
from lorenzo_cli.importer.plan import ImportPlan, Options
from lorenzo_cli.importer.review import (
    apply_json,
    plan_json,
    proposed_map,
    write_review_queue,
)
from lorenzo_cli.importer.run import prepare
from lorenzo_cli.importer.teach import ask, rows_toml, unknown_values
from lorenzo_cli.inventory import preprocess as inventory_preprocess
from lorenzo_cli.inventory.apply import apply as apply_inventory
from lorenzo_cli.inventory.export import export_inventory
from lorenzo_cli.inventory.format import parse as parse_inventory
from lorenzo_cli.inventory.format import render_json, render_markdown
from lorenzo_cli.inventory.plan import Plan, build_plan
from lorenzo_cli.report import (
    import_exit_code,
    print_evaluation,
    print_import_plan,
    print_seed_list,
    print_seed_plan,
    print_unseed_plan,
    print_unseed_result,
    seed_list_json,
    seed_plan_json,
    unseed_counts,
    unseed_plan_json,
    unseed_result_json,
)
from lorenzo_cli.repos import RepoError
from lorenzo_cli.seed import (
    LAYERS,
    UnseedPlan,
    UnseedResult,
    apply_plan,
    apply_unseed,
    load_builtin,
    make_plan,
    make_unseed_plan,
    read_contents,
    read_state,
    read_unseed_state,
)
from lorenzo_cli.self_service import (
    SelfServiceError,
    add_item,
    catalog,
    characters,
    resolve_container,
    resolve_item,
    resolve_owner,
)
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
    add_completion=True,
)
tenant_app = typer.Typer(help="List, read or create a tenant.", no_args_is_help=True)
app.add_typer(tenant_app, name="tenant")
pack_app = typer.Typer(help="Hand out an imported pack.", no_args_is_help=True)
app.add_typer(pack_app, name="pack")
item_app = typer.Typer(help="Find the items you may add, and add one.", no_args_is_help=True)
app.add_typer(item_app, name="item")
inventory_app = typer.Typer(
    help="Bring a character's inventory in from a file, or write it out as one.",
    no_args_is_help=True,
)
app.add_typer(inventory_app, name="inventory")
character_app = typer.Typer(help="List characters.", no_args_is_help=True)
app.add_typer(character_app, name="character")
repo_app = typer.Typer(
    help="Publish a repository, grant it, copy it into a tenant, and take its updates.",
    no_args_is_help=True,
)
app.add_typer(repo_app, name="repo")

_out = Console()
_err = Console(stderr=True)


def _warn(message: str) -> None:
    _err.print(f"[yellow]{message}[/yellow]")


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
    # What `login` remembered (ADR 0157); None means there is no file to read, as in most tests.
    config: SettingsFile | None = None

    @property
    def interactive(self) -> bool:
        if self.interactive_override is not None:
            return self.interactive_override
        return self.stdin.isatty()

    @property
    def settings(self) -> Settings:
        return self.resolve_settings()

    def resolve_settings(
        self, *, issuer: str | None = None, client_id: str | None = None
    ) -> Settings:
        """Flag, then environment, then the remembered file (ADR 0157)."""
        remembered = self.config.load(warn=_warn) if self.config else {}
        return load_settings(
            self.env,
            api_url=self.api_url,
            issuer=issuer,
            client_id=client_id,
            remembered=remembered,
        )


def default_runtime() -> Runtime:
    env = dict(os.environ)
    return Runtime(
        env=env,
        stdin=sys.stdin,
        store=CredentialsFile(Path(credentials.default_path(env))),
        config=SettingsFile(default_config_path(env)),
    )


def _show_version(show: bool) -> None:
    """Answer `--version` before anything else is read: no login, no API URL, no network."""
    if not show:
        return
    try:
        installed = importlib.metadata.version("lorenzo-cli")
    except importlib.metadata.PackageNotFoundError:
        installed = "unknown (not installed as a package)"
    typer.echo(f"lorenzo {installed}")
    raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    api_url: Annotated[
        str | None,
        typer.Option(
            "--api-url", help="The API's base URL (or LORENZO_API_URL; `login` remembers it)."
        ),
    ] = None,
    token_stdin: Annotated[
        bool,
        typer.Option("--token-stdin", help="Read the access token from the first line of stdin."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
        ),
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
        RepoError,
        SelfServiceError,
    ) as exc:
        _err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except LorenzoApiError as exc:
        _err.print(f"[red]{repos.in_words(exc)} (HTTP {exc.status})[/red]", highlight=False)
        raise typer.Exit(1) from exc


@contextmanager
def _client(runtime: Runtime, *, writes: bool = False) -> Iterator[LorenzoClient]:
    """The API client; a command that writes says so when it is the official default (ADR 0164)."""
    settings = runtime.settings
    base_url = settings.require_api_url()
    with httpx.Client(transport=runtime.transport, timeout=30.0) as auth_http:
        tokens = resolve_token_source(
            token_stdin=runtime.token_stdin,
            stdin=runtime.stdin,
            env=runtime.env,
            store=runtime.store,
            http=auth_http,
        )
        if writes and settings.defaulted:
            _err.print(
                f"Using the official Lorenzo at {base_url}.", highlight=False, soft_wrap=True
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
    _print_tenant(found, as_json)


def _print_tenant(found: TenantOut, as_json: bool) -> None:
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


@tenant_app.command("list")
def tenant_list(
    ctx: typer.Context,
    kind: Annotated[
        TenantKind | None,
        typer.Option("--kind", help="Only repositories, or only play tenants."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the tenants as JSON.")] = False,
) -> None:
    """List the tenants you belong to, with each one's kind and your role in it."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        rows = list(
            all_items(
                client,
                LIST_TENANTS,
                query={"kind": kind.value if kind else None},
                of=TenantSummaryOut,
            )
        )
    if as_json:
        typer.echo(json.dumps([row.model_dump(mode="json") for row in rows], indent=2))
        return
    if not rows:
        _out.print("You don't belong to any tenant yet. `lorenzo tenant create` makes one.")
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("slug", "name", "kind", "role"):
        table.add_column(heading)
    for row in rows:
        table.add_row(row.slug, row.name, row.kind.value, row.role.value)
    _out.print(table)


@tenant_app.command("create")
def tenant_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="The tenant's name.")],
    slug: Annotated[
        str | None, typer.Option("--slug", help="Its address (default: derived from the name).")
    ] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    kind: Annotated[
        TenantKind,
        typer.Option(
            "--kind",
            help="repository holds content to publish and copy (what an import needs); play is "
            "a table's own. Fixed for good once created.",
        ),
    ] = TenantKind.repository,
    as_json: Annotated[bool, typer.Option("--json", help="Print the tenant as JSON.")] = False,
) -> None:
    """Create a tenant, a repository unless told otherwise, and become its owner.

    Needs the tenant-creator role. Then `lorenzo seed --tenant <slug>` makes a repository ready
    to import into.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        body = TenantCreate(name=name, slug=slug, description=description, kind=kind)
        created = client.call(CREATE_TENANT, body=body).value
    _print_tenant(created, as_json)
    if not as_json and created.kind == TenantKind.repository:
        _out.print(f"Next: lorenzo seed --tenant {created.slug}")


@tenant_app.command("delete")
def tenant_delete(
    ctx: typer.Context,
    tenant: Annotated[str, typer.Argument(help="The tenant's id or slug.")],
    yes: Annotated[
        bool, typer.Option("--yes", help="Don't ask before deleting (nothing else is asked).")
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the tenant that was deleted as JSON. Needs --yes.")
    ] = False,
) -> None:
    """Delete a tenant and everything in it. This can't be undone.

    Takes both the tenant-creator role and being one of the tenant's owners. A repository that
    other tenants still hold a grant on is refused, with nothing deleted: take the grants back
    (`lorenzo repo revoke`), or delete the tenants that hold it, first. Tenants that copied from
    a repository keep what they copied. The tenant's other members are told.

    It asks you to type the tenant's slug (`--yes` skips that; `--json` never asks and needs it).
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        found = resolve_tenant(client, tenant)
        if not yes:
            if as_json or not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to delete.[/red]")
                raise typer.Exit(1)
            _print_tenant(found, False)
            _err.print(
                f"[bold]This deletes “{found.name}” and everything in it.[/bold] "
                "It can't be undone."
            )
            if typer.prompt("Type its slug to confirm").strip() != found.slug:
                _err.print("Nothing was deleted.")
                raise typer.Exit(1)
        try:
            client.call(DELETE_TENANT, path={"tenant_id": found.id})
        except LorenzoApiError as exc:
            if exc.problem_type != "repository-still-granted":
                raise
            raise LorenzoApiError(
                f"{exc} Take the grants back first (`lorenzo repo subscribers --tenant "
                f"{found.slug}` lists who holds it, `lorenzo repo revoke <tenant> --tenant "
                f"{found.slug}` takes one back), or delete the tenants that hold it.",
                exc.status,
                exc.problem,
            ) from exc
    if as_json:
        typer.echo(found.model_dump_json(indent=2))
    else:
        _out.print(f"Deleted {found.slug} (“{found.name}”).")


def _require_address(name: str, value: str | None) -> None:
    """A remembered address has to look like one, or the next run would fail far from the cause."""
    if value is None:
        return
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigError(f"{name} “{value}” isn't an address: it should start with https://")


def _signing_in(settings: Settings) -> str:
    """Where `login` is about to sign in and for which API, before anything opens (ADR 0164)."""
    where = f"Signing in at {settings.issuer}"
    if settings.api_url:
        where += f", for the API at {settings.api_url}"
    return where + (" (the official Lorenzo)." if settings.defaulted else ".")


def _remember(runtime: Runtime, settings: Settings) -> None:
    """After a login that worked, keep the three settings it used for the next one (ADR 0157)."""
    if runtime.config is None:
        return
    if settings.defaulted:
        # The official set is never kept: a copy would outlive the defaults it came from.
        if runtime.config.delete():
            _out.print(
                f"Forgot the settings remembered in {runtime.config.path}: "
                "the official Lorenzo is the default again."
            )
        return
    used = {
        key: value
        for key, value in (
            ("api_url", settings.api_url),
            ("issuer", settings.issuer),
            ("client_id", settings.client_id),
        )
        if value
    }
    before = runtime.config.load()
    if all(before.get(key) == value for key, value in used.items()):
        return
    runtime.config.save(used)
    _out.print(
        f"Remembered the {', '.join(_SETTING_NAMES[k] for k in used)} in {runtime.config.path}."
    )


_SETTING_NAMES = {"api_url": "API URL", "issuer": "issuer", "client_id": "client id"}


@app.command()
def login(
    ctx: typer.Context,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser", help="Print the address and paste the redirect back (WSL, SSH)."
        ),
    ] = False,
    issuer: Annotated[
        str | None,
        typer.Option("--issuer", help="The Authgear issuer (or LORENZO_AUTHGEAR_ISSUER)."),
    ] = None,
    client_id: Annotated[
        str | None,
        typer.Option(
            "--client-id", help="The Authgear client's id (or LORENZO_AUTHGEAR_CLIENT_ID)."
        ),
    ] = None,
) -> None:
    """Sign in and store the login, and remember the API URL, issuer and client id it used."""
    runtime: Runtime = ctx.obj
    with (
        _reporting_errors(),
        httpx.Client(transport=runtime.transport, timeout=30.0) as http_client,
    ):
        settings = runtime.resolve_settings(issuer=issuer, client_id=client_id)
        _require_address("The API URL", settings.api_url)
        _require_address("The issuer", settings.issuer)
        if settings.issuer:
            _out.print(_signing_in(settings), highlight=False, soft_wrap=True)
        run_login(
            settings,
            no_browser=no_browser,
            http_client=http_client,
            store=runtime.store,
            echo=_out.print,
            read_line=lambda prompt: typer.prompt(prompt, prompt_suffix=""),
        )
        _remember(runtime, settings)
    _out.print("Signed in.")


def _token_origin(runtime: Runtime) -> str:
    """Where the token came from, in the order ADR 0137 fixes."""
    if runtime.token_stdin:
        return "--token-stdin"
    if runtime.env.get("LORENZO_TOKEN"):
        return "LORENZO_TOKEN"
    return "the stored login"


@app.command()
def whoami(
    ctx: typer.Context,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print what the API says as JSON.")
    ] = False,
) -> None:
    """Ask the API who the token you would use belongs to: a check that a login works."""
    runtime: Runtime = ctx.obj
    origin = _token_origin(runtime)
    with _reporting_errors(), _client(runtime) as client:
        try:
            me = client.call(GET_ME).value
        except LorenzoApiError as exc:
            if exc.status == 401:
                raise LorenzoApiError(
                    f"The API didn't accept the token from {origin}. Run `lorenzo login` again, "
                    "or check LORENZO_TOKEN.",
                    exc.status,
                    exc.problem,
                ) from exc
            raise
    if as_json:
        typer.echo(me.model_dump_json(indent=2))
        return
    table = Table(show_header=False, box=None)
    table.add_row("user", str(me.id))
    name = me.display_name or me.nickname
    if name:
        table.add_row("name", name)
    if me.email:
        table.add_row("email", me.email)
    settings = runtime.settings
    table.add_row("api", f"{settings.api_url}{' (the default)' if settings.defaulted else ''}")
    table.add_row("token", origin)
    table.add_row("tenants", str(len(me.memberships)))
    _out.print(table)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Forget the stored login (the API URL, issuer and client id it remembered stay)."""
    runtime: Runtime = ctx.obj
    removed = runtime.store.delete()
    _out.print("Signed out." if removed else "There was no stored login.")


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
        str | None,
        typer.Option(
            "--tenant", "-t", envvar="LORENZO_TENANT", help="The repository tenant's id or slug."
        ),
    ] = None,
    layers: Annotated[
        list[str] | None,
        typer.Option(
            "--layer",
            help=f"Only these layers of the seed ({', '.join(LAYERS)}). Without it, every layer "
            "is seeded, unless the tenant holds one and not another (name the layers then).",
        ),
    ] = None,
    list_seed: Annotated[
        bool,
        typer.Option(
            "--list",
            help="Only list what the seed makes, per layer. Needs no login and no tenant.",
        ),
    ] = False,
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

    Finds or creates by name and slug, and never changes or removes anything (`unseed` takes a
    layer out). The dnd5e-equipment layer is made of attachments: parents it adds to categories of
    the equipment layer. `--list` only prints what the seed makes. Exit codes: 0 done or nothing to
    do, 2 with --dry-run when there is something to create, 1 on a problem.
    """
    runtime: Runtime = ctx.obj
    chosen = tuple(layers) if layers else LAYERS
    unknown = [layer for layer in chosen if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(LAYERS)}")
    spec = load_builtin()
    if list_seed:
        writing = [
            flag
            for flag, given in (
                ("--dry-run", dry_run),
                ("--yes", yes),
                ("--allow-play-tenant", allow_play_tenant),
            )
            if given
        ]
        if writing:
            raise typer.BadParameter(
                f"--list only reads the seed, so it can't go with {', '.join(writing)}."
            )
        if as_json:
            typer.echo(json.dumps(seed_list_json(spec, chosen), indent=2))
        else:
            print_seed_list(_out, spec, chosen)
        return
    if tenant is None:
        raise typer.BadParameter("Name the repository with --tenant (or LORENZO_TENANT).")
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        require_repository(target, allow_play=allow_play_tenant)
        state = read_state(client, target.id, spec)
        plan = make_plan(spec, state, target, chosen, explicit=layers is not None)
        if as_json:
            typer.echo(json.dumps(seed_plan_json(plan), indent=2))
        else:
            print_seed_plan(_out, plan)
            if layers is None and any(a.kind != "retitle" for a in plan.actions):
                _err.print(
                    "[dim]Every layer is going into this one repository, which is fine for your "
                    "own use. To publish them as separate repositories, seed each layer into its "
                    "own with --layer (README, ADR 0162, 0181).[/dim]"
                )
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


@app.command()
def unseed(
    ctx: typer.Context,
    tenant: TenantOption,
    layers: Annotated[
        list[str],
        typer.Option(
            "--layer",
            help=f"A layer of the seed to take out ({', '.join(LAYERS)}). Required; repeat for "
            "more.",
        ),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be removed; exit 2 if anything.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before deleting.")] = False,
    allow_play_tenant: Annotated[
        bool,
        typer.Option("--allow-play-tenant", help="Work on a play tenant, as seed does there."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print the plan and what was removed as JSON. Needs --yes."),
    ] = False,
) -> None:
    """Take a layer of the seed out of a tenant.

    Removes its attachments (the parent a layer adds to a category of another
    layer, which leaves the category itself alone), categories, stat
    definitions and stat groups, and only those the built-in seed names. It
    asks first.

    A category that something outside the layer inherits from stops it, with
    nothing deleted: that includes a category the dnd5e-equipment layer
    attaches, unless you take that layer out in the same call. A stat
    definition that is in use is kept and listed.

    Exit codes: 0 done or nothing to remove, 2 with --dry-run when there is
    something to remove, 1 on a problem, when something was kept, or when you
    said no.
    """
    runtime: Runtime = ctx.obj
    unknown = [layer for layer in layers if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(LAYERS)}")
    chosen = tuple(dict.fromkeys(layers))
    spec = load_builtin()

    def emit(plan: UnseedPlan, result: UnseedResult | None) -> None:
        if as_json:
            document = {
                "plan": unseed_plan_json(plan),
                "result": None if result is None else unseed_result_json(result),
            }
            typer.echo(json.dumps(document, indent=2))

    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        require_repository(target, allow_play=allow_play_tenant)
        plan = make_unseed_plan(
            spec, read_unseed_state(client, target.id, spec, chosen), target, chosen
        )
        if not as_json:
            print_unseed_plan(_out, plan)
        if plan.problems:
            emit(plan, None)
            raise typer.Exit(1)
        if not plan.targets:
            emit(plan, None)
            return
        if dry_run:
            emit(plan, None)
            raise typer.Exit(2)
        if not yes:
            if as_json or not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to delete.[/red]")
                raise typer.Exit(1)
            question = (
                f"Delete {unseed_counts(plan)} of the {' and '.join(chosen)} layer from "
                f"{target.slug}? The stat definitions can't be restored."
            )
            if not typer.confirm(question, default=False):
                _err.print("Nothing was deleted.")
                raise typer.Exit(1)
        result = apply_unseed(client, plan)
    emit(plan, result)
    if not as_json:
        print_unseed_result(_out, result)
    if result.kept:
        raise typer.Exit(1)


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
        if not yes:
            if as_json or not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
                emit(result, None, unresolved)
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
    failed = bool(unresolved or report.failures)
    if as_json:
        emit(result, report, unresolved)
        for failure in report.failures:
            _err.print(f"[red]{failure}[/red]")
        raise typer.Exit(1 if failed else 0)
    attached = f"attached {report.attached}, " if result.part == "system" else ""
    _out.print(
        f"Created {report.created}, finished {report.completed}, {attached}"
        f"retitled {report.retitled}, re-parented {report.reparented}; "
        f"{report.categories} new categories, {report.definitions} new stat definitions."
    )
    for failure in report.failures:
        _err.print(f"[red]{failure}[/red]")
    if not report.failures:
        _save_taught(runtime, taught, map_file, proposed_map_file)
    raise typer.Exit(1 if failed else 0)


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
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            "-t",
            envvar="LORENZO_TENANT",
            help="The tenant's id or slug: one with the pack in it, and the owner.",
        ),
    ],
    owner: Annotated[
        str,
        typer.Option(
            "--owner",
            help="The being or group (slug or id) who gets it. A being takes it into its hands.",
        ),
    ],
    override: Annotated[
        bool,
        typer.Option("--override", help="A GM's: hand it out even past what the owner can carry."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Say what would be made, and make nothing.")
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print what the API made (or would make) as JSON.")
    ] = False,
) -> None:
    """Hand a pack out: its containers, and what is inside them, with quantities.

    The API reads the contents from the pack's description, where the importer put them, and makes
    everything in one go or nothing at all.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        given = give_pack(client, target.id, pack, owner, override=override, dry_run=dry_run)
    if as_json:
        typer.echo(given.model_dump_json(indent=2))
        return
    for line in tree_lines(given):
        _out.print(line, highlight=False)
    verb = "Would give" if dry_run else "Gave"
    _out.print(f"{verb} {count_instances(given)} item(s).")


ItemTenant = Annotated[
    str,
    typer.Option("--tenant", "-t", envvar="LORENZO_TENANT", help="The library: its id or slug."),
]


@item_app.command("list")
def item_list(
    ctx: typer.Context,
    tenant: ItemTenant,
    query: Annotated[
        str | None, typer.Option("--query", "-q", help="Only items whose name has this in it.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the items as JSON.")] = False,
) -> None:
    """List the items you may add: for a player the public catalog, for a member all of it."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        items = catalog(client, target.id, query)
    if as_json:
        typer.echo(json.dumps([item.model_dump(mode="json") for item in items], indent=2))
        return
    if not items:
        _out.print("Nothing matches." if query else "Nothing is in the catalog you can see yet.")
        return
    table = Table(box=None, pad_edge=False)
    table.add_column("title")
    table.add_column("id")
    for item in items:
        table.add_row(item.title, str(item.entity_id))
    _out.print(table)


@item_app.command("add")
def item_add(
    ctx: typer.Context,
    item: Annotated[str, typer.Argument(help="The item: its id, its slug, or its exact title.")],
    tenant: ItemTenant,
    owner: Annotated[
        str | None,
        typer.Option(
            "--owner",
            help="The character (id or name) to add it to; your only one when you leave it out.",
        ),
    ] = None,
    name: Annotated[
        str | None, typer.Option("--name", help="Call it this instead of the item's own name.")
    ] = None,
    quantity: Annotated[
        int, typer.Option("--quantity", "-n", help="How many, as one stack. Needs --into.")
    ] = 1,
    into: Annotated[
        str | None,
        typer.Option("--into", help="A container you hold (id or slug) to put it in."),
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the new item instance as JSON.")
    ] = False,
) -> None:
    """Add an item to a character: one instance, not carried, or a stack inside a container.

    The same rules as the web: a player adds public items to their own characters while self-service
    is on for them, and the API says why when it is not.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        target = resolve_tenant(client, tenant)
        found = resolve_item(client, target.id, item)
        owner_id, owner_name = resolve_owner(client, target.id, owner)
        container = resolve_container(client, target.id, into) if into else None
        made = add_item(
            client, target.id, found, owner_id, name=name, quantity=quantity, into=container
        )
    if as_json:
        typer.echo(made.model_dump_json(indent=2))
        return
    count = f"{quantity} x " if quantity > 1 else ""
    _out.print(f"Added {count}{made.title} to {owner_name}.", highlight=False)
    _out.print(str(made.entity_id))


@character_app.command("list")
def character_list(
    ctx: typer.Context,
    tenant: ItemTenant,
    everyone: Annotated[
        bool, typer.Option("--all", help="The library's characters, not only yours.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the characters as JSON.")] = False,
) -> None:
    """List your characters in a library, or with --all everyone's."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        target = resolve_tenant(client, tenant)
        found = characters(client, target.id, mine=not everyone)
    if as_json:
        typer.echo(json.dumps([row.model_dump(mode="json") for row in found], indent=2))
        return
    if not found:
        _out.print("No characters here." if everyone else "You don't control a character here yet.")
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("name", "id", "kind"):
        table.add_column(heading)
    for row in found:
        table.add_row(row.name, str(row.entity_id), "PC" if row.is_pc else "NPC")
    _out.print(table)


@app.command("api")
def api_request(
    ctx: typer.Context,
    method: Annotated[str, typer.Argument(help="GET, POST, PUT, PATCH or DELETE.")],
    path: Annotated[
        str, typer.Argument(help="A path on the API, like /tenants. Never a full address.")
    ],
    data: Annotated[
        str | None,
        typer.Option(
            "--data", "-d", help="The JSON body: text, @file, or - for stdin (POST, PUT, PATCH)."
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option("--query", "-q", help="A query parameter, KEY=VALUE. Repeat for more."),
    ] = None,
    if_match: Annotated[
        str | None,
        typer.Option("--if-match", help="Send If-Match: an ETag from an earlier read."),
    ] = None,
    include: Annotated[
        bool,
        typer.Option("--include", "-i", help="Print the status line and the headers first."),
    ] = False,
    paginate: Annotated[
        bool,
        typer.Option("--paginate", help="GET only: walk every page and print one array of items."),
    ] = False,
    raw: Annotated[bool, typer.Option("--raw", help="Print the body exactly as it came.")] = False,
) -> None:
    """Make one authenticated request to the API, and print its answer.

    The body goes to stdout. Exit 0 for a 2xx answer, 1 for anything else (the API's own
    explanation is still printed, and its status goes to stderr).
    """
    runtime: Runtime = ctx.obj
    try:
        verb = rawapi.check_method(method)
        target = rawapi.check_path(path)
        pairs = rawapi.parse_query(query or [])
        if paginate and verb != "GET":
            raise rawapi.RequestUsageError("--paginate only walks a GET.", "--paginate")
        if paginate and include:
            raise rawapi.RequestUsageError(
                "--include shows one response; --paginate makes many.", "--paginate"
            )
        body = rawapi.read_body(data, verb, runtime.stdin)
    except rawapi.RequestUsageError as exc:
        raise typer.BadParameter(str(exc), param_hint=exc.hint) from exc

    with _reporting_errors(), _client(runtime, writes=verb != "GET") as client:
        items: list[object] | None = None
        if paginate:
            response, items = rawapi.paginate(client, target, query=pairs)
        else:
            response = rawapi.send(client, verb, target, query=pairs, body=body, if_match=if_match)

    if include:
        typer.echo(rawapi.status_line(response))
        for line in rawapi.header_lines(response):
            typer.echo(line)
        typer.echo("")
    if items is not None:
        typer.echo(json.dumps(items, indent=2, ensure_ascii=False))
    elif response.content:
        typer.echo(response.content if raw else rawapi.pretty(response.content), nl=False)
    if response.is_error:
        _err.print(f"[red]{rawapi.failure_summary(response)}[/red]", highlight=False)
        raise typer.Exit(1)


# --- lorenzo repo (ADR 0159, 0160) ------------------------------------------------------------


class OnCollision(StrEnum):
    merge = "merge"
    skip = "skip"


class Again(StrEnum):
    keep = "keep"
    purge = "purge"


RepositoryTenant = Annotated[
    str,
    typer.Option("--tenant", "-t", envvar="LORENZO_TENANT", help="The repository: its id or slug."),
]
DrawingTenant = Annotated[
    str,
    typer.Option(
        "--tenant",
        "-t",
        envvar="LORENZO_TENANT",
        help="The tenant that draws on the repository, and copies it: its id or slug.",
    ),
]
RepositoryArgument = Annotated[
    str,
    typer.Argument(help="The repository: its id, or its slug among those granted to or copied."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print the answer as JSON.")]
YesOption = Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")]
OnCollisionOption = Annotated[
    OnCollision | None,
    typer.Option(
        "--on-collision",
        help="Answer every name already in use here that allows it: merge into the local one, or "
        "skip. A slug can only be skipped or renamed.",
    ),
]
ChoicesOption = Annotated[
    Path | None,
    typer.Option(
        "--choices",
        exists=True,
        dir_okay=False,
        help="A JSON file of choices (kind, source_id, action, name), as copy-plan --json lists "
        "the collisions.",
    ),
]


def _may_write(runtime: Runtime, *, yes: bool, as_json: bool, prompt: str) -> None:
    """Ask before writing, unless told not to; never with --json, or when nobody can answer."""
    if yes:
        return
    if as_json or not runtime.interactive:
        _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
        raise typer.Exit(1)
    if not typer.confirm(prompt):
        raise typer.Exit(1)


def _echo_json(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@repo_app.command("publish")
def repo_publish(
    ctx: typer.Context,
    tenant: RepositoryTenant,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            help="What to call this release, in your own words (1.3, Spring errata). "
            "Without one it is called by its number.",
        ),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help="What this release is, for the people who read about it."),
    ] = None,
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            help="Say that libraries built on this repository should look before they update.",
        ),
    ] = False,
    acknowledge_breaking: Annotated[
        bool,
        typer.Option(
            "--acknowledge-breaking",
            help="Publish although the release removes or changes things libraries already hold, "
            "which is otherwise refused with the list of them.",
        ),
    ] = False,
    as_json: JsonOption = False,
) -> None:
    """Publish a repository as a release, or as a new one if it already is.

    Only its owners can. Until the first publish no library it is invited to can see anything of
    it; every release tells each of them what it is called and what its notes say.
    """
    runtime: Runtime = ctx.obj
    said = {
        "label": label,
        "notes": notes,
        "breaking": breaking or None,
        "acknowledge_breaking": acknowledge_breaking or None,
    }
    body = PublishRequest(**{key: value for key, value in said.items() if value is not None})
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="published")
        was_published = repository.published_at is not None
        published = client.call(
            PUBLISH_REPOSITORY,
            path={"tenant_id": repository.id},
            body=body if body.model_fields_set else None,
        ).value
    if as_json:
        typer.echo(published.model_dump_json(indent=2))
        return
    release = published.release
    flag = " It is marked breaking." if release.breaking else ""
    if was_published:
        _out.print(
            f"Published release {release.label} of {published.slug}: "
            f"the libraries it is invited to have been told.{flag}"
        )
    else:
        _out.print(
            f"{published.slug} is published as release {release.label}. "
            f"The libraries it is invited to have been told.{flag}"
        )


@repo_app.command("unpublish")
def repo_unpublish(
    ctx: typer.Context, tenant: RepositoryTenant, as_json: JsonOption = False
) -> None:
    """Back to a draft: nobody it is granted to can browse it, copy it or check its updates.

    What they already copied stays theirs.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="unpublished")
        withdrawn = client.call(UNPUBLISH_REPOSITORY, path={"tenant_id": repository.id}).value
    if as_json:
        typer.echo(withdrawn.model_dump_json(indent=2))
        return
    _out.print(f"{withdrawn.slug} is a draft again. Copies tenants already made stay theirs.")


@repo_app.command("grant")
def repo_grant(
    ctx: typer.Context,
    subscriber: Annotated[
        str,
        typer.Argument(help="The tenant to give access to: its id, or its slug if it is yours."),
    ],
    tenant: RepositoryTenant,
    as_json: JsonOption = False,
) -> None:
    """Give a tenant access to a repository. Only its owners can; the tenant's members are told.

    A tenant that isn't yours can only be named by its id, which its members can give you.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="granted")
        subscriber_id = repos.resolve_subscriber_to_grant(client, subscriber)
        reply = client.call(
            GRANT_REPOSITORY,
            path={"tenant_id": repository.id, "subscriber_tenant_id": subscriber_id},
        )
    granted = reply.value
    if as_json:
        typer.echo(granted.model_dump_json(indent=2))
        return
    if reply.status != 201:
        _out.print(f"{granted.slug} already had access to {repository.slug}.")
        return
    _out.print(f"Granted {repository.slug} to {granted.slug}; its members have been told.")
    if repository.published_at is None:
        _out.print(
            f"It isn't published yet, so nothing is visible to them: "
            f"lorenzo repo publish --tenant {repository.slug}"
        )


@repo_app.command("revoke")
def repo_revoke(
    ctx: typer.Context,
    subscriber: Annotated[str, typer.Argument(help="The tenant: its id or slug, as listed.")],
    tenant: RepositoryTenant,
    as_json: JsonOption = False,
) -> None:
    """Take a tenant's access back. What it already copied stays its own."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="revoked")
        held = repos.resolve_subscriber_to_revoke(client, repository.id, subscriber)
        client.call(
            REVOKE_REPOSITORY,
            path={"tenant_id": repository.id, "subscriber_tenant_id": held.tenant_id},
        )
    if as_json:
        _echo_json({"revoked": held.model_dump(mode="json")})
        return
    _out.print(f"{held.slug} can no longer reach {repository.slug}. What it copied stays its own.")


@repo_app.command("subscribers")
def repo_subscribers(
    ctx: typer.Context, tenant: RepositoryTenant, as_json: JsonOption = False
) -> None:
    """List the tenants a repository is granted to, with each one's id."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="granted")
        rows = repos.list_subscribers(client, repository.id)
    if as_json:
        _echo_json([row.model_dump(mode="json") for row in rows])
        return
    repo_report.print_subscribers(_out, rows)


@repo_app.command("contents")
def repo_contents(
    ctx: typer.Context, tenant: RepositoryTenant, as_json: JsonOption = False
) -> None:
    """Show what a repository holds and how much of each seed layer it has.

    Whether it is published and who it is granted to, which repositories it is built on, how many
    stat groups, stat definitions and items it holds, how much of each layer of the seed is in it
    (its categories and the attachments it has), and what the seed doesn't name.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="inspected")
        contents = read_contents(client, repository, load_builtin())
    if as_json:
        _echo_json(repo_report.contents_json(contents))
        return
    repo_report.print_contents(_out, contents)


@repo_app.command("list")
def repo_list(ctx: typer.Context, tenant: DrawingTenant, as_json: JsonOption = False) -> None:
    """List the repositories granted to a tenant or copied by it, and whether any has changed."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        drawing = resolve_tenant(client, tenant)
        rows = repos.list_repositories(client, drawing.id)
    if as_json:
        _echo_json([row.model_dump(mode="json") for row in rows])
        return
    repo_report.print_repositories(_out, rows, drawing.slug)


@repo_app.command("copy-plan")
def repo_copy_plan(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    as_json: JsonOption = False,
) -> None:
    """Say what copying a repository into a tenant would do, and write nothing.

    Exit codes: 0 the copy could go ahead as it stands, 2 it needs a choice for some names, 1 it
    would be refused (not granted, not published, or already copied).
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        plan = client.call(
            PLAN_REPOSITORY_COPY, path={"tenant_id": drawing.id, "repository_id": repository_id}
        ).value
    code = repos.copy_plan_exit_code(plan, repository_id)
    if as_json:
        typer.echo(plan.model_dump_json(indent=2))
        raise typer.Exit(code)
    repo_report.print_copy_plan(_out, plan)
    for blocker in repos.copy_plan_blockers(plan, repository_id):
        _out.print(f"[red]{blocker}[/red]")
    if code == 2:
        _out.print(
            "Give a choice for each with `lorenzo repo copy --choices FILE`, or answer them all "
            "with --on-collision merge|skip."
        )
    raise typer.Exit(code)


@repo_app.command("copy")
def repo_copy(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    on_collision: OnCollisionOption = None,
    choices: ChoicesOption = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Do every check and say what would be copied.")
    ] = False,
    again: Annotated[
        Again | None,
        typer.Option(
            "--again",
            help="Copy afresh a repository already copied: keep leaves the earlier copy as the "
            "tenant's own rows, purge deletes what it created and what hangs off it.",
        ),
    ] = None,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Copy a repository into a tenant: its content becomes the tenant's own.

    A name already in use here needs a choice (rename, merge or skip) before anything is written;
    one that has none stops it with nothing copied (exit 2). Exit 1 if it is refused.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        explicit = repos.read_choices(choices) if choices else []
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        name = repos.repository_name(client, drawing, repository_id)
        if not dry_run and not yes:
            if not as_json and again is None:
                plan = client.call(
                    PLAN_REPOSITORY_COPY,
                    path={"tenant_id": drawing.id, "repository_id": repository_id},
                ).value
                repo_report.print_copy_plan(_out, plan)
            prompt = f"Copy {name} into {drawing.slug}?"
            if again == Again.purge:
                prompt = (
                    "This deletes what the earlier copy created, and whatever hangs off it in "
                    f"{drawing.slug}. --dry-run shows how much. Copy {name} afresh?"
                )
            _may_write(runtime, yes=yes, as_json=as_json, prompt=prompt)
        outcome = repos.copy_with_choices(
            client,
            drawing.id,
            repository_id,
            explicit=explicit,
            on_collision=on_collision.value if on_collision else None,
            dry_run=dry_run,
            again=again.value if again else None,
        )
    if isinstance(outcome, repos.NeedsChoices):
        if as_json:
            _echo_json({"open_collisions": [c.model_dump(mode="json") for c in outcome.collisions]})
        else:
            _out.print(
                "Nothing was copied: these names are already in use here, and need a choice."
            )
            repo_report.print_collisions(_out, outcome.collisions)
            _out.print("Use --choices FILE, or --on-collision merge|skip.")
        raise typer.Exit(2)
    if as_json:
        typer.echo(outcome.model_dump_json(indent=2))
        return
    repo_report.print_copy_result(_out, outcome)


@repo_app.command("updates")
def repo_updates(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Take what needs no decision: changes that don't touch your own edits, "
            "additions that collide with nothing, and the attachments that can be applied.",
        ),
    ] = False,
    actions: Annotated[
        Path | None,
        typer.Option(
            "--actions",
            exists=True,
            dir_okay=False,
            help="A JSON file of the API's own actions (apply with keep_local and take_upstream, "
            "add with a resolution, detach), to decide row by row; or "
            '{"actions": [...], "attachments": [...]} to name attachments to add or detach too.',
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="With --apply or --actions: apply it all, then roll back."),
    ] = False,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Show what a copied repository changed since the copy, row by row; or take it.

    Alone it only shows (exit 0 nothing new, 2 there is something). With --apply or --actions it
    writes, in one transaction. A change to something you also changed is never taken without your
    naming it.
    """
    runtime: Runtime = ctx.obj
    if apply and actions is not None:
        raise typer.BadParameter("--apply and --actions can't be used together.")
    if dry_run and not (apply or actions):
        raise typer.BadParameter("--dry-run is for --apply or --actions.")
    writes = (apply or actions is not None) and not dry_run
    with _reporting_errors(), _client(runtime, writes=writes) as client:
        explicit = repos.read_decisions(actions) if actions else None
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        updates = client.call(
            LIST_REPOSITORY_UPDATES,
            path={"tenant_id": drawing.id, "repository_id": repository_id},
        ).value
        if not (apply or actions):
            if as_json:
                typer.echo(updates.model_dump_json(indent=2))
            else:
                name = repos.repository_name(client, drawing, repository_id)
                repo_report.print_updates(_out, name, updates)
                if repos.updates_waiting(updates):
                    _out.print(
                        f"`lorenzo repo updates {repository} --tenant {drawing.slug} --apply` "
                        "takes what needs no decision."
                    )
            raise typer.Exit(2 if repos.updates_waiting(updates) else 0)
        chosen = repos.clean_updates(updates)
        wanted = explicit if explicit is not None else repos.Decisions(chosen.actions, [])
        if not wanted.count:
            result = None
        else:
            if not dry_run and not yes:
                if not as_json:
                    name = repos.repository_name(client, drawing, repository_id)
                    repo_report.print_updates(_out, name, updates)
                _may_write(
                    runtime,
                    yes=yes,
                    as_json=as_json,
                    prompt=f"Take {wanted.count} update(s) into {drawing.slug}?",
                )
            result = repos.apply_updates(
                client,
                drawing.id,
                repository_id,
                wanted.actions,
                dry_run=dry_run,
                attachments=wanted.attachments,
            )
    left = chosen.left and explicit is None
    if as_json:
        _echo_json(
            {
                "result": result.model_dump(mode="json") if result else None,
                "left": {
                    "conflicts": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.conflicts
                    ],
                    "collisions": [
                        {"kind": a.kind.value, "source_id": str(a.source_id), "name": a.name}
                        for a in chosen.collisions
                    ],
                    "breaking": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.breaking
                    ],
                    "edited_since_the_release": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.edited
                    ],
                    "removed": chosen.removed,
                    "attachments_waiting": [
                        {
                            "child_source_id": str(a.child_source_id),
                            "parent_source_id": str(a.parent_source_id),
                            "reason": a.reason or repo_report.ATTACHMENT_REASON,
                        }
                        for a in chosen.attachments_waiting
                    ],
                    "attachments_removed": chosen.attachments_removed,
                }
                if explicit is None
                else None,
            }
        )
    else:
        if result is None:
            _out.print("Nothing to take that needs no decision.")
        else:
            repo_report.print_applied(_out, result)
        if explicit is None:
            repo_report.print_left_for_a_decision(_out, chosen)
    raise typer.Exit(2 if left else 0)


@repo_app.command("offer")
def repo_offer(
    ctx: typer.Context,
    subscriber: Annotated[
        str,
        typer.Argument(help="The tenant to offer it to: its id, or its slug if it is yours."),
    ],
    tenant: RepositoryTenant,
    on_collision: OnCollisionOption = None,
    choices: ChoicesOption = None,
    apply_updates: Annotated[
        bool,
        typer.Option(
            "--apply-updates",
            help="If the tenant already has a copy, take the updates that need no decision.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Write nothing, the grant included; say what would be done."
        ),
    ] = False,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Offer a repository to a tenant: grant it, then copy it in. Safe to run again.

    For whoever owns the repository and belongs to the tenant. It refuses a repository that isn't
    published, grants (an existing grant is fine), and copies; a tenant that already has a copy is
    a success. Exit 2 if names need a choice, or with --dry-run if there is something to do.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        explicit = repos.read_choices(choices) if choices else []
        repository = resolve_tenant(client, tenant)
        receiving = resolve_tenant(client, subscriber)
        state = repos.read_offer_state(client, repository, receiving)
        if dry_run:
            _offer_dry_run(client, state, apply_updates=apply_updates, as_json=as_json)
            return
        if not as_json:
            repo_report.print_offer_state(_out, state)
        if state.steps or apply_updates:
            _may_write(
                runtime,
                yes=yes,
                as_json=as_json,
                prompt=f"Offer {repository.slug} to {receiving.slug}?",
            )
        result = repos.perform_offer(
            client,
            state,
            explicit=explicit,
            on_collision=on_collision.value if on_collision else None,
            apply_clean_updates=apply_updates,
        )
    if as_json:
        _echo_json(
            {
                "repository": repository.slug,
                "subscriber": receiving.slug,
                "granted": result.granted if not state.granted else "existing",
                "dependencies": result.dependencies,
                "copied": result.copied,
                "copy": result.copy.model_dump(mode="json") if result.copy else None,
                "updates": {
                    "applied": (
                        result.updates_applied.model_dump(mode="json")
                        if result.updates_applied
                        else None
                    ),
                    "waiting": result.updates_waiting,
                },
                "open_collisions": [c.model_dump(mode="json") for c in result.needs_choices],
            }
        )
    else:
        repo_report.print_offer_result(_out, state, result)
    raise typer.Exit(2 if result.needs_choices else 0)


def _offer_dry_run(
    client: LorenzoClient, state: repos.OfferState, *, apply_updates: bool, as_json: bool
) -> None:
    """What an offer would do, read without writing, grant included (ADR 0160)."""
    plan = None
    updates = None
    if state.granted and not state.copied:
        plan = client.call(
            PLAN_REPOSITORY_COPY,
            path={"tenant_id": state.subscriber.id, "repository_id": state.repository.id},
        ).value
    if state.copied and apply_updates:
        updates = client.call(
            LIST_REPOSITORY_UPDATES,
            path={"tenant_id": state.subscriber.id, "repository_id": state.repository.id},
        ).value
    takes = repos.clean_updates(updates).takes if updates is not None else 0
    something = bool(state.steps or takes)
    if as_json:
        _echo_json(
            {
                "dry_run": True,
                "steps": state.steps,
                "dependencies": {
                    d.repository.slug: (
                        "copied"
                        if d.copied
                        else "granted"
                        if d.granted
                        else "unknown"
                        if d.granted is None
                        else "needs-grant"
                    )
                    for d in state.dependencies
                },
                "granted": state.granted,
                "copied": state.copied,
                "collisions": [c.model_dump(mode="json") for c in plan.collisions] if plan else [],
                "clean_updates": takes,
            }
        )
    else:
        repo_report.print_offer_state(_out, state)
        if plan is not None:
            repo_report.print_copy_plan(_out, plan)
        elif not state.granted:
            _out.print("  (The copy can only be planned once the tenant is granted it.)")
        if updates is not None:
            _out.print(f"  updates: {takes} take(s) need no decision.")
        _out.print("Dry run: nothing was written." if something else "Nothing to do.")
    raise typer.Exit(2 if something else 0)


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


@inventory_app.command("import")
def inventory_import(
    ctx: typer.Context,
    file: Annotated[
        Path, typer.Argument(help="The inventory file (Markdown or JSON), or - for stdin.")
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
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    spellings: Annotated[
        Path | None,
        typer.Option(
            "--preprocess", help="A table of other spellings (TOML), added to the built-in one."
        ),
    ] = None,
) -> None:
    """Make the things a file lists, for a character.

    Each line is matched to an item by id, slug, title or a known other spelling, and what matches
    nothing becomes an unsorted item your GM can match later. Nothing is made if any line cannot be
    made as written; with --dry-run nothing is made at all.
    """
    runtime: Runtime = ctx.obj
    text = runtime.stdin.read() if str(file) == "-" else file.read_text("utf-8")
    inventory = parse_inventory(text)
    table = inventory_preprocess.load(spellings)
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        plan = build_plan(client, target, inventory, owner=owner, add=add, table=table)
        for remark in plan.warnings:
            _err.print(f"[yellow]{remark}[/yellow]", highlight=False)
        if plan.problems:
            for remark in plan.problems:
                _err.print(f"[red]{remark}[/red]", highlight=False)
            raise typer.Exit(1)
        _inventory_summary(plan)
        if dry_run or not plan.steps:
            return
        if not yes:
            if not runtime.interactive:
                _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
                raise typer.Exit(1)
            if not typer.confirm("Make these?"):
                raise typer.Exit(1)
        done = apply_inventory(client, plan)
    _out.print(
        f"Made {done.made} ({done.placeholders} unsorted)"
        + (f", moved {done.moved}" if done.moved else "")
        + ".",
        highlight=False,
    )
    for remark in done.failed:
        _err.print(f"[red]{remark}[/red]", highlight=False)
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
    """Write a character's inventory as a file: what they own, where it is, and what is noted."""
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
