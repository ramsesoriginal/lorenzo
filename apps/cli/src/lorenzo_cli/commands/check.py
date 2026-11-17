"""`lorenzo check` (ADR 0489): the vocabulary check of RFC 0055 for a person and for CI. It
reads; it writes and refuses nothing. Findings are grouped by entry, the library's own first,
each with its severity as a symbol and a word, and a count at the end; `--fail-on` turns them
into an exit code."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal
from uuid import UUID

import typer
from rich.text import Text

from lorenzo_cli import console
from lorenzo_cli.client import ops
from lorenzo_cli.client.models import FindingOut, StatDefinitionOut
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.runtime import _client, _reporting_errors
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.tenants import resolve_tenant
from lorenzo_cli.terminal_script import safe

app = typer.Typer()

# The API's severity, said in words a person reads.
SAID = {"warning": ("warning", "warning"), "info": ("note", "note")}
CODES = (
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
    "tie",
)


@app.command("check")
def check(
    ctx: typer.Context,
    tenant: TenantOption,
    code: Annotated[
        list[str] | None, typer.Option("--code", help=f"Only these: {', '.join(CODES)}; repeat.")
    ] = None,
    entry: Annotated[
        str | None, typer.Option("--entry", help="Only this entry (its slug or id).")
    ] = None,
    parent: Annotated[
        str | None, typer.Option("--parent", help="Only what is under this entry (its slug or id).")
    ] = None,
    direct: Annotated[
        bool, typer.Option("--direct", help="With --parent: only its children, not all below it.")
    ] = False,
    kind: Annotated[str | None, typer.Option("--kind", help="Only entries of this kind.")] = None,
    stat: Annotated[
        str | None, typer.Option("--stat", help="Only findings about this stat.")
    ] = None,
    severity: Annotated[
        Literal["warning", "info"] | None,
        typer.Option("--severity", help="Only warnings, or only notes (info)."),
    ] = None,
    fail_on: Annotated[
        Literal["warning", "info"] | None,
        typer.Option(
            "--fail-on", help="Exit 1 on a warning, or (info) on any finding: for a script or CI."
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print one JSON document.")] = False,
) -> None:
    """Check a library's stats for what they get wrong without saying so: an unset input, an own
    value that shadows a formula, a tie, a value outside its scale or beyond its hint, a long
    formula chain. Exit 0 whatever it finds, unless --fail-on says otherwise."""
    unknown = [c for c in code or [] if c not in CODES]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(CODES)}.")
    with _reporting_errors(), _client(ctx.obj) as client:
        target = resolve_tenant(client, tenant)
        path = {"tenant_id": target.id}

        def entry_id(reference: str) -> UUID:
            try:
                return UUID(reference)
            except ValueError:
                return client.call(
                    ops.GET_ENTITY_BY_SLUG, path={**path, "slug": reference}
                ).value.id

        stats = {
            s.name: s
            for s in all_items(client, ops.LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
        }
        if stat is not None and stat not in stats:
            raise SelfServiceError(f"No stat called {stat} here.")
        query = {
            "code": code or None,
            "entry_id": str(entry_id(entry)) if entry else None,
            "parent_id": str(entry_id(parent)) if parent else None,
            "recursive": not direct if parent else None,
            "kind": kind,
            "stat_definition_id": str(stats[stat].id) if stat else None,
        }
        with console.waiting(f"Checking {target.slug}"):
            findings = [
                f
                for f in all_items(
                    client, ops.CHECK_VOCABULARY, path=path, query=query, of=FindingOut
                )
                if severity is None or f.severity.value == severity
            ]
        ids = sorted({f.entry_id for f in findings if f.entry_id is not None})

        def name(entry_uuid: UUID) -> tuple[UUID, str]:
            found = client.call(ops.GET_ENTITY, path={**path, "entity_id": entry_uuid}).value
            return entry_uuid, found.name

        with ThreadPoolExecutor(max_workers=4) as pool:
            names = dict(pool.map(name, ids))
    counts = Counter(f.severity.value for f in findings)
    failed = (fail_on == "warning" and counts["warning"] > 0) or (fail_on == "info" and findings)
    if as_json:
        console.emit(
            {
                "library": target.slug,
                "findings": [
                    {
                        **f.model_dump(mode="json"),
                        "entry": names.get(f.entry_id) if f.entry_id else None,
                    }
                    for f in findings
                ],
                "counts": {"warning": counts["warning"], "info": counts["info"]},
                "entries": len(ids),
            }
        )
        raise typer.Exit(1 if failed else 0)
    if not findings:
        console.out.print(console.status("done", f"nothing found in {target.slug}."))
        raise typer.Exit(0)
    by_entry: dict[UUID | None, list[FindingOut]] = {}
    for finding in findings:
        by_entry.setdefault(finding.entry_id, []).append(finding)
    order = sorted(by_entry, key=lambda e: (e is not None, names.get(e, "") if e else ""))
    for key in order:
        heading = "The library" if key is None else names.get(key, str(key))
        console.out.print(Text(safe(heading), style="bold"))
        for finding in by_entry[key]:
            symbol_word = "warning" if finding.severity.value == "warning" else "note"
            label = console.status(
                symbol_word, Text(f"{finding.code.value}  {safe(finding.message)}")
            )
            console.out.print(Text("  ").append(label))
    warnings, notes = counts["warning"], counts["info"]
    said = f"{warnings} warning{'s' * (warnings != 1)}, {notes} note{'s' * (notes != 1)}"
    console.out.print(Text(f"{said} in {len(ids)} entr{'ies' if len(ids) != 1 else 'y'}."))
    raise typer.Exit(1 if failed else 0)
