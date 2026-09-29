"""Showing what the JavaScript host read from a set of files (`lorenzo inspect`)."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.table import Table

from lorenzo_cli.evalworker import STANDARD_LISTS, EvalResult


def print_evaluation(console: Console, result: EvalResult) -> None:
    files = Table("file", "role", "result", title="Files", title_justify="left")
    for file in result.files:
        status = "[green]ok[/green]" if file.status == "ok" else f"[red]{file.error}[/red]"
        files.add_row(file.name, file.role, status)
    console.print(files)

    lists = Table("list", "entries", "from", title="Lists", title_justify="left")
    for name in STANDARD_LISTS:
        origins = Counter(result.origins.get(name, {}).values())
        sources = ", ".join(f"{file or '?'} ({count})" for file, count in origins.most_common())
        lists.add_row(name, str(result.counts.get(name, 0)), sources)
    console.print(lists)

    others = {
        name: count for name, count in result.counts.items() if name not in STANDARD_LISTS and count
    }
    if others:
        console.print(
            "Read but not imported (RFC 0025 is standard items only): "
            + ", ".join(f"{name} {count}" for name, count in sorted(others.items()))
        )
    if result.stubs:
        console.print(
            "Names the sheet supplies that were stubbed: "
            + ", ".join(f"{s.name} ({s.calls})" for s in result.stubs)
        )
    if result.stubs_in_data:
        console.print(
            f"[yellow]{len(result.stubs_in_data)} value(s) came from a stubbed sheet call and "
            "are unknown; the first is "
            f"{result.stubs_in_data[0].path}.[/yellow]"
        )
