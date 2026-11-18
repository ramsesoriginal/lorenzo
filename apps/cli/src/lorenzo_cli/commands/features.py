"""`lorenzo feature`, `grant-rule` and `grants` (ADR 0488): what an entry has, the rules that give
it, and applying them, with a person choosing at a terminal or a script answering with `--pick`."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import typer
from rich.table import Table
from rich.text import Text

from lorenzo_cli import console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    ApplyIn,
    ApplyOut,
    EntityListOut,
    FeatureActiveIn,
    FeatureAwardIn,
    GrantRuleOut,
    GrantsOut,
    OpenChoiceOut,
    PickIn,
    StatDefinitionOut,
    SystemOut,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.library import grants
from lorenzo_cli.library.document import GrantRuleRow
from lorenzo_cli.runtime import Runtime, _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

feature_app = typer.Typer(
    help="Features: list, read, award, switch on and off, remove.", no_args_is_help=True
)
rule_app = typer.Typer(
    help="Grant rules: list, read, create from a file, delete.", no_args_is_help=True
)
grants_app = typer.Typer(
    help="What an entry holds and is due, and applying it.", no_args_is_help=True
)

Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
Yes = Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")]
EntryArgument = Annotated[str, typer.Argument(help="The entry: its slug or id.")]
FeatureArgument = Annotated[str, typer.Argument(help="The feature: its slug or id.")]


class _Library:
    def __init__(self, client: LorenzoClient, tenant_id: UUID) -> None:
        self.client = client
        self.path = {"tenant_id": tenant_id}

    def entry(self, reference: str) -> Any:
        try:
            entry_id = UUID(reference)
        except ValueError:
            return self.client.call(
                ops.GET_ENTITY_BY_SLUG, path={**self.path, "slug": reference}
            ).value
        return self.client.call(ops.GET_ENTITY, path={**self.path, "entity_id": entry_id}).value

    def slug(self, entry_id: UUID) -> str:
        found = self.client.call(ops.GET_ENTITY, path={**self.path, "entity_id": entry_id}).value
        return found.slug or str(found.id)

    def rules(self, on: UUID | None = None) -> list[GrantRuleOut]:
        query = {"entry_id": str(on)} if on else None
        return list(
            all_items(
                self.client, ops.LIST_GRANT_RULES, path=self.path, query=query, of=GrantRuleOut
            )
        )

    def held(self, holder: UUID, feature: UUID) -> Any:
        found = self.client.call(
            ops.LIST_HELD_FEATURES, path={**self.path, "entity_id": holder}
        ).value
        hits = [f for f in found.features if f.feature.id == feature]
        if not hits:
            raise SelfServiceError("It does not hold that feature: `lorenzo grants show HOLDER`.")
        return hits[0]


# --- lorenzo feature ----------------------------------------------------------------------------


@feature_app.command("list")
def feature_list(
    ctx: typer.Context,
    tenant: TenantOption,
    system: Annotated[
        str | None, typer.Option("--system", help="Only those under its root.")
    ] = None,
    as_json: Json = False,
) -> None:
    """The library's features."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        query: dict[str, Any] = {"kind": "feature"}
        if system is not None:
            found = next(
                (
                    s
                    for s in all_items(client, ops.LIST_SYSTEMS, path=library.path, of=SystemOut)
                    if s.slug == system
                ),
                None,
            )
            if found is None or found.root_entry_id is None:
                raise SelfServiceError(f"No system {system} with a root here.")
            query |= {"parent_id": str(found.root_entry_id), "recursive": True}
        rows = list(
            all_items(client, ops.LIST_ENTITIES, path=library.path, query=query, of=EntityListOut)
        )
        with console.waiting("Reading their values"):
            details = _details(client, library.path, {r.id for r in rows})
    listed = [
        {
            **r.model_dump(mode="json"),
            **details.get(r.id, {"slug": None, "under": [], "values": {}}),
        }
        for r in rows
    ]
    if as_json:
        console.emit({"features": listed})
        return
    if not rows:
        console.out.print("No features yet.")
        return
    prefix = f"{system}_" if system else ""
    table = Table("name", "slug", "under", "values", box=None, pad_edge=False)
    for row in listed:
        values = ", ".join(
            f"{name.removeprefix(prefix)} {value}" for name, value in row["values"].items()
        )
        table.add_row(
            Text(safe(row["name"])),
            Text(safe(row["slug"] or "-")),
            Text(safe(", ".join(row["under"]))),
            Text(safe(values)),
        )
    console.out.print(table)


def _details(
    client: LorenzoClient, path: dict[str, Any], wanted: set[UUID]
) -> dict[UUID, dict[str, Any]]:
    """The slug, the parents by name and the own values of each wanted entry: from the export,
    500 entries a request, and the stat names, one request (ADR 0262)."""
    names = {
        s.id: s.name
        for s in all_items(client, ops.LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }
    rows: dict[UUID, Any] = {}
    cursor: str | None = None
    while True:
        page = client.call(ops.EXPORT_ENTITIES, path=path, query={"cursor": cursor, "limit": 500})
        rows |= {row.id: row for row in page.value.items}
        cursor = page.value.next_cursor
        if cursor is None:
            break
    return {
        entry_id: {
            "slug": rows[entry_id].slug,
            "under": [rows[p].name for p in rows[entry_id].parent_ids if p in rows],
            "values": {
                names.get(s.stat_definition_id, str(s.stat_definition_id)): s.value
                for s in rows[entry_id].stats
            },
        }
        for entry_id in wanted
        if entry_id in rows
    }


@feature_app.command("show")
def feature_show(
    ctx: typer.Context, feature: FeatureArgument, tenant: TenantOption, as_json: Json = False
) -> None:
    """A feature: whether it repeats or starts switched off, its prerequisites, and the rules that
    grant it."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        entry = library.entry(feature)
        columns = client.call(
            ops.GET_FEATURE_COLUMNS, path={**library.path, "feature_id": entry.id}
        ).value
        prereq = client.call(
            ops.GET_PREREQUISITES, path={**library.path, "feature_id": entry.id}
        ).value
        granting = [r for r in library.rules() if any(o.id == entry.id for o in r.options)]
    conditions = [
        grants.comparison_from_api(p).model_dump(exclude_none=True) for p in prereq.prerequisites
    ]
    rules = [{"label": r.label, "on": r.entry_name, "mode": r.mode.value} for r in granting]
    if as_json:
        console.emit(
            {**columns.model_dump(mode="json"), "prerequisites": conditions, "granted_by": rules}
        )
        return
    flags = [
        w
        for w, on in (("repeatable", columns.repeatable), ("starts off", columns.starts_inactive))
        if on
    ]
    console.out.print(
        Text(f"{safe(columns.name)}{'  (' + ', '.join(flags) + ')' if flags else ''}")
    )
    for c in conditions:
        right = c.get("right") or c.get("value")
        console.out.print(Text(f"  needs {c['stat']} {c['comparator']} {right}"))
    for rule in rules:
        console.out.print(
            Text(f"  granted by {rule['label']} on {safe(rule['on'])} ({rule['mode']})")
        )


@feature_app.command("award")
def feature_award(
    ctx: typer.Context,
    feature: FeatureArgument,
    to: Annotated[str, typer.Option("--to", help="The holder: its slug or id.")],
    tenant: TenantOption,
    inactive: Annotated[bool, typer.Option("--inactive", help="Award it switched off.")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Award a feature to an entry by hand (a GM's, an administrator's, or its controller's when
    the library lets them, ADR 0467)."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        found, holder = library.entry(feature), library.entry(to)
        may_write(ctx.obj, yes=yes, question=f"Award {found.name} to {holder.name}?", default=True)
        made = client.call(
            ops.AWARD_FEATURE,
            path={**library.path, "entity_id": holder.id},
            body=FeatureAwardIn(feature_id=found.id, active=False if inactive else None),
        ).value
    if as_json:
        console.emit(made.model_dump(mode="json"))
    else:
        console.out.print(console.status("done", f"{holder.name} has {made.name}."))


def _switch(
    ctx: typer.Context, feature: str, on: str, tenant: str, active: bool, yes: bool
) -> None:
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        found, holder = library.entry(feature), library.entry(on)
        held = library.held(holder.id, found.id)
        verb = "on" if active else "off"
        may_write(
            ctx.obj,
            yes=yes,
            question=f"Switch {found.name} {verb} for {holder.name}?",
            default=True,
        )
        client.call(
            ops.SET_FEATURE_ACTIVE,
            path={**library.path, "instance_id": held.id},
            body=FeatureActiveIn(active=active),
        )
    console.out.print(console.status("done", f"{found.name} is {verb} for {holder.name}."))


@feature_app.command("activate")
def feature_activate(
    ctx: typer.Context,
    feature: FeatureArgument,
    on: Annotated[str, typer.Option("--on", help="The holder.")],
    tenant: TenantOption,
    yes: Yes = False,
) -> None:
    """Switch a held feature on."""
    _switch(ctx, feature, on, tenant, True, yes)


@feature_app.command("deactivate")
def feature_deactivate(
    ctx: typer.Context,
    feature: FeatureArgument,
    on: Annotated[str, typer.Option("--on", help="The holder.")],
    tenant: TenantOption,
    yes: Yes = False,
) -> None:
    """Switch a held feature off; what it alone granted is revoked."""
    _switch(ctx, feature, on, tenant, False, yes)


@feature_app.command("remove")
def feature_remove(
    ctx: typer.Context,
    feature: FeatureArgument,
    from_: Annotated[str, typer.Option("--from", help="The holder.")],
    tenant: TenantOption,
    yes: Yes = False,
) -> None:
    """Take a feature away: a revocation; the record of it stays."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        found, holder = library.entry(feature), library.entry(from_)
        held = library.held(holder.id, found.id)
        may_write(ctx.obj, yes=yes, question=f"Take {found.name} from {holder.name}?")
        client.call(ops.REMOVE_FEATURE, path={**library.path, "instance_id": held.id})
    console.out.print(console.status("done", f"{holder.name} no longer has {found.name}."))


# --- lorenzo grant-rule -------------------------------------------------------------------------


def _rule(library: _Library, reference: str) -> GrantRuleOut:
    """A rule by id, or as ENTRY:LABEL."""
    try:
        rule_id = UUID(reference)
    except ValueError:
        on, sep, label = reference.partition(":")
        if not sep:
            raise SelfServiceError("Name a rule by its id or as ENTRY:LABEL.") from None
        entry = library.entry(on)
        found = [r for r in library.rules(entry.id) if r.label == label]
        if not found:
            raise SelfServiceError(
                f"No rule {label} on {on}: `lorenzo grant-rule list --on {on}`."
            ) from None
        return found[0]
    return library.client.call(ops.GET_GRANT_RULE, path={**library.path, "rule_id": rule_id}).value


@rule_app.command("list")
def rule_list(
    ctx: typer.Context,
    tenant: TenantOption,
    on: Annotated[str | None, typer.Option("--on", help="Only the rules on this entry.")] = None,
    as_json: Json = False,
) -> None:
    """The grant rules: where each is, what it gives, all at once or to choose."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        rows = library.rules(library.entry(on).id if on else None)
    if as_json:
        console.emit({"grant_rules": [r.model_dump(mode="json") for r in rows]})
        return
    if not rows:
        console.out.print("No grant rules yet.")
        return
    table = Table("on", "label", "mode", "gives", box=None, pad_edge=False)
    for r in rows:
        gives = ", ".join(o.name for o in r.options) or (
            r.option_category.name if r.option_category else ""
        )
        count = f" ({r.min_count}..{r.max_count or ''})" if r.mode.value == "choose" else ""
        table.add_row(
            Text(safe(r.entry_name)),
            Text(safe(r.label or "")),
            r.mode.value + count,
            Text(safe(gives)),
        )
    console.out.print(table)


@rule_app.command("show")
def rule_show(
    ctx: typer.Context,
    rule: Annotated[str, typer.Argument(help="The rule: its id, or ENTRY:LABEL.")],
    tenant: TenantOption,
    as_json: Json = False,
) -> None:
    """A grant rule as a document writes it."""
    import tomli_w

    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        out = _rule(library, rule)
        row = grants.rule_from_out(out, library.slug)
    if as_json:
        console.emit(out.model_dump(mode="json"))
        return
    console.out.print(
        Text(safe(tomli_w.dumps({"grant_rule": [row.model_dump(exclude_none=True)]})))
    )


@rule_app.command("create")
def rule_create(
    ctx: typer.Context,
    tenant: TenantOption,
    from_file: Annotated[
        Path, typer.Option("--from", dir_okay=False, help="A TOML file with one [[grant_rule]].")
    ],
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Create a grant rule from a file, or replace the one with its entry and label (a rule is
    replaced whole; its entry is fixed)."""
    try:
        data = tomllib.loads(from_file.read_text(encoding="utf-8"))
        rows = data.get("grant_rule", [data])
        row = GrantRuleRow.model_validate(rows[0] if len(rows) == 1 else None)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        raise SelfServiceError(f"{from_file}: one [[grant_rule]], as in a document: {exc}") from exc
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        stats = {
            s.name: s.id
            for s in all_items(
                client, ops.LIST_STAT_DEFINITIONS, path=library.path, of=StatDefinitionOut
            )
        }

        def stat_id(name: str) -> UUID:
            if name not in stats:
                raise SelfServiceError(f"No stat {name} here.")
            return stats[name]

        on = library.entry(row.on)
        existing = next((r for r in library.rules(on.id) if r.label == row.label), None)
        body = grants.rule_body(
            row,
            entry_id=lambda slug: library.entry(slug).id,
            stat_id=stat_id,
            creating=existing is None,
        )
        verb = "Replace" if existing else "Create"
        may_write(
            ctx.obj, yes=yes, question=f"{verb} the rule {row.label} on {on.name}?", default=True
        )
        if existing is None:
            made = client.call(ops.CREATE_GRANT_RULE, path=library.path, body=body).value
        else:
            made = client.call(
                ops.REPLACE_GRANT_RULE, path={**library.path, "rule_id": existing.id}, body=body
            ).value
    if as_json:
        console.emit(made.model_dump(mode="json"))
    else:
        console.out.print(
            console.status(
                "done",
                f"{'replaced' if existing else 'created'} {made.label} on {made.entry_name}.",
            )
        )


@rule_app.command("delete")
def rule_delete(
    ctx: typer.Context,
    rule: Annotated[str, typer.Argument(help="The rule: its id, or ENTRY:LABEL.")],
    tenant: TenantOption,
    yes: Yes = False,
) -> None:
    """Delete a grant rule; what it granted is orphaned, and `grants apply` revokes it."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        out = _rule(library, rule)
        may_write(ctx.obj, yes=yes, question=f"Delete the rule {out.label} on {out.entry_name}?")
        client.call(ops.DELETE_GRANT_RULE, path={**library.path, "rule_id": out.id})
    console.out.print(console.status("done", f"deleted {out.label} on {out.entry_name}."))


# --- lorenzo grants -----------------------------------------------------------------------------


@grants_app.command("show")
def grants_show(
    ctx: typer.Context, holder: EntryArgument, tenant: TenantOption, as_json: Json = False
) -> None:
    """What an entry holds and how it came to, what is due, the choices open to it, and what is
    orphaned (its source or conditions gone)."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        found = library.entry(holder)
        state: GrantsOut = client.call(
            ops.GET_GRANTS, path={**library.path, "entity_id": found.id}
        ).value
    if as_json:
        console.emit(state.model_dump(mode="json"))
        return
    out = console.out
    out.print(Text(safe(state.holder.name), style="bold"))
    out.print(Text("Held", style="bold"))
    for h in state.held:
        how = f"granted by {h.label} from {h.source.name}" if h.source else "awarded"
        out.print(Text(f"  {safe(h.feature.name)}  ({safe(how)})"))
    if not state.held:
        out.print("  nothing yet")
    out.print(Text("Due", style="bold"))
    for d in state.due:
        out.print(
            Text(f"  {safe(d.feature.name)}  (by {safe(d.label or '')} from {safe(d.source.name)})")
        )
    if not state.due:
        out.print("  nothing")
    out.print(Text("Open choices", style="bold"))
    for c in state.open_choices:
        _print_choice(c)
    if not state.open_choices:
        out.print("  none")
    if state.orphaned:
        out.print(Text("Orphaned", style="bold"))
        for o in state.orphaned:
            out.print(Text(f"  {safe(o.feature.name)}  ({o.reason.value})"))


def _print_choice(choice: OpenChoiceOut) -> None:
    picked = f", picked {', '.join(p.name for p in choice.picked)}" if choice.picked else ""
    console.out.print(
        Text(
            f"  {safe(choice.label or '')} from {safe(choice.source.name)}: choose "
            f"{choice.minimum} to {choice.maximum}{picked}"
        )
    )
    for number, option in enumerate(choice.options, start=1):
        console.out.print(Text(f"    {number}  {safe(option.name)}"))


def _picks(library: _Library, choices: list[OpenChoiceOut], given: list[str]) -> list[PickIn]:
    """`--pick RULE=OPTION[,OPTION]`: a rule by its label or id, an option by name, slug or id."""
    picks: list[PickIn] = []
    for text in given:
        rule, sep, options = text.partition("=")
        if not sep:
            raise typer.BadParameter(f"{text}: write a pick as RULE=OPTION[,OPTION].")
        matching = [c for c in choices if rule in (c.label, str(c.rule_id))]
        if not matching:
            open_now = ", ".join(c.label or str(c.rule_id) for c in choices) or "none"
            raise SelfServiceError(f"No open choice {rule} (open: {open_now}).")
        for choice in matching:
            chosen: list[UUID] = []
            for name in [o.strip() for o in options.split(",") if o.strip()]:
                hit = next((o for o in choice.options if name in (o.name, str(o.id))), None)
                if hit is None:
                    entry = library.entry(name)
                    hit = next((o for o in choice.options if o.id == entry.id), None)
                if hit is None or hit.id is None:
                    raise SelfServiceError(f"{name} is not one of the options of {rule}.")
                chosen.append(hit.id)
            if choice.source.id is not None:
                picks.append(
                    PickIn(rule_id=choice.rule_id, source_id=choice.source.id, options=chosen)
                )
    return picks


def _ask(choices: list[OpenChoiceOut], answered: set[UUID]) -> list[PickIn]:
    """At a terminal: each open choice not answered by `--pick`, as a numbered list."""
    picks: list[PickIn] = []
    for choice in choices:
        if choice.rule_id in answered or choice.source.id is None:
            continue
        _print_choice(choice)
        with console.paused():
            text = typer.prompt(
                f"Pick {choice.minimum} to {choice.maximum} (numbers, commas between; "
                "empty to leave it)",
                default="",
                show_default=False,
                err=True,
            )
        numbers = [int(n) for n in text.replace(" ", "").split(",") if n.isdigit()]
        if not numbers:
            continue
        if not choice.minimum <= len(numbers) <= choice.maximum:
            raise SelfServiceError(f"{choice.label}: pick {choice.minimum} to {choice.maximum}.")
        options = [choice.options[n - 1].id for n in numbers if 0 < n <= len(choice.options)]
        picks.append(
            PickIn(
                rule_id=choice.rule_id,
                source_id=choice.source.id,
                options=[o for o in options if o],
            )
        )
    return picks


def _print_apply(result: ApplyOut, *, written: bool) -> None:
    verb = "" if written else "would be "
    for c in result.created:
        console.out.print(
            console.status("create", f"{c.feature.name} {verb}granted ({c.label or 'award'})")
        )
    for r in result.revoked:
        console.out.print(
            console.status("remove", f"{r.feature.name} {verb}revoked ({r.reason.value})")
        )
    if result.truncated:
        console.warning("the chain went deeper than one apply follows: apply again to finish.")


@grants_app.command("apply")
def grants_apply(
    ctx: typer.Context,
    holder: EntryArgument,
    tenant: TenantOption,
    pick: Annotated[
        list[str] | None,
        typer.Option("--pick", help="RULE=OPTION[,OPTION]: a choice answered; repeat."),
    ] = None,
    override: Annotated[
        bool, typer.Option("--override", help="A GM's: past prerequisites and counts.")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what it would do.")] = False,
    yes: Yes = False,
    as_json: Json = False,
) -> None:
    """Grant what is due and revoke what is orphaned. It always asks the API for a dry run first
    and shows it; at a terminal it asks each open choice, and `--pick` answers one for a script.

    Exit codes: 0 done or nothing due, 2 not applied or choices left open, 1 refused."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        found = library.entry(holder)
        path = {**library.path, "entity_id": found.id}
        first: ApplyOut = client.call(
            ops.APPLY_GRANTS, path=path, body=ApplyIn(dry_run=True, override=override)
        ).value
        picks = _picks(library, first.open_choices, pick or [])
        if runtime.interactive and not yes and not as_json and not dry_run:
            picks += _ask(first.open_choices, {p.rule_id for p in picks})
        planned = first
        if picks:
            planned = client.call(
                ops.APPLY_GRANTS,
                path=path,
                body=ApplyIn(picks=picks, dry_run=True, override=override),
            ).value
        if override and not as_json:
            console.warning("override: a GM's apply; prerequisites and counts were not held to.")
        nothing = not (planned.created or planned.revoked)
        if dry_run or nothing:
            if as_json:
                console.emit(planned.model_dump(mode="json"))
            else:
                _print_apply(planned, written=False)
                for c in planned.open_choices:
                    _print_choice(c)
            raise typer.Exit(2 if planned.open_choices or not nothing else 0)
        if not as_json:
            _print_apply(planned, written=False)
        said = f"{len(planned.created)} to grant, {len(planned.revoked)} to revoke"
        may_write(runtime, yes=yes, question=f"Apply to {found.name}: {said}?", default=True)
        done: ApplyOut = client.call(
            ops.APPLY_GRANTS, path=path, body=ApplyIn(picks=picks, override=override)
        ).value
    if as_json:
        console.emit(done.model_dump(mode="json"))
    else:
        console.out.print(
            console.status("done", f"{len(done.created)} granted, {len(done.revoked)} revoked.")
        )
        for c in done.open_choices:
            _print_choice(c)
    raise typer.Exit(2 if done.open_choices else 0)
