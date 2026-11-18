"""How a plan reads at a terminal: a short one row by row, a long one with what it creates counted
per kind and what it changes still listed (RFC 0057)."""

from __future__ import annotations

import uuid

import pytest
from rich.console import Console

from lorenzo_cli import console
from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.library.document import Document
from lorenzo_cli.library.planner import Action, Plan
from lorenzo_cli.library.render import print_plan

TENANT = TenantOut.model_construct(id=uuid.uuid4(), slug="table", name="Table")


def plan(creates: int, changes: int = 0) -> Plan:
    actions = [Action("create", "stat", f"wg_stat_{n}", "int in wg_traits") for n in range(creates)]
    actions += [Action("change", "stat", f"own_{n}", "unit: kg") for n in range(changes)]
    return Plan(Document(format=1, name="wg"), TENANT, actions=actions)


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch) -> tuple[Console, Console]:
    out = Console(record=True, width=120, force_terminal=False)
    err = Console(record=True, width=120, force_terminal=False, stderr=True)
    monkeypatch.setattr(console, "out", out)
    monkeypatch.setattr(console, "err", err)
    return out, err


def test_a_short_plan_lists_every_row(screen: tuple[Console, Console]) -> None:
    out, _ = screen
    print_plan(plan(3))

    text = out.export_text()
    assert "wg_stat_0" in text and "wg_stat_2" in text
    assert "how many" not in text


def test_a_long_plan_counts_what_it_creates_and_lists_what_it_changes(
    screen: tuple[Console, Console],
) -> None:
    out, err = screen
    print_plan(plan(200, changes=2))

    text = out.export_text()
    assert "200" in text and "wg_stat_0, wg_stat_1, wg_stat_2, and 197 more" in text
    assert "wg_stat_150" not in text
    assert "own_0" in text and "own_1" in text  # what already exists is always named
    assert "200 rows are counted, not listed" in err.export_text()


def test_full_lists_every_row_of_a_long_plan(screen: tuple[Console, Console]) -> None:
    out, _ = screen
    print_plan(plan(200), full=True)

    assert "wg_stat_150" in out.export_text()
