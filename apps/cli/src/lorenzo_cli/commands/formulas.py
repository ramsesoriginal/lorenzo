"""`lorenzo formula` (ADR 0500): set, show, preview, trace and delete one formula on an entry.

A formula is its kind and that kind's fields, as options for the kinds whose fields are flat, or
from a file for the rest (a `select` and its steps). No notation (RFC 0016).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import typer
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from lorenzo_cli import completers, console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import ComputedStatPreviewIn, EntityDetailOut, StatDefinitionOut
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.library.formulas import (
    KINDS,
    FormulaError,
    body,
    check,
    from_api,
    stats_named,
)
from lorenzo_cli.runtime import _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

app = typer.Typer(
    help="Set, show, preview, trace or delete a formula on an entry.", no_args_is_help=True
)

StatArgument = Annotated[
    str,
    typer.Argument(help="The stat the formula computes, by name.", autocompletion=completers.stat),
]
OnOption = Annotated[str, typer.Option("--on", help="The entry it is on: its slug or id.")]
Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
Opt = typer.Option
MAX_DEPTH = 64


class _Library:
    """The stats of a library by name and id, and its entries by slug, read once per command."""

    def __init__(self, client: LorenzoClient, tenant_id: UUID) -> None:
        self.client = client
        self.path = {"tenant_id": tenant_id}
        rows = all_items(client, ops.LIST_STAT_DEFINITIONS, path=self.path, of=StatDefinitionOut)
        self.stats = {s.name: s for s in rows}
        self.names = {s.id: s.name for s in self.stats.values()}
        self._entries: dict[UUID, EntityDetailOut] = {}

    def stat(self, name: str) -> StatDefinitionOut:
        found = self.stats.get(name)
        if found is None:
            raise SelfServiceError(f"No stat called {name} here: `lorenzo stat-definition list`.")
        return found

    def stat_id(self, name: str) -> UUID:
        return self.stat(name).id

    def entry(self, reference: str) -> EntityDetailOut:
        try:
            entry_id = UUID(reference)
        except ValueError:
            found = self.client.call(
                ops.GET_ENTITY_BY_SLUG, path={**self.path, "slug": reference}
            ).value
        else:
            found = self.client.call(
                ops.GET_ENTITY, path={**self.path, "entity_id": entry_id}
            ).value
        self._entries[found.id] = found
        return found

    def by_id(self, entry_id: UUID) -> EntityDetailOut:
        if entry_id not in self._entries:
            self._entries[entry_id] = self.client.call(
                ops.GET_ENTITY, path={**self.path, "entity_id": entry_id}
            ).value
        return self._entries[entry_id]

    def formula(
        self, entry: EntityDetailOut, stat: str
    ) -> tuple[EntityDetailOut, dict[str, Any]] | None:
        """The formula that computes `stat` for `entry`: its own, or the one it inherits."""
        held = next((s for s in entry.stats if s.name == stat), None)
        source = entry
        if held is not None and held.computed and held.from_entity is not None:
            source = self.by_id(held.from_entity.id)
        rows = self.client.call(
            ops.LIST_ENTITY_COMPUTED_STATS, path={**self.path, "entity_id": source.id}
        ).value
        stat_id = self.stat_id(stat)
        found = next((r for r in rows if r.stat_definition_id == stat_id), None)
        if found is None:
            return None
        return source, found.formula.model_dump(mode="json", by_alias=True)


def _fields(
    *,
    source: str | None,
    multiplier: float | None,
    offset: float | None,
    round_: str | None,
    left: str | None,
    comparator: str | None,
    right: str | None,
    right_value: float | None,
    if_true: str | None,
    if_false: str | None,
    terms: list[str] | None,
    inputs: list[str] | None,
    factors: list[str] | None,
    numerator: str | None,
    denominator: str | None,
    denominator_value: float | None,
    count: str | None,
    count_value: int | None,
    sides: str | None,
    sides_value: int | None,
    aggregate: str | None,
    only_active: bool | None,
    only_kind: str | None,
    where: str | None,
    if_none: float | None,
    as_: str | None,
) -> dict[str, Any]:
    def term(text: str) -> Any:
        name, _, coefficient = text.partition("*")
        return {"stat": name, "coefficient": float(coefficient)} if coefficient else name

    def number_or_name(text: str) -> Any:
        try:
            return float(text)
        except ValueError:
            return text

    fields: dict[str, Any] = {
        "source": source,
        "multiplier": multiplier,
        "offset": offset,
        "round": round_,
        "left": left,
        "comparator": comparator,
        "right": right,
        "right_constant": right_value,
        "true_value": if_true,
        "false_value": if_false,
        "terms": [term(t) for t in terms] if terms else None,
        "inputs": [number_or_name(i) for i in inputs] if inputs else None,
        "factors": factors or None,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_constant": denominator_value,
        "count": count,
        "count_constant": count_value,
        "sides": sides,
        "sides_constant": sides_value,
        "aggregate": aggregate,
        "only_active": only_active,
        "only_kind": only_kind,
        "where": where,
        "if_none": if_none,
        "as": as_,
    }
    return {k: v for k, v in fields.items() if v is not None}


def _from_file(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SelfServiceError(f"Couldn't read {path}: {exc}") from exc
    rows = data.get("formula", [data])
    if not isinstance(rows, list) or len(rows) != 1:
        raise SelfServiceError(f"{path} holds {len(rows)} formulas; name one file per formula.")
    row = {k: v for k, v in rows[0].items() if k not in ("on", "stat")}
    kind = row.pop("kind", None)
    if kind is None:
        raise SelfServiceError(f"{path}: a formula names its `kind`.")
    return str(kind), row


# The options every command that writes or previews a formula takes.
KindOption = Annotated[str | None, Opt("--kind", help=f"One of: {', '.join(KINDS)}.")]
FromOption = Annotated[
    Path | None, Opt("--from", dir_okay=False, help="A TOML file with the formula (for a select).")
]


def _formula(
    kind: str | None, from_file: Path | None, flags: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    if from_file is not None:
        if kind is not None or flags:
            raise SelfServiceError("Give the formula with --from or with options, not both.")
        found_kind, fields = _from_file(from_file)
    elif kind is None:
        raise SelfServiceError("Name the formula's --kind (or give it --from a file).")
    else:
        found_kind, fields = kind, flags
    try:
        check(found_kind, fields)
    except FormulaError as exc:
        raise SelfServiceError(str(exc)) from exc
    return found_kind, fields


def _show_fields(kind: str, fields: dict[str, Any]) -> Text:
    import tomli_w

    return Text(safe(tomli_w.dumps({"kind": kind, **fields}).rstrip()))


@app.command("set")
def formula_set(
    ctx: typer.Context,
    stat: StatArgument,
    on: OnOption,
    tenant: TenantOption,
    kind: KindOption = None,
    from_file: FromOption = None,
    source: Annotated[str | None, Opt("--source", help="The stat it reads.")] = None,
    multiplier: Annotated[float | None, Opt("--multiplier")] = None,
    offset: Annotated[float | None, Opt("--offset")] = None,
    round_: Annotated[
        str | None, Opt("--round", help="none, floor, ceil, round, truncate.")
    ] = None,
    left: Annotated[str | None, Opt("--left")] = None,
    comparator: Annotated[str | None, Opt("--comparator", help="lt, le, eq, ne, ge, gt.")] = None,
    right: Annotated[str | None, Opt("--right")] = None,
    right_value: Annotated[float | None, Opt("--right-value")] = None,
    if_true: Annotated[
        str | None, Opt("--true", help="A comparison's value when it holds.")
    ] = None,
    if_false: Annotated[str | None, Opt("--false")] = None,
    terms: Annotated[list[str] | None, Opt("--term", help="STAT or STAT*COEFF; repeat.")] = None,
    inputs: Annotated[list[str] | None, Opt("--input", help="STAT or a number; repeat.")] = None,
    factors: Annotated[list[str] | None, Opt("--factor", help="A stat; repeat.")] = None,
    numerator: Annotated[str | None, Opt("--numerator")] = None,
    denominator: Annotated[str | None, Opt("--denominator")] = None,
    denominator_value: Annotated[float | None, Opt("--denominator-value")] = None,
    count: Annotated[str | None, Opt("--count", help="A dice formula's count, a stat.")] = None,
    count_value: Annotated[int | None, Opt("--count-value")] = None,
    sides: Annotated[str | None, Opt("--sides")] = None,
    sides_value: Annotated[int | None, Opt("--sides-value")] = None,
    aggregate: Annotated[str | None, Opt("--aggregate", help="sum, min, max, count.")] = None,
    only_active: Annotated[bool | None, Opt("--only-active/--also-inactive")] = None,
    only_kind: Annotated[
        str | None, Opt("--only-kind", help="item_instance, feature_instance.")
    ] = None,
    where: Annotated[str | None, Opt("--where", help="Only what holds this flag stat.")] = None,
    if_none: Annotated[float | None, Opt("--if-none")] = None,
    as_: Annotated[str | None, Opt("--as", help="A dice value: min, max, average.")] = None,
    warnings: Annotated[bool, Opt("--warnings", help="Ask the check about what it wrote.")] = False,
    yes: Annotated[bool, Opt("--yes", help="Don't ask before writing.")] = False,
    as_json: Json = False,
) -> None:
    """Set the formula that computes STAT on an entry, replacing any it has there.

    The limits of its kind are checked before anything is sent: two to five inputs or factors,
    one to twenty terms, one to sixty-four steps, a dice count of 1 to 100 and sides of 2 to 1000.
    """
    flags = _fields(
        source=source, multiplier=multiplier, offset=offset, round_=round_, left=left,
        comparator=comparator, right=right, right_value=right_value, if_true=if_true,
        if_false=if_false, terms=terms, inputs=inputs, factors=factors, numerator=numerator,
        denominator=denominator, denominator_value=denominator_value, count=count,
        count_value=count_value, sides=sides, sides_value=sides_value, aggregate=aggregate,
        only_active=only_active, only_kind=only_kind, where=where, if_none=if_none, as_=as_,
    )  # fmt: skip
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        found_kind, fields = _formula(kind, from_file, flags)
        target = resolve_tenant(client, tenant)
        library = _Library(client, target.id)
        entry = library.entry(on)
        stat_id = library.stat_id(stat)
        request = body(found_kind, fields, library.stat_id)
        may_write(
            ctx.obj, yes=yes, question=f"Set {stat} on {entry.name} to a {found_kind} formula?",
            default=True,
        )  # fmt: skip
        written = client.call(
            ops.SET_COMPUTED_STAT,
            path={"tenant_id": target.id, "entity_id": entry.id, "stat_definition_id": stat_id},
            query={"warnings": True} if warnings else None,
            body=request,
        ).value
    if as_json:
        console.emit(written.model_dump(mode="json", by_alias=True))
        return
    console.out.print(console.status("done", f"{stat} on {entry.name} is a {found_kind} formula."))
    for finding in written.warnings or []:
        console.warning(f"{finding.code}: {finding.message}")


@app.command("show")
def formula_show(
    ctx: typer.Context,
    stat: StatArgument,
    on: OnOption,
    tenant: TenantOption,
    as_json: Json = False,
) -> None:
    """The formula that computes STAT on an entry, its own or the one it inherits."""
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        library = _Library(client, target.id)
        entry = library.entry(on)
        found = library.formula(entry, stat)
    if found is None:
        raise_none(stat, entry.name)
    assert found is not None
    source, formula = found
    kind = str(formula.pop("kind"))
    fields = from_api(formula, lambda i: library.names.get(i, str(i)), kind)
    if as_json:
        console.emit(
            {"entry": entry.slug, "stat": stat, "from": source.slug, "kind": kind, "fields": fields}
        )
        return
    if source.id != entry.id:
        console.out.print(Text(f"{stat} on {entry.name} is inherited from {source.name}:"))
    console.out.print(_show_fields(kind, fields))


def raise_none(stat: str, entry: str) -> None:
    console.out.print(f"{stat} on {entry} has no formula: it holds its own value, or none.")
    raise typer.Exit(0)


@app.command("preview")
def formula_preview(
    ctx: typer.Context,
    stat: StatArgument,
    on: OnOption,
    tenant: TenantOption,
    kind: KindOption = None,
    from_file: FromOption = None,
    source: Annotated[str | None, Opt("--source")] = None,
    multiplier: Annotated[float | None, Opt("--multiplier")] = None,
    offset: Annotated[float | None, Opt("--offset")] = None,
    round_: Annotated[str | None, Opt("--round")] = None,
    terms: Annotated[list[str] | None, Opt("--term")] = None,
    inputs: Annotated[list[str] | None, Opt("--input")] = None,
    factors: Annotated[list[str] | None, Opt("--factor")] = None,
    count: Annotated[str | None, Opt("--count")] = None,
    count_value: Annotated[int | None, Opt("--count-value")] = None,
    sides: Annotated[str | None, Opt("--sides")] = None,
    sides_value: Annotated[int | None, Opt("--sides-value")] = None,
    as_: Annotated[str | None, Opt("--as")] = None,
    as_json: Json = False,
) -> None:
    """What STAT on an entry comes to, with each input and its value: the formula it has, or, with
    --kind or --from, one before it is saved. A dice value prints as its notation."""
    flags = _fields(
        source=source, multiplier=multiplier, offset=offset, round_=round_, left=None,
        comparator=None, right=None, right_value=None, if_true=None, if_false=None, terms=terms,
        inputs=inputs, factors=factors, numerator=None, denominator=None, denominator_value=None,
        count=count, count_value=count_value, sides=sides, sides_value=sides_value,
        aggregate=None, only_active=None, only_kind=None, where=None, if_none=None, as_=as_,
    )  # fmt: skip
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        library = _Library(client, target.id)
        entry = library.entry(on)
        stat_id = library.stat_id(stat)
        asked = None
        if kind is not None or from_file is not None:
            found_kind, fields = _formula(kind, from_file, flags)
            asked = body(found_kind, fields, library.stat_id)
        answer = client.call(
            ops.PREVIEW_COMPUTED_STAT,
            path={"tenant_id": target.id, "entity_id": entry.id, "stat_definition_id": stat_id},
            body=ComputedStatPreviewIn(formula=asked),
        ).value
    if as_json:
        console.emit(answer.model_dump(mode="json"))
        return
    said = {"computed": "calculated", "direct": "its own value", "unset": "no value"}
    value = "unknown" if answer.value is None else answer.value
    console.out.print(Text(f"{stat} on {entry.name} = {value}  ({said[answer.source.value]})"))
    if answer.inputs:
        table = Table("input", "value", box=None, pad_edge=False)
        for row in answer.inputs:
            table.add_row(Text(safe(row.name)), "unknown" if row.value is None else str(row.value))
        console.out.print(table)


@app.command("tree")
def formula_tree(
    ctx: typer.Context,
    stat: StatArgument,
    on: OnOption,
    tenant: TenantOption,
    as_json: Json = False,
) -> None:
    """The chain of formulas behind STAT on an entry, down to the values it holds, and the formulas
    that read STAT anywhere in the library."""
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        library = _Library(client, target.id)
        entry = library.entry(on)

        def node(name: str, seen: tuple[str, ...]) -> dict[str, Any]:
            held = next((s for s in entry.stats if s.name == name), None)
            here: dict[str, Any] = {"stat": name, "value": held.value if held else None}
            if name in seen or len(seen) >= MAX_DEPTH:
                return {**here, "loop": True}
            found = library.formula(entry, name) if held is None or held.computed else None
            if found is None:
                here["own"] = held is not None and held.own
                return here
            source, formula = found
            kind = str(formula.pop("kind"))
            fields = from_api(formula, lambda i: library.names.get(i, str(i)), kind)
            here |= {"kind": kind, "from": source.slug}
            here["inputs"] = [node(n, (*seen, name)) for n in stats_named(fields)]
            return here

        chain = node(stat, ())
        dependents = client.call(
            ops.LIST_STAT_DEPENDENTS,
            path={"tenant_id": target.id, "stat_definition_id": library.stat_id(stat)},
        ).value
        readers = [
            {
                "stat": library.names.get(d.stat_definition_id, str(d.stat_definition_id)),
                "kind": d.kind.value,
                "on": library.by_id(d.entity_id).name,
            }
            for d in dependents
        ]
    if as_json:
        console.emit({"chain": chain, "read_by": readers})
        return
    tree = Tree(_label(chain))

    def grow(branch: Tree, here: dict[str, Any]) -> None:
        for child in here.get("inputs", []):
            grow(branch.add(_label(child)), child)

    grow(tree, chain)
    console.out.print(tree)
    if readers:
        said = "; ".join(f"{r['stat']} ({r['kind']}) on {r['on']}" for r in readers)
        console.out.print(Text(f"Read by: {said}"))


def _label(here: dict[str, Any]) -> Text:
    value = "unknown" if here.get("value") is None else here["value"]
    if here.get("loop"):
        return Text(f"{here['stat']}  (already above: a loop)")
    if "kind" in here:
        return Text(f"{here['stat']} = {value}  ({here['kind']}, on {here['from']})")
    origin = (
        "own value"
        if here.get("own")
        else "inherited"
        if here.get("value") is not None
        else "unset"
    )
    return Text(f"{here['stat']} = {value}  ({origin})")


@app.command("delete")
def formula_delete(
    ctx: typer.Context,
    stat: StatArgument,
    on: OnOption,
    tenant: TenantOption,
    yes: Annotated[bool, Opt("--yes", help="Don't ask before deleting.")] = False,
) -> None:
    """Remove the formula an entry has for STAT; an inherited one stays on its own entry."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        target = resolve_tenant(client, tenant)
        library = _Library(client, target.id)
        entry = library.entry(on)
        stat_id = library.stat_id(stat)
        may_write(ctx.obj, yes=yes, question=f"Remove the formula for {stat} on {entry.name}?")
        client.call(
            ops.DELETE_COMPUTED_STAT,
            path={"tenant_id": target.id, "entity_id": entry.id, "stat_definition_id": stat_id},
        )
    console.out.print(console.status("done", f"removed the formula for {stat} on {entry.name}."))
