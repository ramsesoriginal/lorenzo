"""`lorenzo check` against the real API (ADR 0489): findings grouped by entry, filtered, counted,
and an exit code for CI only when asked."""

from __future__ import annotations

import json
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack

DOCUMENT = """
format = 1
name = "ck"

[[group]]
name = "ck_numbers"

[[stat]]
name = "ck_base"
group = "ck_numbers"
type = "int"

[[stat]]
name = "ck_total"
group = "ck_numbers"
type = "int"
max = 10

[[entry]]
slug = "ck-thing"
name = "Thing"

[[entry]]
slug = "ck-big"
name = "Big thing"
parents = ["ck-thing"]
stats = { ck_base = 40 }

[[formula]]
on = "ck-thing"
stat = "ck_total"
kind = "linear"
source = "ck_base"
multiplier = 1
"""


def test_the_check_reports_and_fails_only_when_asked(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("check")
    tenant = make_tenant(stack, token, kind="play")
    (tmp_path / "ck.toml").write_text(DOCUMENT, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    applied = cli("apply", str(tmp_path / "ck.toml"), "-t", tenant, "--yes")
    assert applied.exit_code == 0, applied.output
    assert "lorenzo check" in applied.output  # the write points at the check, and does not run it

    found = cli("check", "-t", tenant, "--json")
    assert found.exit_code == 0, found.output  # a read: findings are not a failure
    document = json.loads(found.stdout)
    codes = {f["code"] for f in document["findings"]}
    assert "unset-input" in codes  # Thing's total reads a base it does not hold
    assert "computed-outside-scale" in codes  # Big thing's total is 40, its scale ends at 10
    big = [f for f in document["findings"] if f["entry"] == "Big thing"]
    assert {f["code"] for f in big} >= {"computed-outside-scale"}

    only = json.loads(cli("check", "-t", tenant, "--code", "unset-input", "--json").stdout)
    assert {f["code"] for f in only["findings"]} == {"unset-input"}
    one = json.loads(cli("check", "-t", tenant, "--entry", "ck-big", "--json").stdout)
    assert {f["entry"] for f in one["findings"]} == {"Big thing"}

    for_ci = cli("check", "-t", tenant, "--fail-on", "warning")
    assert for_ci.exit_code == 1  # unset-input is a warning
    read = cli("check", "-t", tenant)
    assert "Big thing" in read.output and "in 2 entries" in read.output
