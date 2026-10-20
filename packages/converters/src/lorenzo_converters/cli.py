"""`lorenzo-convert`: one subcommand per source (ADR 0246)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from lorenzo_converters import donjon as donjon_converter
from lorenzo_converters import ledger
from lorenzo_converters.sheet import ConversionError, convert

app = typer.Typer(
    help="Simple converters from files players already have into a LorenzoLedger.",
    no_args_is_help=True,
    add_completion=False,
)
err = Console(stderr=True)


@app.callback()
def main() -> None:
    """Convert a file into a ledger: pick the kind of file."""


@app.command()
def sheet(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help=".xlsx or .csv file")],
    owner: Annotated[str, typer.Option("--owner", "-o", help="The character the ledger is for")],
    output: Annotated[
        Path | None, typer.Option("--output", "-O", help="Write here instead of to the screen")
    ] = None,
    home: Annotated[
        str | None,
        typer.Option(
            help="The place that means 'with the character'; containers elsewhere get place:"
        ),
    ] = None,
    equipped: Annotated[
        str | None,
        typer.Option(help="A container that means 'in hand' (holding, equipped, hands… always do)"),
    ] = None,
) -> None:
    """A spreadsheet inventory (Items and Container tables) as a ledger to import."""
    try:
        result = convert(file, owner, home=home, equipped=equipped)
    except ConversionError as error:
        err.print(f"[red]{error}[/red]", highlight=False)
        raise typer.Exit(1) from error
    text = ledger.render(result.ledger)
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.write_text(text, encoding="utf-8")
    for warning in result.warnings:
        err.print(f"[yellow]warning:[/yellow] {warning}", highlight=False)
    for note in result.notes:
        err.print(note, highlight=False)
    if output is not None:
        err.print(
            f"Written to {output}. Check it, then: lorenzo inventory import {output} --dry-run"
        )


@app.command()
def donjon(
    files: Annotated[list[Path], typer.Argument(help="One or more saved donjon JSON exports")],
    name: Annotated[str, typer.Option(help="Name of the authored calendar")],
    source_key: Annotated[
        str, typer.Option(help="Stable local source key, reused for later imports")
    ],
    reference_year: Annotated[int, typer.Option(help="Exported year to anchor weekdays and moons")],
    output: Annotated[Path | None, typer.Option("--output", "-O")] = None,
    unescape_html: Annotated[
        bool, typer.Option(help="Decode one layer of HTML entities, retaining original text")
    ] = False,
) -> None:
    """Convert saved donjon calendars into a native Lorenzo calendar JSON document, offline."""
    try:
        if sum(file.stat().st_size for file in files) > donjon_converter.MAX_SOURCE_BYTES:
            raise donjon_converter.DonjonError("Calendar source exceeds the 2 MB limit")
        text = "\n".join(file.read_text(encoding="utf-8-sig") for file in files)
        document = donjon_converter.convert(
            text,
            name=name,
            source_key=source_key,
            reference_year=reference_year,
            unescape_html=unescape_html,
        )
        rendered = document.model_dump_json(indent=2) + "\n"
        if output is None:
            typer.echo(rendered, nl=False)
        else:
            output.write_text(rendered, encoding="utf-8")
    except (OSError, UnicodeError, ValidationError, donjon_converter.DonjonError) as error:
        err.print(str(error), markup=False, highlight=False)
        raise typer.Exit(1) from error
    for warning in document.warnings:
        err.print(f"warning [{warning.key}]: {warning.message}", markup=False, highlight=False)
