"""`lorenzo import` and `lorenzo export` (ADR 0490): what comes in from a file and goes out to one.
Both are lazy groups, so `lorenzo import calendar` loads the calendar code and nothing of the MPMB
importer's."""

from __future__ import annotations

import typer

from lorenzo_cli.lazy import Entry, LazyGroup

_C = "lorenzo_cli.commands."
_CALENDAR = "lorenzo_cli.calendar_commands"

IMPORTS: dict[str, Entry] = {
    "mpmb": Entry(f"{_C}mpmb", "app", "Plan, apply or inspect MPMB item files."),
    "inventory": Entry(
        f"{_C}inventory", "app", "A character's inventory from a LorenzoLedger file.", "import"
    ),
    "calendar": Entry(_CALENDAR, "app", "An authored calendar document.", "import"),
}

EXPORTS: dict[str, Entry] = {
    "inventory": Entry(
        f"{_C}inventory", "app", "A character's inventory as a LorenzoLedger file.", "export"
    ),
    "calendar": Entry(_CALENDAR, "app", "The calendar a source key manages.", "export"),
}


class ImportGroup(LazyGroup):
    registry = IMPORTS


class ExportGroup(LazyGroup):
    registry = EXPORTS


import_app = typer.Typer(
    cls=ImportGroup,
    help="Import MPMB items, an inventory or a calendar.",
    no_args_is_help=True,
)
export_app = typer.Typer(
    cls=ExportGroup, help="Export an inventory or a calendar.", no_args_is_help=True
)


@import_app.callback()
def _import() -> None:
    """Import MPMB items, an inventory or a calendar."""


@export_app.callback()
def _export() -> None:
    """Export an inventory or a calendar."""
