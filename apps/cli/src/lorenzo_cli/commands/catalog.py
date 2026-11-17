"""`lorenzo item` and `lorenzo character` (ADR 0190, 0295)."""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.table import Table

from lorenzo_cli import entry_commands
from lorenzo_cli.commands.common import ItemTenant
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _out,
    _reporting_errors,
)
from lorenzo_cli.self_service import (
    add_item,
    catalog,
    characters,
    resolve_container,
    resolve_item,
    resolve_owner,
)
from lorenzo_cli.tenants import (
    resolve_tenant,
)

item_app = typer.Typer(
    help="Find the items you may add, add one, or read one.", no_args_is_help=True
)
character_app = typer.Typer(help="List characters.", no_args_is_help=True)


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


item_app.command("show")(entry_commands.item_show)
