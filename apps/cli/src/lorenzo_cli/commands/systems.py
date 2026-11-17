"""`lorenzo system` (ADR 0485): a library's game systems, one row at a time. A system groups stats
under its slug's prefix, picks a campaign's templates, and names the entry its content descends
from (ADR 0448, ADR 0452)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import typer
from rich.table import Table
from rich.text import Text

from lorenzo_cli import completers, console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    CampaignSummaryOut,
    StatGroupOut,
    SystemOut,
    SystemUpdate,
    TemplateSummaryOut,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.library.document import Document, SystemRow
from lorenzo_cli.library.planner import make_plan
from lorenzo_cli.library.render import print_plan, print_result
from lorenzo_cli.library.state import read
from lorenzo_cli.library.writer import apply as write_plan
from lorenzo_cli.runtime import Runtime, _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

app = typer.Typer(help="List, read, create, edit or delete a game system.", no_args_is_help=True)

Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
Yes = Annotated[bool, typer.Option("--yes", help="Don't ask before writing (ADR 0482).")]
SystemArgument = Annotated[
    str, typer.Argument(help="The system: its slug or id.", autocompletion=completers.system)
]


def _systems(client: LorenzoClient, tid: UUID) -> list[SystemOut]:
    return list(all_items(client, ops.LIST_SYSTEMS, path={"tenant_id": tid}, of=SystemOut))


def find(client: LorenzoClient, tid: UUID, reference: str) -> SystemOut:
    systems = _systems(client, tid)
    found = next(
        (s for s in systems if s.slug == reference.lower() or str(s.id) == reference), None
    )
    if found is None:
        known = ", ".join(s.slug for s in systems) or "none yet"
        raise SelfServiceError(f"No system {reference} here (this library has: {known}).")
    return found


def _users(client: LorenzoClient, tid: UUID, system: SystemOut) -> dict[str, list[str]]:
    """What names the system: its groups, its templates and the campaigns that play it."""
    path = {"tenant_id": tid}
    groups = [
        g.name
        for g in all_items(client, ops.LIST_STAT_GROUPS, path=path, of=StatGroupOut)
        if g.system_id == system.id
    ]
    templates = [
        t.name
        for t in all_items(
            client,
            ops.LIST_TEMPLATES,
            path=path,
            query={"system": system.slug},
            of=TemplateSummaryOut,
        )
        if getattr(t, "system", None) == system.slug
    ]
    campaigns = [
        c.name
        for c in all_items(client, ops.LIST_CAMPAIGNS, path=path, of=CampaignSummaryOut)
        if getattr(c, "system_id", None) == system.id
    ]
    return {"groups": groups, "templates": templates, "campaigns": campaigns}


@app.command("list")
def system_list(ctx: typer.Context, tenant: TenantOption, as_json: Json = False) -> None:
    """The library's systems, with their roots."""
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        systems = _systems(client, target.id)
    if as_json:
        console.emit({"systems": [s.model_dump(mode="json") for s in systems]})
        return
    if not systems:
        console.out.print("No systems yet: `lorenzo system create SLUG NAME`.")
        return
    table = Table("slug", "name", "id", box=None, pad_edge=False)
    for system in systems:
        table.add_row(system.slug, Text(safe(system.name)), str(system.id))
    console.out.print(table)


@app.command("show")
def system_show(
    ctx: typer.Context, system: SystemArgument, tenant: TenantOption, as_json: Json = False
) -> None:
    """A system, and what names it: its stat groups, templates and campaigns."""
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        found = find(client, target.id, system)
        users = _users(client, target.id, found)
    if as_json:
        console.emit({**found.model_dump(mode="json"), **users})
        return
    console.out.print(Text(f"{found.slug}  {safe(found.name)}"))
    console.out.print(f"Root: {found.root_entry_id or 'none'}")
    for what, names in users.items():
        console.out.print(Text(f"{what.capitalize()}: {', '.join(names) if names else 'none'}"))


@app.command("create")
def system_create(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Lowercase letters and digits; its stats' prefix.")],
    name: Annotated[str, typer.Argument(help="What it is called.")],
    tenant: TenantOption,
    root: Annotated[
        str | None, typer.Option("--root", help="The slug of the entry its content descends from.")
    ] = None,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Create a system: a plan of one row through the library document's planner (ADR 0485)."""
    runtime: Runtime = ctx.obj
    with _reporting_errors():
        try:
            doc = Document(format=1, name=slug, system=SystemRow(slug=slug, name=name, root=root))
        except ValueError as exc:
            raise SelfServiceError(
                f"{slug}: a system's slug is lowercase letters and digits, starting with a "
                "letter, 32 at most."
            ) from exc
        with _client(runtime, writes=True) as client:
            target = resolve_tenant(client, tenant)
            state = read(client, target)
            plan = make_plan(doc, state)
            if plan.problems or not plan.actions:
                print_plan(plan)
                raise typer.Exit(plan.exit_code())
            may_write(
                runtime, yes=yes, question=f"Create the system {slug} ({name})?", default=True
            )
            result = write_plan(client, plan, state)
            if result.failed:
                print_result(result)
                raise typer.Exit(1)
            made = find(client, target.id, slug)
    if as_json:
        console.emit(made.model_dump(mode="json"))
    else:
        console.out.print(console.status("done", f"created {made.slug} ({made.name})."))


@app.command("edit")
def system_edit(
    ctx: typer.Context,
    system: SystemArgument,
    tenant: TenantOption,
    name: Annotated[str | None, typer.Option("--name")] = None,
    slug: Annotated[
        str | None, typer.Option("--slug", help="A new slug; refused while a group uses it.")
    ] = None,
    root: Annotated[str | None, typer.Option("--root", help="The root entry's slug.")] = None,
    clear_root: Annotated[bool, typer.Option("--clear-root")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Change a system's name, slug or root; only what is named changes."""
    runtime: Runtime = ctx.obj
    if root is not None and clear_root:
        raise typer.BadParameter("Choose either --root or --clear-root.")
    with _reporting_errors(), _client(runtime, writes=True) as client:
        target = resolve_tenant(client, tenant)
        found = find(client, target.id, system)
        changes: dict[str, Any] = {}
        if name is not None:
            changes["name"] = name
        if slug is not None and slug != found.slug:
            groups = _users(client, target.id, found)["groups"]
            if groups:
                raise SelfServiceError(
                    f"{found.slug} can't take a new slug while groups use it: {', '.join(groups)}."
                )
            changes["slug"] = slug
        if clear_root:
            changes["root_entry_id"] = None
        elif root is not None:
            entry = client.call(
                ops.GET_ENTITY_BY_SLUG, path={"tenant_id": target.id, "slug": root}
            ).value
            changes["root_entry_id"] = entry.id
        if not changes:
            raise SelfServiceError("Name at least one thing to change.")
        said = ", ".join("root" if k == "root_entry_id" else k for k in changes)
        may_write(runtime, yes=yes, question=f"Change {said} of {found.slug}?", default=True)
        edited = client.call(
            ops.UPDATE_SYSTEM,
            path={"tenant_id": target.id, "system_id": found.id},
            body=SystemUpdate(**changes),
        ).value
    if as_json:
        console.emit(edited.model_dump(mode="json"))
    else:
        console.out.print(console.status("done", f"changed {said} of {edited.slug}."))


@app.command("delete")
def system_delete(
    ctx: typer.Context, system: SystemArgument, tenant: TenantOption, yes: Yes = False
) -> None:
    """Delete a system nothing names any more. A group, template or campaign that uses it is
    named first, and the API refuses while one does."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        target = resolve_tenant(client, tenant)
        found = find(client, target.id, system)
        users = {k: v for k, v in _users(client, target.id, found).items() if v}
        if users:
            said = "; ".join(f"{k}: {', '.join(v)}" for k, v in users.items())
            raise SelfServiceError(f"{found.slug} is still used ({said}).")
        may_write(runtime, yes=yes, question=f"Delete the system {found.slug}?")
        client.call(ops.DELETE_SYSTEM, path={"tenant_id": target.id, "system_id": found.id})
    console.out.print(console.status("done", f"deleted {found.slug}."))
