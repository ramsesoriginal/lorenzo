"""The `lorenzo` command line (ADR 0137). Each command group is a module of its own, imported only
when it is run or its own help is shown, so `--version`, `--help` and a completion load none of
them (ADR 0483)."""

from __future__ import annotations

import importlib.metadata
from typing import Annotated

import typer
from typer import _click as click  # typer vendors its own click; its classes are these

from lorenzo_cli import console
from lorenzo_cli.lazy import Entry, LazyGroup
from lorenzo_cli.runtime import Runtime, default_runtime

_C = "lorenzo_cli.commands."
COMMANDS: dict[str, Entry] = {
    "login": Entry(f"{_C}account", "app", "Sign in and store the login.", "login"),
    "logout": Entry(f"{_C}account", "app", "Forget the stored login.", "logout"),
    "whoami": Entry(f"{_C}account", "app", "Ask the API who your token belongs to.", "whoami"),
    "legal": Entry(
        f"{_C}account", "app", "Where the legal notice and privacy policy are.", "legal"
    ),
    "tenant": Entry(f"{_C}tenant", "app", "List, read, create or delete a tenant."),
    "stat-group": Entry(
        "lorenzo_cli.vocabulary_commands", "groups_app", "Read, create and edit stat groups."
    ),
    "stat-definition": Entry(
        "lorenzo_cli.vocabulary_commands",
        "stats_app",
        "Read, create and edit stat definitions and their hints.",
    ),
    "item": Entry(f"{_C}catalog", "item_app", "Find the items you may add, add one, or read one."),
    "item-instance": Entry("lorenzo_cli.entry_commands", "instance_app", "Read item instances."),
    "being": Entry("lorenzo_cli.entry_commands", "being_app", "Read beings and their sheets."),
    "character": Entry(f"{_C}catalog", "character_app", "List characters."),
    "pack": Entry(f"{_C}pack", "app", "Hand out an imported pack."),
    "seed": Entry(f"{_C}seeding", "app", "Create the item taxonomy and stats in a tenant.", "seed"),
    "unseed": Entry(f"{_C}seeding", "app", "Take a layer of the seed out of a tenant.", "unseed"),
    "import": Entry(
        f"{_C}transfer", "import_app", "Import MPMB items, an inventory or a calendar."
    ),
    "export": Entry(f"{_C}transfer", "export_app", "Export an inventory or a calendar."),
    "repo": Entry(f"{_C}repo", "app", "Publish, grant, copy and update repositories."),
    "api": Entry(f"{_C}api", "app", "Make one authenticated request to the API.", "api"),
}


class RootGroup(LazyGroup):
    """`lorenzo` itself: a lazy group that also sets the console up for each run."""

    registry = COMMANDS

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Every run starts from the console's defaults; `--json` anywhere on the line makes this a
        # run whose stdout is one document, which the console needs before any command code runs.
        console.reset()
        console.configure(json="--json" in args)
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="lorenzo",
    cls=RootGroup,
    help="The Lorenzo command line.",
    epilog="The legal notice and the privacy policy of the Lorenzo you use: `lorenzo legal`.",
    no_args_is_help=True,
    add_completion=True,
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
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet", "-q", help="Print the result only: no notices and no progress (ADR 0481)."
        ),
    ] = False,
    no_progress: Annotated[
        bool, typer.Option("--no-progress", help="Show waits as plain lines, without animation.")
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    console.configure(quiet=quiet, no_progress=no_progress)
    if ctx.obj is None:
        ctx.obj = default_runtime()
    runtime: Runtime = ctx.obj
    if api_url is not None:
        runtime.api_url = api_url
    if token_stdin:
        runtime.token_stdin = True


__all__ = ["COMMANDS", "Runtime", "app"]
