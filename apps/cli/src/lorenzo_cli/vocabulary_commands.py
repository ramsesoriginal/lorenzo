"""Vocabulary commands over existing API contracts (ADR 0295)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any
from uuid import UUID

import typer
from pydantic import BaseModel, ValidationError
from rich.table import Table
from rich.text import Text

from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    StatDefinitionCreate,
    StatDefinitionOut,
    StatDefinitionUpdate,
    StatGroupCreate,
    StatGroupOut,
    StatGroupUpdate,
    StatValueType,
    TenantUpdate,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import ScriptError, safe

Tenant = Annotated[
    str, typer.Option("--tenant", "-t", envvar="LORENZO_TENANT", help="Library id or slug.")
]
Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
groups_app = typer.Typer(help="Read, create and edit stat groups.", no_args_is_help=True)
stats_app = typer.Typer(
    help="Read, create and edit stat definitions and their hints.", no_args_is_help=True
)


@contextmanager
def session(
    ctx: typer.Context, tenant: str, *, writes: bool = False
) -> Iterator[tuple[LorenzoClient, UUID]]:
    from lorenzo_cli.main import _client, _reporting_errors

    with _reporting_errors(), _client(ctx.obj, writes=writes) as client:
        try:
            yield client, resolve_tenant(client, tenant).id
        except (ValidationError, ScriptError) as error:
            raise SelfServiceError(str(error)) from error


def vocabulary(client: LorenzoClient, tid: UUID, *, groups: bool = False) -> list[Any]:
    return list(
        all_items(
            client,
            ops.LIST_STAT_GROUPS if groups else ops.LIST_STAT_DEFINITIONS,
            path={"tenant_id": tid},
            of=StatGroupOut if groups else StatDefinitionOut,
        )
    )


def resolve(rows: list[Any], reference: str, kind: str) -> UUID:
    # IDs are passed through; the API checks that they belong to this tenant.
    try:
        return UUID(reference)
    except ValueError:
        pass
    found = [r for r in rows if r.name.casefold() == reference.casefold()]
    if len(found) == 1:
        return UUID(str(found[0].id))
    if not found:
        raise SelfServiceError(
            f"No {kind} called “{reference}” here. Use its list command to find it."
        )
    candidates = "".join(f"\n  {r.name}  {r.id}" for r in found)
    raise SelfServiceError(
        f"More than one {kind} matches “{reference}”; name it by id.{candidates}"
    )


def output(value: BaseModel | list[Any], as_json: bool) -> None:
    from lorenzo_cli.main import _out

    if as_json:
        typer.echo(
            json.dumps([r.model_dump(mode="json") for r in value], indent=2)
            if isinstance(value, list)
            else value.model_dump_json(indent=2)
        )
    elif isinstance(value, list):
        table = Table("name", "id", box=None)
        for row in value:
            table.add_row(Text(safe(row.name)), str(row.id))
        _out.print(table if value else Text("Nothing defined yet."))
    else:
        # Plain Text protects user-authored names from Rich markup interpretation.
        _out.print(Text(safe(value.model_dump_json(indent=2))))


def changes(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def nullable(data: dict[str, Any], key: str, value: Any, clear: bool) -> None:
    if clear and value is not None:
        raise SelfServiceError(f"Choose either setting or clearing {key.replace('_', ' ')}.")
    if clear:
        data[key] = None
    elif value is not None:
        data[key] = value


def hints(
    client: LorenzoClient,
    tid: UUID,
    data: dict[str, Any],
    maximum: str | None,
    minimum: str | None,
    resolved: str | None,
    clear_max: bool = False,
    clear_min: bool = False,
    clear_resolved: bool = False,
) -> None:
    rows = vocabulary(client, tid) if any((maximum, minimum, resolved)) else []
    for key, ref, clear in [
        ("max_hint_id", maximum, clear_max),
        ("min_hint_id", minimum, clear_min),
        ("resolved_hint_id", resolved, clear_resolved),
    ]:
        nullable(data, key, resolve(rows, ref, "stat") if ref is not None else None, clear)


@groups_app.command("list")
def group_list(ctx: typer.Context, tenant: Tenant, as_json: Json = False) -> None:
    with session(ctx, tenant) as (client, tid):
        output(vocabulary(client, tid, groups=True), as_json)


@stats_app.command("list")
def stat_list(ctx: typer.Context, tenant: Tenant, as_json: Json = False) -> None:
    with session(ctx, tenant) as (client, tid):
        output(vocabulary(client, tid), as_json)


@groups_app.command("create")
def group_create(
    ctx: typer.Context,
    name: str,
    tenant: Tenant,
    priority: int = 0,
    mandatory: bool = False,
    position: int | None = None,
    as_json: Json = False,
) -> None:
    with session(ctx, tenant, writes=True) as (client, tid):
        body = StatGroupCreate(
            **changes(name=name, priority=priority, mandatory=mandatory, position=position)
        )
        output(
            client.call(ops.CREATE_STAT_GROUP, path={"tenant_id": tid}, body=body).value, as_json
        )


@groups_app.command("edit")
def group_edit(
    ctx: typer.Context,
    group: str,
    tenant: Tenant,
    name: str | None = None,
    priority: int | None = None,
    mandatory: Annotated[bool | None, typer.Option("--mandatory/--no-mandatory")] = None,
    position: int | None = None,
    as_json: Json = False,
) -> None:
    with session(ctx, tenant, writes=True) as (client, tid):
        data = changes(name=name, priority=priority, mandatory=mandatory, position=position)
        if not data:
            raise SelfServiceError("Name at least one field to edit.")
        gid = resolve(vocabulary(client, tid, groups=True), group, "stat group")
        output(
            client.call(
                ops.UPDATE_STAT_GROUP,
                path={"tenant_id": tid, "stat_group_id": gid},
                body=StatGroupUpdate(**data),
            ).value,
            as_json,
        )


@stats_app.command("create")
def stat_create(
    ctx: typer.Context,
    name: str,
    tenant: Tenant,
    group: Annotated[str, typer.Option("--group", help="Stat group id or exact name.")],
    value_type: Annotated[StatValueType, typer.Option("--type")],
    enum_value: Annotated[list[str] | None, typer.Option("--enum-value")] = None,
    unit: str | None = None,
    adjustable_in_play: bool = False,
    pin: bool = False,
    signed: bool = False,
    position: int | None = None,
    max_hint: str | None = None,
    min_hint: str | None = None,
    resolved_hint: str | None = None,
    as_json: Json = False,
) -> None:
    with session(ctx, tenant, writes=True) as (client, tid):
        gid = resolve(vocabulary(client, tid, groups=True), group, "stat group")
        data = changes(
            name=name,
            stat_group_id=gid,
            value_type=value_type,
            enum_values=enum_value,
            unit=unit,
            adjustable_in_play=adjustable_in_play,
            pin=pin,
            signed=signed,
            position=position,
        )
        hints(client, tid, data, max_hint, min_hint, resolved_hint)
        output(
            client.call(
                ops.CREATE_STAT_DEFINITION,
                path={"tenant_id": tid},
                body=StatDefinitionCreate(**data),
            ).value,
            as_json,
        )


@stats_app.command("edit")
def stat_edit(
    ctx: typer.Context,
    stat: str,
    tenant: Tenant,
    unit: str | None = None,
    clear_unit: bool = False,
    adjustable_in_play: Annotated[
        bool | None, typer.Option("--adjustable-in-play/--no-adjustable-in-play")
    ] = None,
    pin: Annotated[bool | None, typer.Option("--pin/--no-pin")] = None,
    signed: Annotated[bool | None, typer.Option("--signed/--no-signed")] = None,
    position: int | None = None,
    max_hint: str | None = None,
    min_hint: str | None = None,
    resolved_hint: str | None = None,
    clear_max_hint: bool = False,
    clear_min_hint: bool = False,
    clear_resolved_hint: bool = False,
    as_json: Json = False,
) -> None:
    """Edit display fields and hints. Name, type and group are fixed by the API."""
    with session(ctx, tenant, writes=True) as (client, tid):
        data = changes(
            adjustable_in_play=adjustable_in_play, pin=pin, signed=signed, position=position
        )
        nullable(data, "unit", unit, clear_unit)
        hints(
            client,
            tid,
            data,
            max_hint,
            min_hint,
            resolved_hint,
            clear_max_hint,
            clear_min_hint,
            clear_resolved_hint,
        )
        if not data:
            raise SelfServiceError("Name at least one field to edit.")
        sid = resolve(vocabulary(client, tid), stat, "stat")
        output(
            client.call(
                ops.UPDATE_STAT_DEFINITION,
                path={"tenant_id": tid, "stat_definition_id": sid},
                body=StatDefinitionUpdate(**data),
            ).value,
            as_json,
        )


def sheet_settings(
    ctx: typer.Context,
    tenant: str,
    being_stat_group: str | None = None,
    clear_being_stat_group: bool = False,
    weapon_stat_group: str | None = None,
    clear_weapon_stat_group: bool = False,
    ability_information_type: str | None = None,
    clear_ability_information_type: bool = False,
    as_json: Json = False,
) -> None:
    """Read the tenant sheet settings, or set or clear individual selections."""
    writes = any(
        (
            being_stat_group is not None,
            clear_being_stat_group,
            weapon_stat_group is not None,
            clear_weapon_stat_group,
            ability_information_type is not None,
            clear_ability_information_type,
        )
    )
    with session(ctx, tenant, writes=writes) as (client, tid):
        data: dict[str, Any] = {}
        gid = (
            resolve(vocabulary(client, tid, groups=True), weapon_stat_group, "stat group")
            if weapon_stat_group is not None
            else None
        )
        being_gid = (
            resolve(vocabulary(client, tid, groups=True), being_stat_group, "stat group")
            if being_stat_group is not None
            else None
        )
        nullable(data, "being_stat_group_id", being_gid, clear_being_stat_group)
        nullable(data, "weapon_stat_group_id", gid, clear_weapon_stat_group)
        nullable(
            data,
            "ability_information_type",
            ability_information_type,
            clear_ability_information_type,
        )
        found = (
            client.call(ops.UPDATE_TENANT, path={"tenant_id": tid}, body=TenantUpdate(**data)).value
            if data
            else client.call(ops.GET_TENANT, path={"tenant_id": tid}).value
        )
        if as_json:
            typer.echo(
                json.dumps(
                    {
                        "being_stat_group_id": str(found.being_stat_group_id)
                        if found.being_stat_group_id
                        else None,
                        "weapon_stat_group_id": str(found.weapon_stat_group_id)
                        if found.weapon_stat_group_id
                        else None,
                        "ability_information_type": found.ability_information_type,
                    },
                    indent=2,
                )
            )
        else:
            from lorenzo_cli.main import _out

            _out.print(
                Text(
                    f"Being stat group: {found.being_stat_group_id or 'not set'}\n"
                    f"Weapon stat group: {found.weapon_stat_group_id or 'not set'}\n"
                    f"Ability information type: {found.ability_information_type or 'not set'}"
                )
            )


def register(app: typer.Typer, tenant_app: typer.Typer) -> None:
    app.add_typer(groups_app, name="stat-group")
    app.add_typer(stats_app, name="stat-definition")
    tenant_app.command("sheet-settings")(sheet_settings)
