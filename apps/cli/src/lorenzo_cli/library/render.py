"""A plan and its result, for a person (a table with a symbol and a word on every row) and as
`--json` (ADR 0481)."""

from __future__ import annotations

from typing import Any

from rich.table import Table
from rich.text import Text

from lorenzo_cli import console
from lorenzo_cli.library.planner import Plan
from lorenzo_cli.library.writer import Result
from lorenzo_cli.terminal_script import safe


def plan_json(plan: Plan, result: Result | None = None) -> dict[str, Any]:
    document: dict[str, Any] = {
        "document": plan.document.name,
        "library": plan.tenant.slug,
        "prune": plan.prune,
        "counts": plan.counts(),
        "actions": [a.as_json() for a in plan.actions],
        "problems": plan.problems,
        "notes": plan.notes,
    }
    if result is not None:
        document["result"] = result.as_json()
    return document


def counts_line(plan: Plan) -> str:
    counts = plan.counts()
    said = [f"{counts['create']} to create", f"{counts['change']} to change"]
    if plan.prune:
        said.append(f"{counts['remove']} to remove")
    return ", ".join(said)


def print_plan(plan: Plan) -> None:
    out = console.out
    out.print(
        Text(f"{plan.document.name} into {plan.tenant.slug}: {counts_line(plan)}."), soft_wrap=True
    )
    if plan.actions:
        table = Table("", "what", "name", "detail", box=None, pad_edge=False)
        for action in plan.actions:
            table.add_row(
                console.status(action.verb),
                action.kind,
                Text(safe(action.key)),
                Text(safe(action.detail)),
            )
        out.print(table)
    for note in plan.notes:
        console.err.print(console.status("note", note), soft_wrap=True)
    for problem in plan.problems:
        console.err.print(console.status("refused", problem), soft_wrap=True)


def print_result(result: Result) -> None:
    done = len(result.done)
    console.out.print(console.status("done", f"{done} written."), soft_wrap=True)
    for action, why in result.failed:
        console.error(f"{action.verb} {action.kind} {action.key}: {why}")
    if result.skipped:
        console.warning(
            f"{len(result.skipped)} not written, after the failure; apply again to finish."
        )
