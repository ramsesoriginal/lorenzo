"""Formulas against the real API (ADR 0500): in a document, applied, found again and exported; and
one at a time with `lorenzo formula`."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack

DOCUMENT = """
format = 1
name = "tt"

[system]
slug = "tt"
name = "Test Tables"
root = "tt-root"

[[group]]
name = "tt_core"
system = true

[[stat]]
name = "tt_strength"
group = "tt_core"
type = "int"
min = 1
max = 30

[[stat]]
name = "tt_strength_mod"
group = "tt_core"
type = "int"

[[stat]]
name = "tt_level"
group = "tt_core"
type = "int"

[[stat]]
name = "tt_proficiency"
group = "tt_core"
type = "int"

[[stat]]
name = "tt_damage"
group = "tt_core"
type = "dice"

[[entry]]
slug = "tt-root"
name = "Test Tables"

[[entry]]
slug = "tt-character"
name = "Character"
parents = ["tt-root"]

[[entry]]
slug = "tt-fighter"
name = "Fighter"
parents = ["tt-character"]
stats = { tt_strength = 16, tt_level = 5 }

[[formula]]
on = "tt-character"
stat = "tt_strength_mod"
kind = "linear"
source = "tt_strength"
multiplier = 0.5
offset = -5
round = "floor"

[[formula]]
on = "tt-character"
stat = "tt_proficiency"
kind = "select"
source = "tt_level"
mode = "threshold"
steps = [
  { from = 1, result = { number = 2 } },
  { from = 5, result = { number = 3 } },
  { from = 9, result = { number = 4 } },
]

[[formula]]
on = "tt-character"
stat = "tt_damage"
kind = "dice"
count = "tt_proficiency"
sides_constant = 6
"""


def test_formulas_in_a_document_are_applied_found_again_and_exported(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("formula-document")
    tenant = make_tenant(stack, token)
    path = tmp_path / "tt.toml"
    path.write_text(DOCUMENT, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    applied = cli("apply", str(path), "-t", tenant, "--yes")
    assert applied.exit_code == 0, applied.output
    again = cli("plan", str(path), "-t", tenant)
    assert again.exit_code == 0, again.output  # the formulas read back as the document wrote them

    preview = json.loads(
        cli(
            "formula", "preview", "tt_strength_mod", "--on", "tt-fighter", "-t", tenant, "--json"
        ).stdout
    )
    assert preview["value"] == 3 and preview["source"] == "computed"  # floor(16 / 2 - 5)
    damage = json.loads(
        cli("formula", "preview", "tt_damage", "--on", "tt-fighter", "-t", tenant, "--json").stdout
    )
    assert str(damage["value"]).lower() in ("3d6",)  # proficiency at level 5 is 3

    exported = tomllib.loads(cli("export", "tt", "-t", tenant).stdout)
    kinds = {(f["on"], f["stat"]): f["kind"] for f in exported["formula"]}
    assert kinds == {
        ("tt-character", "tt_strength_mod"): "linear",
        ("tt-character", "tt_proficiency"): "select",
        ("tt-character", "tt_damage"): "dice",
    }

    changed = DOCUMENT.replace("offset = -5", "offset = -4")
    path.write_text(changed, encoding="utf-8")
    planned = json.loads(cli("plan", str(path), "-t", tenant, "--json").stdout)
    assert [(a["verb"], a["kind"], a["key"]) for a in planned["actions"]] == [
        ("change", "formula", "tt-character: tt_strength_mod")
    ]


def test_one_formula_at_a_time(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("formula-rows")
    tenant = make_tenant(stack, token)
    (tmp_path / "tt.toml").write_text(DOCUMENT, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    assert cli("apply", str(tmp_path / "tt.toml"), "-t", tenant, "--yes").exit_code == 0

    too_few = cli(
        "formula", "set", "tt_proficiency", "--on", "tt-fighter", "-t", tenant,
        "--kind", "max", "--input", "tt_strength", "--yes",
    )  # fmt: skip
    assert too_few.exit_code == 1 and "inputs" in too_few.output  # refused before any request

    capped = cli(
        "formula", "set", "tt_proficiency", "--on", "tt-fighter", "-t", tenant,
        "--kind", "min", "--input", "tt_strength", "--input", "3", "--yes",
    )  # fmt: skip
    assert capped.exit_code == 0, capped.output
    shown = json.loads(
        cli(
            "formula", "show", "tt_proficiency", "--on", "tt-fighter", "-t", tenant, "--json"
        ).stdout
    )
    assert shown["kind"] == "min" and shown["fields"]["inputs"] == ["tt_strength", 3]

    inherited = cli("formula", "show", "tt_strength_mod", "--on", "tt-fighter", "-t", tenant)
    assert "inherited from Character" in inherited.output

    tree = json.loads(
        cli("formula", "tree", "tt_damage", "--on", "tt-fighter", "-t", tenant, "--json").stdout
    )
    assert tree["chain"]["kind"] == "dice"
    assert [i["stat"] for i in tree["chain"]["inputs"]] == ["tt_proficiency"]
    readers = json.loads(
        cli("formula", "tree", "tt_level", "--on", "tt-fighter", "-t", tenant, "--json").stdout
    )
    assert {r["stat"] for r in readers["read_by"]} == {"tt_proficiency"}

    gone = cli("formula", "delete", "tt_proficiency", "--on", "tt-fighter", "-t", tenant, "--yes")
    assert gone.exit_code == 0, gone.output
    back = cli("formula", "show", "tt_proficiency", "--on", "tt-fighter", "-t", tenant)
    assert "inherited from Character" in back.output  # its own is gone, the inherited one stays
    none = cli("formula", "show", "tt_level", "--on", "tt-fighter", "-t", tenant)
    assert "has no formula" in none.output
