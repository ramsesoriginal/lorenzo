"""`lorenzo template` (ADR 0501): a library's templates, what an entry matches, and an entry
read through one. A template's slots are many and nested, so it is written in a file, as in a
document."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import typer
from rich.table import Table
from rich.text import Text

from lorenzo_cli import completers, console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import (
    StatDefinitionOut,
    StatGroupOut,
    SystemOut,
    TemplateOut,
    TemplateSummaryOut,
    TemplateViewOut,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.library import templates
from lorenzo_cli.library.document import TemplateRow
from lorenzo_cli.runtime import _client, _reporting_errors, may_write
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.sheet_view import print_view
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

app = typer.Typer(
    help="List, read, create or delete templates, and read an entry through one.",
    no_args_is_help=True,
)

Json = Annotated[bool, typer.Option("--json", help="Print one JSON document.")]
SystemOption = Annotated[
    str | None,
    typer.Option(
        "--system",
        help="Only this system's templates and the neutral ones.",
        autocompletion=completers.system,
    ),
]
NameArgument = Annotated[
    str, typer.Argument(help="The template's name or id.", autocompletion=completers.template)
]


class _Library:
    def __init__(self, client: LorenzoClient, tenant_id: UUID) -> None:
        self.client = client
        self.path = {"tenant_id": tenant_id}

    def systems(self) -> dict[str, SystemOut]:
        rows = all_items(self.client, ops.LIST_SYSTEMS, path=self.path, of=SystemOut)
        return {s.slug: s for s in rows}

    def groups(self) -> dict[str, StatGroupOut]:
        rows = all_items(self.client, ops.LIST_STAT_GROUPS, path=self.path, of=StatGroupOut)
        return {g.name: g for g in rows}

    def stats(self) -> dict[str, StatDefinitionOut]:
        rows = all_items(
            self.client, ops.LIST_STAT_DEFINITIONS, path=self.path, of=StatDefinitionOut
        )
        return {s.name: s for s in rows}

    def summaries(self, system: str | None = None) -> list[TemplateSummaryOut]:
        return list(
            all_items(
                self.client,
                ops.LIST_TEMPLATES,
                path=self.path,
                query={"system": system},
                of=TemplateSummaryOut,
            )
        )

    def template(self, reference: str) -> TemplateOut:
        rows = self.summaries()
        found = next((t for t in rows if t.name == reference or str(t.id) == reference), None)
        if found is None:
            known = ", ".join(t.name for t in rows) or "none yet"
            raise SelfServiceError(f"No template {reference} here (this library has: {known}).")
        return self.client.call(ops.GET_TEMPLATE, path={**self.path, "template_id": found.id}).value

    def entry_id(self, reference: str) -> UUID:
        try:
            return UUID(reference)
        except ValueError:
            return self.client.call(
                ops.GET_ENTITY_BY_SLUG, path={**self.path, "slug": reference}
            ).value.id

    def entry_slug(self, entry_id: UUID) -> str:
        found = self.client.call(ops.GET_ENTITY, path={**self.path, "entity_id": entry_id}).value
        return found.slug or str(found.id)


def _row(library: _Library, out: TemplateOut) -> TemplateRow:
    stats = {s.id: s.name for s in library.stats().values()}
    groups = {g.id: g.name for g in library.groups().values()}
    return templates.from_out(
        out,
        doc_system=None,
        group_name=lambda i: groups.get(i, str(i)),
        stat_name=lambda i: stats.get(i, str(i)),
        entry_slug=library.entry_slug,
    )


@app.command("list")
def template_list(
    ctx: typer.Context, tenant: TenantOption, system: SystemOption = None, as_json: Json = False
) -> None:
    """The library's templates: name, system, the kind and the ancestor an entry must have."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        rows = library.summaries(system)
    if as_json:
        console.emit({"templates": [r.model_dump(mode="json") for r in rows]})
        return
    if not rows:
        console.out.print("No templates yet: `lorenzo template create --from FILE`.")
        return
    table = Table("name", "system", "kind", box=None, pad_edge=False)
    for row in rows:
        kind = row.required_kind.value if row.required_kind else "any"
        table.add_row(Text(safe(row.name)), row.system or "", kind)
    console.out.print(table)


@app.command("show")
def template_show(
    ctx: typer.Context, template: NameArgument, tenant: TenantOption, as_json: Json = False
) -> None:
    """A template's filter and slots, by name, as a document writes them."""
    import tomli_w

    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        out = library.template(template)
        row = _row(library, out)
    if as_json:
        console.emit(out.model_dump(mode="json"))
        return
    dumped = row.model_dump(exclude_none=True, exclude_defaults=True)
    console.out.print(Text(safe(tomli_w.dumps({"template": [{"name": row.name, **dumped}]}))))


def _load(path: Path) -> TemplateRow:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SelfServiceError(f"Couldn't read {path}: {exc}") from exc
    rows = data.get("template", [data])
    if not isinstance(rows, list) or len(rows) != 1:
        raise SelfServiceError(f"{path} holds {len(rows)} templates; give one file per template.")
    try:
        return TemplateRow.model_validate(rows[0])
    except ValueError as exc:
        raise SelfServiceError(f"{path}: {exc}") from exc


@app.command("create")
def template_create(
    ctx: typer.Context,
    tenant: TenantOption,
    from_file: Annotated[
        Path, typer.Option("--from", dir_okay=False, help="A TOML file with one [[template]].")
    ],
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    as_json: Json = False,
) -> None:
    """Create a template from a file, or replace the one of that name (the API replaces it
    whole). `system` in the file is a system's slug, or false for a template of none."""
    row = _load(from_file)
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        systems, groups, stats = library.systems(), library.groups(), library.stats()

        def need(table: dict[str, Any], name: str, what: str) -> UUID:
            if name not in table:
                raise SelfServiceError(f"No {what} {name} here.")
            return UUID(str(table[name].id))

        body = templates.to_body(
            row,
            doc_system=None,
            system_id=lambda slug: need(systems, slug, "system"),
            group_id=lambda name: need(groups, name, "stat group"),
            stat_id=lambda name: need(stats, name, "stat"),
            entry_id=library.entry_id,
        )
        existing = next((t for t in library.summaries() if t.name == row.name), None)
        verb = "Replace" if existing else "Create"
        may_write(ctx.obj, yes=yes, question=f"{verb} the template {row.name}?", default=True)
        if existing is None:
            made = client.call(ops.CREATE_TEMPLATE, path=library.path, body=body).value
        else:
            made = client.call(
                ops.REPLACE_TEMPLATE,
                path={**library.path, "template_id": existing.id},
                body=body,
            ).value
    if as_json:
        console.emit(made.model_dump(mode="json"))
    else:
        done = "replaced" if existing else "created"
        console.out.print(console.status("done", f"{done} {made.name}, {len(made.slots)} slots."))


@app.command("delete")
def template_delete(
    ctx: typer.Context,
    template: NameArgument,
    tenant: TenantOption,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before deleting.")] = False,
) -> None:
    """Delete a template; a sheet that read it reads another, or none."""
    with _reporting_errors(), _client(ctx.obj, writes=True) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        out = library.template(template)
        may_write(ctx.obj, yes=yes, question=f"Delete the template {out.name}?")
        client.call(ops.DELETE_TEMPLATE, path={**library.path, "template_id": out.id})
    console.out.print(console.status("done", f"deleted {out.name}."))


@app.command("matching")
def template_matching(
    ctx: typer.Context,
    entry: Annotated[str, typer.Argument(help="The entry: its slug or id.")],
    tenant: TenantOption,
    system: SystemOption = None,
    as_json: Json = False,
) -> None:
    """The templates an entry matches: its kind and its ancestors."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        rows = client.call(
            ops.MATCHING_TEMPLATES,
            path={**library.path, "entity_id": library.entry_id(entry)},
            query={"system": system},
        ).value
    if as_json:
        console.emit({"templates": [r.model_dump(mode="json") for r in rows]})
        return
    if not rows:
        console.out.print(f"{entry} matches no template.")
        return
    for row in rows:
        console.out.print(Text(f"{safe(row.name)}  {row.system or ''}".rstrip()))


@app.command("view")
def template_view(
    ctx: typer.Context,
    entry: Annotated[str, typer.Argument(help="The entry: its slug or id.")],
    template: NameArgument,
    tenant: TenantOption,
    as_json: Json = False,
) -> None:
    """An entry read through a template, slot by slot, as a sheet shows it."""
    with _reporting_errors(), _client(ctx.obj) as client:
        library = _Library(client, resolve_tenant(client, tenant).id)
        out = library.template(template)
        view: TemplateViewOut = client.call(
            ops.READ_THROUGH_TEMPLATE,
            path={**library.path, "entity_id": library.entry_id(entry), "template_id": out.id},
        ).value
        definitions = {} if as_json else {s.id: s for s in library.stats().values()}
    if as_json:
        console.emit(view.model_dump(mode="json"))
        return
    print_view(view, definitions)
