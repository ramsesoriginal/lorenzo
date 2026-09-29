"""The `lorenzo` command line (ADR 0137); commands arrive with the RFC 0025 slices."""

from __future__ import annotations

import json
import os
import sys
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
from lorenzo_cli.report import print_evaluation, print_seed_plan, seed_plan_json
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

_out = Console()
_err = Console(stderr=True)


@dataclass
class Runtime:
    """What a command runs against. Tests hand one in instead of the real environment."""

    env: Mapping[str, str]
    stdin: TextIO
    store: CredentialsFile
    transport: httpx.BaseTransport | None = None
    # Evaluates MPMB files; the worker subprocess unless a test hands in another.
    engine: Engine = field(default_factory=WorkerEngine)
    api_url: str | None = None
    token_stdin: bool = False

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
            if not runtime.stdin.isatty():
                _err.print("[red]Not asking anything here: run again with --yes to write.[/red]")
                raise typer.Exit(1)
            if not typer.confirm("Create these?"):
                raise typer.Exit(1)
        apply_plan(client, spec, plan, state)
    if not as_json:
        _out.print(
            f"Created {len(plan.actions)}. Run it again to check: it should find nothing to do."
        )
