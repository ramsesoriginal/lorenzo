"""`lorenzo-convert`: one subcommand per source (ADR 0243)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

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
