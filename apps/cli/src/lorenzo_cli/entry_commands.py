"""Read entries and their permissioned text in the terminal (ADR 0295)."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

import typer
from rich.table import Column, Table
from rich.text import Text

from lorenzo_cli import console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import DescriptionOut, ItemInstanceOut, ItemOut, SheetOut
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer.tenant_view import resolve_slugs
from lorenzo_cli.self_service import SelfServiceError, beings_named, characters, resolve_item
from lorenzo_cli.terminal_script import Parser, print_script, safe
from lorenzo_cli.vocabulary_commands import Json, Tenant, session, vocabulary

Kind = Literal["item", "item_instance", "being"]
instance_app = typer.Typer(help="Read item instances.", no_args_is_help=True)
being_app = typer.Typer(help="Read beings and their sheets, or make one.", no_args_is_help=True)


def entry_id(client: LorenzoClient, tid: UUID, ref: str, kind: Kind) -> UUID:
    if kind == "item":
        return resolve_item(client, tid, ref).entity_id
    try:
        return UUID(ref)
    except ValueError:
        pass
    hits = resolve_slugs(client, tid, [ref])
    if ref in hits:
        return hits[ref].entity_id
    if kind == "being":
        mine = [c for c in characters(client, tid) if c.name.casefold() == ref.casefold()]
        rows: set[UUID] = {r.entity_id for r in mine}
        rows.update(r.entity_id for r in beings_named(client, tid, ref))
    else:
        rows = {
            r.entity_id
            for r in all_items(
                client, ops.LIST_ITEM_INSTANCES, path={"tenant_id": tid}, of=ItemInstanceOut
            )
            if r.title.casefold() == ref.casefold()
        }
    if len(rows) == 1:
        return next(iter(rows))
    if not rows:
        raise SelfServiceError(
            f"No {kind.replace('_', ' ')} called “{ref}” you can read here. "
            "Try its id or link name."
        )
    ids = "\n".join(f"  {eid}" for eid in rows)
    raise SelfServiceError(f"More than one entry matches “{ref}”; name it by id.\n{ids}")


def formatted(value: object, definition: Any = None) -> str:
    if isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, (int, float)):
        text = format(value, "+") if definition and definition.signed else str(value)
    else:
        text = str(value)
    return safe(text + (f" {definition.unit}" if definition and definition.unit else ""))


def description_origin(desc: DescriptionOut) -> str:
    """Where a description comes from, as a title suffix: nothing for the entry's own.

    A null `from_entity` is the entry's own text only when `from_hidden` is not set: a text from an
    entry the library hides arrives with no name and `from_hidden: true` (ADR 0437), and is said
    to come from "a hidden entry" and never named.
    """
    if desc.from_entity:
        return f" · from {desc.from_entity.name}"
    if desc.from_hidden:
        return " · from a hidden entry"
    return ""


def references(
    client: LorenzoClient, tid: UUID, home: UUID, parsed: list[dict[str, Any]]
) -> dict[str, str]:
    refs = {
        (r["hint"], r["slug"])
        for document in parsed
        for r in document["refs"]
        if r["kind"] in ("entity", "image")
    }
    slugs = sorted({f"my/{slug}" if hint == "my" else slug for hint, slug in refs})
    found: dict[str, str] = {}
    for start in range(0, len(slugs), 100):
        hits = client.call(
            ops.RESOLVE_SLUGS,
            path={"tenant_id": tid},
            query={"slug": slugs[start : start + 100], "from": str(home)},
        ).value
        for hit in hits:
            for hint, slug in refs:
                if hit.slug == (f"my/{slug}" if hint == "my" else slug):
                    found[f"{hint}/{slug}"] = (
                        f"{hint + '/' if hint else ''}{hit.slug} · {hit.entity_id}"
                    )
    return found


def show(
    ctx: typer.Context,
    tenant: str,
    ref: str,
    kind: Kind,
    as_json: bool,
    *,
    system: str | None = None,
    campaign: str | None = None,
    template: str | None = None,
) -> None:
    from lorenzo_cli.runtime import _out

    with session(ctx, tenant) as (client, tid):
        eid = entry_id(client, tid, ref, kind)
        detail = client.call(
            ops.GET_ENTITY, path={"tenant_id": tid, "entity_id": eid}, query={"system": system}
        ).value
        if kind not in {k.value for k in detail.kinds}:
            raise SelfServiceError(f"“{detail.name}” is not a {kind.replace('_', ' ')}.")
        item: ItemOut | ItemInstanceOut | None = None
        if kind == "item":
            item = client.call(ops.GET_ITEM, path={"tenant_id": tid, "entity_id": eid}).value
        elif kind == "item_instance":
            item = client.call(
                ops.GET_ITEM_INSTANCE, path={"tenant_id": tid, "entity_id": eid}
            ).value
        sheet = (
            client.call(
                ops.GET_BEING_SHEET,
                path={"tenant_id": tid, "entity_id": eid},
                query=_sheet_query(client, tid, campaign, template),
            ).value
            if kind == "being"
            else None
        )
        # A campaign or a template names the sheet: the being is read through it (ADR 0487).
        view = (
            client.call(
                ops.READ_THROUGH_TEMPLATE,
                path={"tenant_id": tid, "entity_id": eid, "template_id": sheet.template.id},
            ).value
            if sheet is not None and sheet.template is not None and (campaign or template)
            else None
        )
        held = (
            client.call(ops.LIST_HELD_FEATURES, path={"tenant_id": tid, "entity_id": eid}).value
            if kind == "being"
            else None
        )
        data = {"entry": detail.model_dump(mode="json")}
        if item is not None:
            data["item" if kind == "item" else "item_instance"] = item.model_dump(mode="json")
        if sheet is not None:
            data["sheet"] = sheet.model_dump(mode="json")
        if view is not None:
            data["view"] = view.model_dump(mode="json")
        if as_json:
            console.emit(data)
            return
        definitions = vocabulary(client, tid)
        by_name = {d.name: d for d in definitions}
        stat_values = {s.name: s.value for s in detail.stats}

        _out.print(Text(safe(item.title if item else detail.name), style="bold"))
        _out.print(Text(f"{eid}" + (f" · {safe(detail.slug)}" if detail.slug else ""), style="dim"))
        _out.print(Text("Kinds: " + ", ".join(k.value for k in detail.kinds)))
        if detail.prototypes:
            _out.print(Text("Inherits from: " + ", ".join(safe(p.name) for p in detail.prototypes)))
        if detail.parent:
            _out.print(Text(f"In: {safe(detail.parent.name)} · {detail.parent.id}"))
        if detail.quantity is not None:
            _out.print(Text(f"Quantity: {detail.quantity}"))
        if isinstance(item, ItemInstanceOut):
            _out.print(
                Text(
                    f"Owner: {item.owner_entity_id or 'none'}" + (" · Bound" if item.bound else "")
                )
            )
        # A feature a being holds is an entry below it, not something it carries.
        features = list(held.features) if held is not None else []
        feature_ids = {f.id for f in features}
        carried = [c for c in detail.children if c.id not in feature_ids]
        if carried:
            _out.print(Text("Contains: " + ", ".join(safe(c.name) for c in carried)))
        if features and view is None:
            _out.print(
                Text(
                    "Features: "
                    + ", ".join(safe(f.name) + ("" if f.active else " (off)") for f in features)
                )
            )
        if view is not None:
            from lorenzo_cli.sheet_view import print_view

            _out.print()
            print_view(view, {d.id: d for d in definitions})
            return
        if (campaign or template) and sheet is not None and sheet.template is None:
            console.notice("No template matches it there, so every stat follows.")
        table = Table("Stat", "Value", "Hints", "Source", box=None)
        stats = {s.name: s for s in detail.stats}
        ordered = [d.name for d in definitions if d.name in stats]
        ordered.extend(name for name in stats if name not in ordered)
        by_id = {d.id: d for d in definitions}
        for name in ordered:
            stat, definition = stats[name], by_name.get(name)
            hint_text: list[str] = []
            if definition:
                for label, hint in [
                    ("of", definition.max_hint_id),
                    ("min", definition.min_hint_id),
                    ("resolved", definition.resolved_hint_id),
                ]:
                    target = by_id.get(hint)
                    if target and target.name in stat_values:
                        hint_text.append(f"{label} {formatted(stat_values[target.name], target)}")
            source = (
                "own"
                if stat.own
                else f"from {stat.from_entity.name}"
                if stat.from_entity
                else "inherited"
            )
            if stat.computed:
                source += " · calculated"
            table.add_row(
                Text(safe(name)),
                Text(formatted(stat.value, definition)),
                Text("; ".join(hint_text)),
                Text(safe(source)),
            )
        if stats:
            _out.print(table)
        if sheet:
            print_sheet(sheet, by_name)
        texts: list[tuple[str, str]] = []
        seen: set[str] = set()
        if item:
            for desc in item.descriptions:
                title = f"Description{description_origin(desc)} · {desc.locale}"
                texts.append((title, desc.content))
                seen.add(desc.content)
            if item.pictures:
                _out.print(Text(f"Pictures: {len(item.pictures)} (use a web app to view)"))
        information = {note.id: note for note in detail.information}
        if sheet:
            information.update({note.id: note for note in sheet.abilities})
        for note in sorted(information.values(), key=lambda n: (n.order, str(n.id))):
            audience = "Everyone" if note.is_public else "Not for everyone"
            title = f"{note.title} · {note.type} · {audience}" + (
                f" · {note.created_by_name}" if note.created_by_name else ""
            )
            for payload in note.payloads:
                body = payload.root
                if body.kind == "description":
                    if note.type == "description" and body.content in seen:
                        continue
                    texts.append((f"{title} · {body.locale}", body.content))
                elif body.kind == "number":
                    texts.append((title, body.value))
                else:
                    _out.print(Text(safe(f"{title}: {body.kind} (use a web app to view)")))
        parser = Parser()
        try:
            stat_text = {
                parser.slugify(s.name): formatted(s.value, by_name.get(s.name))
                for s in detail.stats
            }
            parsed = [parser.parse(content) for _, content in texts]
            links = references(client, tid, eid, parsed)
            for (title, _), document in zip(texts, parsed, strict=True):
                _out.print(Text(safe(title), style="bold"))
                print_script(_out, document, stats=stat_text, entities=links)
        finally:
            parser.close()


def print_sheet(sheet: SheetOut, definitions: dict[str, Any]) -> None:
    from lorenzo_cli.runtime import _out

    if not sheet.weapons_configured:
        _out.print(Text("Weapon stat group is not set.", style="dim"))
    else:
        names = list(dict.fromkeys(s.name for weapon in sheet.weapons for s in weapon.stats))
        table = Table(
            "Equipped weapon", "Quantity", *[Column(header=Text(safe(n))) for n in names], box=None
        )
        for weapon in sheet.weapons:
            values = {s.name: s.value for s in weapon.stats}
            table.add_row(
                Text(safe(weapon.name)),
                str(weapon.quantity or 1),
                *[
                    Text(formatted(values[n], definitions.get(n)) if n in values else "—")
                    for n in names
                ],
            )
        _out.print(table if sheet.weapons else Text("No equipped weapons visible."))
    if not sheet.abilities_configured:
        _out.print(Text("Ability information type is not set.", style="dim"))
    elif not sheet.abilities:
        _out.print(Text("No abilities visible.", style="dim"))


SystemOption = Annotated[
    str | None,
    typer.Option(
        "--system", help="Read it as one system shows it: its stats and the neutral ones."
    ),
]


def _sheet_query(
    client: LorenzoClient, tid: UUID, campaign: str | None, template: str | None
) -> dict[str, str]:
    """The sheet's campaign (whose system picks the template) and template, by name or id."""
    from lorenzo_cli.client.models import TemplateSummaryOut
    from lorenzo_cli.commands.campaigns import find as find_campaign

    query: dict[str, str] = {}
    if campaign is not None:
        query["campaign_id"] = str(find_campaign(client, tid, campaign).id)
    if template is not None:
        rows = all_items(client, ops.LIST_TEMPLATES, path={"tenant_id": tid}, of=TemplateSummaryOut)
        found = next((t for t in rows if template in (t.name, str(t.id))), None)
        if found is None:
            raise SelfServiceError(f"No template {template} here: `lorenzo template list`.")
        query["template_id"] = str(found.id)
    return query


def item_show(
    ctx: typer.Context,
    item: str,
    tenant: Tenant,
    system: SystemOption = None,
    as_json: Json = False,
) -> None:
    """Read an item by id, link name or exact title."""
    show(ctx, tenant, item, "item", as_json, system=system)


@instance_app.command("show")
def instance_show(
    ctx: typer.Context,
    instance: str,
    tenant: Tenant,
    system: SystemOption = None,
    as_json: Json = False,
) -> None:
    """Read an item instance by id, link name or exact title."""
    show(ctx, tenant, instance, "item_instance", as_json, system=system)


@being_app.command("show")
def being_show(
    ctx: typer.Context,
    being: str,
    tenant: Tenant,
    system: SystemOption = None,
    campaign: Annotated[
        str | None,
        typer.Option(
            "--campaign", help="Its sheet as this campaign shows it (its system's template)."
        ),
    ] = None,
    template: Annotated[
        str | None, typer.Option("--template", help="Its sheet through this template.")
    ] = None,
    as_json: Json = False,
) -> None:
    """Read a being by id, link name or exact name, with equipped weapons and abilities."""
    show(ctx, tenant, being, "being", as_json, system=system, campaign=campaign, template=template)


@being_app.command("create")
def being_create(
    ctx: typer.Context,
    name: str,
    tenant: Tenant,
    parent: Annotated[
        list[str] | None,
        typer.Option("--parent", help="An entry it inherits from, by slug or id; repeat."),
    ] = None,
    slug: Annotated[str | None, typer.Option("--slug", help="Its link name.")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    as_json: Json = False,
) -> None:
    """Make a being, inheriting from the entries named (an operative type, a class, a person)."""
    from lorenzo_cli.client.models import EntityCreate
    from lorenzo_cli.runtime import may_write

    with session(ctx, tenant, writes=True) as (client, tid):
        parents = []
        for ref in parent or []:
            try:
                parents.append(UUID(ref))
            except ValueError:
                parents.append(
                    client.call(
                        ops.GET_ENTITY_BY_SLUG, path={"tenant_id": tid, "slug": ref}
                    ).value.id
                )
        under = f" under {', '.join(parent)}" if parent else ""
        may_write(ctx.obj, yes=yes, question=f"Make the being {name}{under}?", default=True)
        values: dict[str, Any] = {"name": name, "kinds": ["being"], "parents": parents}
        if slug is not None:
            values["slug"] = slug
        made = client.call(
            ops.CREATE_ENTITY, path={"tenant_id": tid}, body=EntityCreate(**values)
        ).value
    if as_json:
        console.emit(made.model_dump(mode="json"))
        return
    console.out.print(console.status("done", f"made {made.name}{under}."))
    console.out.print(str(made.id))
