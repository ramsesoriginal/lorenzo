"""An entry read through a template, drawn slot by slot as a sheet (ADR 0451, ADR 0501): for
`template view`, and for `being show` when a campaign or a template names the sheet."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rich.table import Table
from rich.text import Text

from lorenzo_cli import console
from lorenzo_cli.client.models import TemplateViewOut
from lorenzo_cli.terminal_script import safe


def _value(value: Any, definition: Any) -> str:
    from lorenzo_cli.entry_commands import formatted

    return "unknown" if value is None else formatted(value, definition)


def print_view(view: TemplateViewOut, definitions: dict[UUID, Any]) -> None:
    """`definitions` by id: what says a value is signed, and its unit."""
    out = console.out
    out.print(Text(f"{safe(view.entity.name)} as {safe(view.template.name)}", style="bold"))
    for slot in view.slots:
        out.print(Text(f"\n{safe(slot.label or slot.kind.value.capitalize())}", style="bold"))
        shown = _print_slot(slot, definitions)
        if not shown:
            out.print(Text("  none", style="dim"))


def _print_slot(slot: Any, definitions: dict[UUID, Any]) -> bool:
    out = console.out
    shown = False
    stats = [*(slot.stats or []), *(slot.tags or [])]
    if stats:
        table = Table(box=None, pad_edge=False, show_header=False)
        table.add_column("stat")
        table.add_column("value", justify="right")
        for stat in stats:
            table.add_row(
                Text(safe(stat.label or stat.name)),
                _value(stat.value, definitions.get(stat.stat_definition_id)),
            )
        out.print(table)
        shown = True
    for info in slot.information or []:
        out.print(Text(f"  {safe(info.title)}"))
        shown = True
    if slot.rows:
        columns = list(slot.columns or [])
        table = Table(box=None, pad_edge=False)
        table.add_column("")
        table.add_column("qty", justify="right")
        for column in columns:
            table.add_column(safe(column.label or column.name), justify="right")
        for row in slot.rows:
            cells = {c.stat_definition_id: c.value for c in row.cells}
            table.add_row(
                Text(safe(row.entity.name)),
                str(row.quantity or 1),
                *[
                    _value(cells.get(c.stat_definition_id), definitions.get(c.stat_definition_id))
                    for c in columns
                ],
            )
        out.print(table)
        shown = True
    for group in slot.feature_groups or []:
        names = [f.name + ("" if f.active else " (off)") for f in group.features]
        if not names:
            continue
        under = f"{group.type.name}: " if group.type is not None else ""
        out.print(Text(f"  {safe(under)}{safe(', '.join(names))}"))
        shown = True
    return shown
