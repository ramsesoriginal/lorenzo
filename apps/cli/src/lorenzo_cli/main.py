"""The `lorenzo` command line (ADR 0137); commands arrive with the RFC 0025 slices."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
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
from lorenzo_cli.tenants import TenantNotFoundError, resolve_tenant

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
