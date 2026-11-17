"""`lorenzo pack give` (ADR 0150)."""

from __future__ import annotations

from typing import Annotated

import typer

from lorenzo_cli import console
from lorenzo_cli.importer.give import (
    count_instances,
    give_pack,
    tree_lines,
)
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _out,
    _reporting_errors,
    may_write,
)
from lorenzo_cli.tenants import (
    resolve_tenant,
)

app = typer.Typer(help="Hand out an imported pack.", no_args_is_help=True)
pack_app = app


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
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before handing it out.")] = False,
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
        if not dry_run:
            may_write(runtime, yes=yes, question=f"Give {pack} to {owner}?", default=True)
        given = give_pack(client, target.id, pack, owner, override=override, dry_run=dry_run)
    if as_json:
        console.emit(given.model_dump(mode="json"))
        return
    for line in tree_lines(given):
        _out.print(line, highlight=False)
    verb = "Would give" if dry_run else "Gave"
    _out.print(f"{verb} {count_instances(given)} item(s).")
