"""`lorenzo campaign` (ADR 0487): list, create, and the system a campaign plays, which picks the
templates its beings' sheets are read through (ADR 0452)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import typer
from rich.table import Table
from rich.text import Text

from lorenzo_cli import completers, console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    CampaignCreate,
    CampaignSummaryOut,
    CampaignUpdate,
    SystemOut,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.runtime import _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

app = typer.Typer(
    help="List or create campaigns, and set the system one plays.", no_args_is_help=True
)

Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
Yes = Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")]


def systems(client: LorenzoClient, tid: UUID) -> dict[str, SystemOut]:
    rows = all_items(client, ops.LIST_SYSTEMS, path={"tenant_id": tid}, of=SystemOut)
    return {s.slug: s for s in rows}


def find_system(client: LorenzoClient, tid: UUID, slug: str) -> SystemOut:
    found = systems(client, tid).get(slug.lower())
    if found is None:
        raise SelfServiceError(f"No system {slug} here: `lorenzo system list` names them.")
    return found


def campaigns(client: LorenzoClient, tid: UUID) -> list[CampaignSummaryOut]:
    return list(
        all_items(client, ops.LIST_CAMPAIGNS, path={"tenant_id": tid}, of=CampaignSummaryOut)
    )


def find(client: LorenzoClient, tid: UUID, reference: str) -> CampaignSummaryOut:
    rows = campaigns(client, tid)
    found = [
        c
        for c in rows
        if reference in (str(c.id), c.slug) or c.name.casefold() == reference.casefold()
    ]
    if len(found) == 1:
        return found[0]
    if not found:
        raise SelfServiceError(f"No campaign {reference} here: `lorenzo campaign list` names them.")
    raise SelfServiceError(f"More than one campaign matches {reference}; name it by slug.")


@app.command("list")
def campaign_list(ctx: typer.Context, tenant: TenantOption, as_json: Json = False) -> None:
    """The library's campaigns, with the system each plays."""
    with _reporting_errors(), _client(ctx.obj) as client:
        tid = resolve_tenant(client, tenant).id
        rows = campaigns(client, tid)
        by_id = {s.id: s.slug for s in systems(client, tid).values()}
    if as_json:
        console.emit({"campaigns": [r.model_dump(mode="json") for r in rows]})
        return
    if not rows:
        console.out.print("No campaigns yet: `lorenzo campaign create NAME --slug SLUG`.")
        return
    table = Table("slug", "name", "system", box=None, pad_edge=False)
    for row in rows:
        table.add_row(
            row.slug, Text(safe(row.name)), by_id.get(row.system_id, "") if row.system_id else ""
        )
    console.out.print(table)


@app.command("create")
def campaign_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="What it is called.")],
    tenant: TenantOption,
    slug: Annotated[str, typer.Option("--slug", help="Its address.")],
    system: Annotated[
        str | None,
        typer.Option("--system", help="The system it plays.", autocompletion=completers.system),
    ] = None,
    description: Annotated[str, typer.Option("--description")] = "",
    secret: Annotated[
        bool, typer.Option("--secret", help="Hidden from the library's players.")
    ] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Create a campaign, playing a system if one is named."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        tid = resolve_tenant(client, tenant).id
        chosen = find_system(client, tid, system) if system else None
        playing = f", playing {chosen.slug}" if chosen else ""
        may_write(ctx.obj, yes=yes, question=f"Create the campaign {name}{playing}?", default=True)
        made = client.call(
            ops.CREATE_CAMPAIGN,
            path={"tenant_id": tid},
            body=CampaignCreate(
                name=name,
                slug=slug,
                description=description,
                secret=secret,
                system_id=chosen.id if chosen else None,
                # The free-text field a campaign has always had; the system's name fills it.
                game_system=chosen.name if chosen else "",
            ),
        ).value
    if as_json:
        console.emit(made.model_dump(mode="json"))
    else:
        console.out.print(console.status("done", f"created {made.slug}{playing}."))


@app.command("set-system")
def campaign_set_system(
    ctx: typer.Context,
    campaign: Annotated[
        str,
        typer.Argument(
            help="The campaign: its slug, name or id.", autocompletion=completers.campaign
        ),
    ],
    tenant: TenantOption,
    system: Annotated[
        str | None, typer.Argument(help="The system's slug.", autocompletion=completers.system)
    ] = None,
    none: Annotated[bool, typer.Option("--none", help="Play no system.")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Set the system a campaign plays, or none: its beings' sheets follow its templates."""
    if (system is None) == (not none):
        raise typer.BadParameter("Name a system, or --none.")
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        tid = resolve_tenant(client, tenant).id
        found = find(client, tid, campaign)
        chosen = find_system(client, tid, system) if system else None
        said = chosen.slug if chosen else "no system"
        may_write(ctx.obj, yes=yes, question=f"Make {found.slug} play {said}?", default=True)
        changes: dict[str, Any] = {"system_id": chosen.id if chosen else None}
        if chosen is not None:
            changes["game_system"] = chosen.name
        edited = client.call(
            ops.UPDATE_CAMPAIGN,
            path={"tenant_id": tid, "campaign_id": found.id},
            body=CampaignUpdate(**changes),
        ).value
    if as_json:
        console.emit(edited.model_dump(mode="json"))
    else:
        console.out.print(console.status("done", f"{edited.slug} plays {said}."))
