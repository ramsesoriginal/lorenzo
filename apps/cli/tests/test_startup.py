"""What `lorenzo` loads before it does anything (ADR 0483).

Each case runs in a fresh interpreter, since this test session has imported everything already.
A command group's modules, the generated models, the HTTP stack, the calendar engine and the MPMB
engine must not load for `--version`, the root's `--help` or a completion of the root; the time each
took is printed, as a record, and is not asserted on (a shared CI runner's timing is not ours).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

HEAVY = (
    "lorenzo_cli.commands",
    "lorenzo_cli.client",
    "lorenzo_cli.importer",
    "lorenzo_cli.inventory",
    "lorenzo_cli.seed",
    "lorenzo_cli.evalworker",
    "lorenzo_cli.calendar_commands",
    "lorenzo_cli.entry_commands",
    "lorenzo_cli.vocabulary_commands",
    "lorenzo_calendar",
    "py_mini_racer",
    "httpx",
)

PROBE = """
import io, json, os, sys
from contextlib import redirect_stdout
args = json.loads(sys.argv[1])
env = json.loads(sys.argv[2])
os.environ.update(env)
from lorenzo_cli.main import app
from typer.main import get_command
with redirect_stdout(io.StringIO()):
    try:
        get_command(app).main(args, prog_name="lorenzo", standalone_mode=False)
    except SystemExit:
        pass
print(json.dumps(sorted(sys.modules)), file=sys.stderr)
"""


def loaded(args: list[str], env: dict[str, str] | None = None) -> tuple[list[str], float]:
    started = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-c", PROBE, json.dumps(args), json.dumps(env or {})],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = time.perf_counter() - started
    modules: list[str] = json.loads(done.stderr.strip().splitlines()[-1])
    return modules, elapsed


def leaked(modules: list[str]) -> list[str]:
    return [m for m in modules if any(m == h or m.startswith(f"{h}.") for h in HEAVY)]


@pytest.mark.parametrize(
    ("args", "env"),
    [
        (["--version"], None),
        (["--help"], None),
        ([], {"_LORENZO_COMPLETE": "complete_bash", "COMP_WORDS": "lorenzo ", "COMP_CWORD": "1"}),
    ],
    ids=["version", "help", "completion"],
)
def test_the_root_loads_no_command_group(args: list[str], env: dict[str, str] | None) -> None:
    modules, elapsed = loaded(args, env)
    print(f"lorenzo {' '.join(args) or '<TAB>'}: {elapsed * 1000:.0f} ms, {len(modules)} modules")
    assert leaked(modules) == []


def test_a_group_loads_only_itself() -> None:
    modules, _ = loaded(["repo", "--help"])
    assert any(m == "lorenzo_cli.commands.repo" for m in modules)
    assert not any(
        m.startswith(("lorenzo_cli.commands.inventory", "lorenzo_calendar")) for m in modules
    )
    assert "py_mini_racer" not in modules


def test_import_and_export_list_their_commands_without_loading_them() -> None:
    modules, _ = loaded(["import", "--help"])
    assert leaked(modules) == ["lorenzo_cli.commands", "lorenzo_cli.commands.transfer"]


def test_importing_a_calendar_loads_nothing_of_the_mpmb_importer() -> None:
    modules, _ = loaded(["import", "calendar", "--help"])
    assert "lorenzo_cli.calendar_commands" in modules
    mpmb = (
        "lorenzo_cli.commands.mpmb",
        "lorenzo_cli.evalworker",
        "lorenzo_cli.importer.mapping",
        "lorenzo_cli.importer.plan",
        "lorenzo_cli.importer.apply",
    )
    assert not any(m.startswith(mpmb) for m in modules)
