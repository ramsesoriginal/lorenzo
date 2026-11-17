"""`lorenzo import` and `lorenzo export` (ADR 0484, ADR 0490): what comes in from a file and
goes out to one. Both are lazy groups, so `lorenzo import calendar` loads the calendar code and
nothing of the MPMB importer's."""

from __future__ import annotations

from typing import Any

import typer
from typer import _click as click  # typer vendors its own click; its classes are these

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
    "system": Entry(f"{_C}library", "export_app", "A system as a library document.", "system"),
    "neutral": Entry(
        f"{_C}library", "export_app", "The neutral vocabulary as a library document.", "neutral"
    ),
    "inventory": Entry(
        f"{_C}inventory", "app", "A character's inventory as a LorenzoLedger file.", "export"
    ),
    "calendar": Entry(_CALENDAR, "app", "The calendar a source key manages.", "export"),
}


class ImportGroup(LazyGroup):
    registry = IMPORTS


class ExportGroup(LazyGroup):
    """`lorenzo export SLUG` is `lorenzo export system SLUG` (ADR 0484): a name that is not one of
    the group's commands is a system's slug."""

    registry = EXPORTS

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and not args[0].startswith("-") and args[0] not in self.registry:
            command = self.get_command(ctx, "system")
            return "system", command, args
        found: Any = super().resolve_command(ctx, args)
        return found  # type: ignore[no-any-return]


import_app = typer.Typer(
    cls=ImportGroup,
    help="Import MPMB items, an inventory or a calendar.",
    no_args_is_help=True,
)
export_app = typer.Typer(
    cls=ExportGroup,
    help="Export a system, the neutral vocabulary, an inventory or a calendar.",
    no_args_is_help=True,
)


@import_app.callback()
def _import() -> None:
    """Import MPMB items, an inventory or a calendar."""


@export_app.callback()
def _export() -> None:
    """Export a system or the neutral vocabulary as a library document, or an inventory or a
    calendar as its own file. `lorenzo export SLUG` exports that system."""
