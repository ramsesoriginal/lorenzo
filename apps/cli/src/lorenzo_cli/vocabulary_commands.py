"""Vocabulary commands over existing API contracts (ADR 0295)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any
from uuid import UUID

import typer
from pydantic import BaseModel, ValidationError
from rich.table import Table
from rich.text import Text

from lorenzo_cli import completers, console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    StatDefinitionCreate,
    StatDefinitionOut,
    StatDefinitionUpdate,
    StatGroupCreate,
    StatGroupOut,
    StatGroupUpdate,
    StatValueType,
    SystemOut,
    TenantUpdate,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import ScriptError, safe

Tenant = Annotated[
    str,
    typer.Option(
        "--tenant",
        "-t",
        envvar="LORENZO_TENANT",
        autocompletion=completers.library,
        help="Library id or slug.",
    ),
]
Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
Yes = Annotated[bool, typer.Option("--yes", help="Don't ask before writing (ADR 0496).")]
groups_app = typer.Typer(help="Read, create and edit stat groups.", no_args_is_help=True)
stats_app = typer.Typer(
    help="Read, create and edit stat definitions and their hints.", no_args_is_help=True
)


@contextmanager
def session(
    ctx: typer.Context, tenant: str, *, writes: bool = False
) -> Iterator[tuple[LorenzoClient, UUID]]:
    from lorenzo_cli.runtime import _client, _reporting_errors

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


GroupRoleOption = Annotated[
    str | None,
    typer.Option("--role", help="physical, economic, destroyable, damaging or tags (ADR 0449)."),
]
StatRoleOption = Annotated[
    str | None,
    typer.Option("--role", help="What the API reads it for: weight, price, armor... (ADR 0449)."),
]
SystemOption = Annotated[
    str | None,
    typer.Option(
        "--system",
        help="A system's slug: only its rows and the neutral ones.",
        autocompletion=completers.system,
    ),
]
NeutralOption = Annotated[bool, typer.Option("--neutral", help="Only the rows of no system.")]


def systems(client: LorenzoClient, tid: UUID) -> dict[UUID, SystemOut]:
    return {
        s.id: s for s in all_items(client, ops.LIST_SYSTEMS, path={"tenant_id": tid}, of=SystemOut)
    }


def system_id(client: LorenzoClient, tid: UUID, slug: str) -> UUID:
    found = next((s for s in systems(client, tid).values() if s.slug == slug.lower()), None)
    if found is None:
        raise SelfServiceError(f"No system {slug} here: `lorenzo system list` names them.")
    return found.id


def _plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _bounds(row: StatDefinitionOut) -> str:
    if row.min_value is None and row.max_value is None:
        return ""
    low = "" if row.min_value is None else f"{row.min_value:g}"
    high = "" if row.max_value is None else f"{row.max_value:g}"
    return f"{low}..{high}"


def output(value: BaseModel | list[Any], as_json: bool, key: str = "rows") -> None:
    from lorenzo_cli.runtime import _out

    if as_json:
        console.emit(
            {key: [r.model_dump(mode="json") for r in value]}
            if isinstance(value, list)
            else value.model_dump(mode="json")
        )
    elif isinstance(value, list):
        table = Table("name", "id", box=None)
        for row in value:
            table.add_row(Text(safe(row.name)), str(row.id))
        _out.print(table if value else Text("Nothing defined yet."))
    else:
        # Plain Text protects user-authored names from Rich markup interpretation.
        _out.print(Text(safe(value.model_dump_json(indent=2))))


def ask(ctx: typer.Context, yes: bool, question: str, *, default: bool = True) -> None:
    """One row to write: asked at a terminal, default yes (ADR 0496)."""
    from lorenzo_cli.runtime import may_write

    may_write(ctx.obj, yes=yes, question=question, default=default)


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


def _keep(group: StatGroupOut, wanted: UUID | None, neutral: bool) -> bool:
    if neutral:
        return group.system_id is None
    return wanted is None or group.system_id in (None, wanted)


@groups_app.command("list")
def group_list(
    ctx: typer.Context,
    tenant: Tenant,
    system: SystemOption = None,
    neutral: NeutralOption = False,
    as_json: Json = False,
) -> None:
    """The stat groups: name, system, role, priority and how many stats each holds."""
    with session(ctx, tenant) as (client, tid):
        known = systems(client, tid)
        wanted = system_id(client, tid, system) if system else None
        groups = [g for g in vocabulary(client, tid, groups=True) if _keep(g, wanted, neutral)]
        counts = Counter(s.stat_group_id for s in vocabulary(client, tid))
    if as_json:
        console.emit({"stat_groups": [g.model_dump(mode="json") for g in groups]})
        return
    if not groups:
        console.out.print("Nothing defined yet.")
        return
    table = Table("name", "system", "role", "priority", "stats", "id", box=None, pad_edge=False)
    for g in groups:
        sys = known.get(g.system_id) if g.system_id else None
        table.add_row(
            Text(safe(g.name)),
            sys.slug if sys else "",
            _plain(g.role) or "",
            str(g.priority),
            str(counts.get(g.id, 0)),
            str(g.id),
        )
    console.out.print(table)


@stats_app.command("list")
def stat_list(
    ctx: typer.Context,
    tenant: Tenant,
    system: SystemOption = None,
    neutral: NeutralOption = False,
    group: Annotated[
        str | None,
        typer.Option(
            "--group", help="Only this group's stats.", autocompletion=completers.stat_group
        ),
    ] = None,
    as_json: Json = False,
) -> None:
    """The stats: name, group, system, type, unit, role and bounds."""
    with session(ctx, tenant) as (client, tid):
        known = systems(client, tid)
        wanted = system_id(client, tid, system) if system else None
        groups = {g.id: g for g in vocabulary(client, tid, groups=True)}
        only = resolve(list(groups.values()), group, "stat group") if group else None
        stats = [
            s
            for s in vocabulary(client, tid)
            if s.stat_group_id in groups
            and _keep(groups[s.stat_group_id], wanted, neutral)
            and (only is None or s.stat_group_id == only)
        ]
    if as_json:
        console.emit({"stat_definitions": [s.model_dump(mode="json") for s in stats]})
        return
    if not stats:
        console.out.print("Nothing defined yet.")
        return
    table = Table(
        "name", "group", "system", "type", "unit", "role", "bounds", box=None, pad_edge=False
    )
    for s in stats:
        g = groups[s.stat_group_id]
        sys = known.get(g.system_id) if g.system_id else None
        table.add_row(
            Text(safe(s.name)),
            Text(safe(g.name)),
            sys.slug if sys else "",
            s.value_type.value,
            s.unit or "",
            _plain(s.role) or "",
            _bounds(s),
        )
    console.out.print(table)


@groups_app.command("show")
def group_show(ctx: typer.Context, group: str, tenant: Tenant, as_json: Json = False) -> None:
    """A stat group by id or exact name."""
    with session(ctx, tenant) as (client, tid):
        gid = resolve(vocabulary(client, tid, groups=True), group, "stat group")
        found = client.call(ops.GET_STAT_GROUP, path={"tenant_id": tid, "stat_group_id": gid})
        output(found.value, as_json)


@stats_app.command("show")
def stat_show(ctx: typer.Context, stat: str, tenant: Tenant, as_json: Json = False) -> None:
    """A stat by id or exact name."""
    with session(ctx, tenant) as (client, tid):
        sid = resolve(vocabulary(client, tid), stat, "stat")
        found = client.call(
            ops.GET_STAT_DEFINITION, path={"tenant_id": tid, "stat_definition_id": sid}
        )
        output(found.value, as_json)


@groups_app.command("create")
def group_create(
    ctx: typer.Context,
    name: str,
    tenant: Tenant,
    priority: int = 0,
    mandatory: bool = False,
    position: int | None = None,
    system: Annotated[
        str | None,
        typer.Option(
            "--system", help="The system it belongs to, by slug.", autocompletion=completers.system
        ),
    ] = None,
    role: GroupRoleOption = None,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    if system and role:
        raise SelfServiceError("A role is held by a group of no system (ADR 0449).")
    with session(ctx, tenant, writes=True) as (client, tid):
        sid = system_id(client, tid, system) if system else None
        in_system = f" in {system}" if system else ""
        ask(ctx, yes, f"Create the stat group {name}{in_system}?")
        body = StatGroupCreate(
            **changes(
                name=name,
                priority=priority,
                mandatory=mandatory,
                position=position,
                system_id=sid,
                role=role,
            )
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
    system: Annotated[
        str | None,
        typer.Option(
            "--system",
            help="Move it into a system: its stats must have the prefix.",
            autocompletion=completers.system,
        ),
    ] = None,
    no_system: Annotated[bool, typer.Option("--no-system", help="Make it neutral.")] = False,
    role: GroupRoleOption = None,
    clear_role: Annotated[bool, typer.Option("--clear-role")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    with session(ctx, tenant, writes=True) as (client, tid):
        data = changes(name=name, priority=priority, mandatory=mandatory, position=position)
        nullable(data, "role", role, clear_role)
        nullable(data, "system_id", system_id(client, tid, system) if system else None, no_system)
        if not data:
            raise SelfServiceError("Name at least one field to edit.")
        gid = resolve(vocabulary(client, tid, groups=True), group, "stat group")
        if system:
            unprefixed = [
                s.name
                for s in vocabulary(client, tid)
                if s.stat_group_id == gid and not s.name.startswith(f"{system.lower()}_")
            ]
            if unprefixed:
                raise SelfServiceError(
                    f"{group} can join {system} once its stats are named {system.lower()}_...: "
                    f"{', '.join(unprefixed)} are not (ADR 0448)."
                )
        said = ", ".join("system" if k == "system_id" else k for k in data)
        ask(ctx, yes, f"Change {said} of the stat group {group}?")
        output(
            client.call(
                ops.UPDATE_STAT_GROUP,
                path={"tenant_id": tid, "stat_group_id": gid},
                body=StatGroupUpdate(**data),
            ).value,
            as_json,
        )


@groups_app.command("delete")
def group_delete(ctx: typer.Context, group: str, tenant: Tenant, yes: Yes = False) -> None:
    """Delete an empty stat group. The API refuses one that still holds a stat."""
    with session(ctx, tenant, writes=True) as (client, tid):
        gid = resolve(vocabulary(client, tid, groups=True), group, "stat group")
        ask(ctx, yes, f"Delete the stat group {group}?", default=False)
        client.call(ops.DELETE_STAT_GROUP, path={"tenant_id": tid, "stat_group_id": gid})
    console.out.print(console.status("done", f"deleted the stat group {group}."))


@stats_app.command("create")
def stat_create(
    ctx: typer.Context,
    name: str,
    tenant: Tenant,
    group: Annotated[
        str,
        typer.Option(
            "--group", help="Stat group id or exact name.", autocompletion=completers.stat_group
        ),
    ],
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
    role: StatRoleOption = None,
    minimum: Annotated[
        float | None, typer.Option("--min", help="The lowest value it may hold.")
    ] = None,
    maximum: Annotated[
        float | None, typer.Option("--max", help="The highest value it may hold.")
    ] = None,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    if value_type == StatValueType.dice and unit is not None:
        raise SelfServiceError("A dice stat has no unit.")
    if (minimum is not None or maximum is not None) and value_type not in (
        StatValueType.int,
        StatValueType.float,
    ):
        raise SelfServiceError("Only an int or a float stat has bounds.")
    with session(ctx, tenant, writes=True) as (client, tid):
        groups = vocabulary(client, tid, groups=True)
        gid = resolve(groups, group, "stat group")
        chosen = next(g for g in groups if g.id == gid)
        if chosen.system_id is not None:
            sys = systems(client, tid).get(chosen.system_id)
            prefix = f"{sys.slug}_" if sys else ""
            if prefix and not name.startswith(prefix):
                raise SelfServiceError(
                    f"A stat of {chosen.name} ({sys.slug if sys else ''}) is named "
                    f"{prefix}something: {prefix}{name} (ADR 0448)."
                )
            if role:
                raise SelfServiceError("A role is held by a stat of no system (ADR 0449).")
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
            role=role,
            min_value=minimum,
            max_value=maximum,
        )
        hints(client, tid, data, max_hint, min_hint, resolved_hint)
        ask(ctx, yes, f"Create the stat {name} ({value_type.value}) in {group}?")
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
    role: StatRoleOption = None,
    clear_role: Annotated[bool, typer.Option("--clear-role")] = False,
    minimum: Annotated[float | None, typer.Option("--min")] = None,
    maximum: Annotated[float | None, typer.Option("--max")] = None,
    clear_min: Annotated[bool, typer.Option("--clear-min")] = False,
    clear_max: Annotated[bool, typer.Option("--clear-max")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Edit display fields, hints, role and bounds. Name, type and group are fixed by the API."""
    with session(ctx, tenant, writes=True) as (client, tid):
        data = changes(
            adjustable_in_play=adjustable_in_play, pin=pin, signed=signed, position=position
        )
        nullable(data, "unit", unit, clear_unit)
        nullable(data, "role", role, clear_role)
        nullable(data, "min_value", minimum, clear_min)
        nullable(data, "max_value", maximum, clear_max)
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
        ask(ctx, yes, f"Change {', '.join(data)} of the stat {stat}?")
        output(
            client.call(
                ops.UPDATE_STAT_DEFINITION,
                path={"tenant_id": tid, "stat_definition_id": sid},
                body=StatDefinitionUpdate(**data),
            ).value,
            as_json,
        )


@stats_app.command("delete")
def stat_delete(ctx: typer.Context, stat: str, tenant: Tenant, yes: Yes = False) -> None:
    """Delete a stat nothing uses. The API refuses one with a value, a formula or a reader."""
    with session(ctx, tenant, writes=True) as (client, tid):
        sid = resolve(vocabulary(client, tid), stat, "stat")
        ask(ctx, yes, f"Delete the stat {stat}? It can't be restored.", default=False)
        client.call(ops.DELETE_STAT_DEFINITION, path={"tenant_id": tid, "stat_definition_id": sid})
    console.out.print(console.status("done", f"deleted the stat {stat}."))


def sheet_settings(
    ctx: typer.Context,
    tenant: str,
    being_stat_group: str | None = None,
    clear_being_stat_group: bool = False,
    weapon_stat_group: str | None = None,
    clear_weapon_stat_group: bool = False,
    ability_information_type: str | None = None,
    clear_ability_information_type: bool = False,
    controllers_award_features: Annotated[
        bool | None,
        typer.Option(
            "--controllers-award-features/--no-controllers-award-features",
            help="Whether a holder's controller may award it features (ADR 0467).",
        ),
    ] = None,
    yes: Yes = False,
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
            controllers_award_features is not None,
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
        if controllers_award_features is not None:
            data["controllers_award_features"] = controllers_award_features
        if data:
            ask(ctx, yes, f"Change {', '.join(data)} of the sheet settings?")
        found = (
            client.call(ops.UPDATE_TENANT, path={"tenant_id": tid}, body=TenantUpdate(**data)).value
            if data
            else client.call(ops.GET_TENANT, path={"tenant_id": tid}).value
        )
        if as_json:
            console.emit(
                {
                    "being_stat_group_id": str(found.being_stat_group_id)
                    if found.being_stat_group_id
                    else None,
                    "weapon_stat_group_id": str(found.weapon_stat_group_id)
                    if found.weapon_stat_group_id
                    else None,
                    "ability_information_type": found.ability_information_type,
                    "controllers_award_features": found.controllers_award_features,
                }
            )
        else:
            from lorenzo_cli.runtime import _out

            _out.print(
                Text(
                    f"Being stat group: {found.being_stat_group_id or 'not set'}\n"
                    f"Weapon stat group: {found.weapon_stat_group_id or 'not set'}\n"
                    f"Ability information type: {found.ability_information_type or 'not set'}\n"
                    "Controllers award features: "
                    f"{'yes' if found.controllers_award_features else 'no'}"
                )
            )
