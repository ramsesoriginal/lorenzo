"""`lorenzo tenant`: list, read, create and delete a tenant (ADR 0033, 0175, 0184)."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from lorenzo_cli import console, vocabulary_commands
from lorenzo_cli.client.errors import (
    LorenzoApiError,
)
from lorenzo_cli.client.models import (
    TenantCreate,
    TenantKind,
    TenantOut,
    TenantSummaryOut,
)
from lorenzo_cli.client.ops import (
    CREATE_TENANT,
    DELETE_TENANT,
    LIST_TENANTS,
)
from lorenzo_cli.client.paging import all_items
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

app = typer.Typer(help="List, read, create or delete a tenant.", no_args_is_help=True)
tenant_app = app


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
        console.emit(found.model_dump(mode="json"))
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
        console.emit({"tenants": [row.model_dump(mode="json") for row in rows]})
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
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before creating it.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the tenant as JSON.")] = False,
) -> None:
    """Create a tenant, a repository unless told otherwise, and become its owner.

    Needs the tenant-creator role. Then `lorenzo seed --tenant <slug>` makes a repository ready
    to import into.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        body = TenantCreate(name=name, slug=slug, description=description, kind=kind)
        may_write(
            runtime, yes=yes, question=f"Create the {kind.value} tenant {name}?", default=True
        )
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
                console.err.print(
                    console.status("note", "nothing was deleted: run again with --yes to delete."),
                    soft_wrap=True,
                )
                raise typer.Exit(2)
            _print_tenant(found, False)
            console.warning(
                f"this deletes “{found.name}” and everything in it. It can't be undone."
            )
            with console.paused():
                typed = typer.prompt("Type its slug to confirm", err=True).strip()
            if typed != found.slug:
                console.err.print(console.status("note", "nothing was deleted."))
                raise typer.Exit(2)
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
        console.emit(found.model_dump(mode="json"))
    else:
        _out.print(f"Deleted {found.slug} (“{found.name}”).")


tenant_app.command("sheet-settings")(vocabulary_commands.sheet_settings)
