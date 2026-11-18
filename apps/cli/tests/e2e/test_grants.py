"""Features, grant rules and grants against the real API (ADR 0502): in a document, applied, found
again and exported; a choice answered with --pick; a feature awarded, switched off and removed."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack

DOCUMENT = """
format = 1
name = "ft"

[system]
slug = "ft"
name = "Feature Test"
root = "ft-root"

[[group]]
name = "ft_core"
system = true

[[stat]]
name = "ft_level"
group = "ft_core"
type = "int"

[[entry]]
slug = "ft-root"
name = "Feature Test"

[[entry]]
slug = "ft-styles"
name = "Fighting styles"
parents = ["ft-root"]

[[entry]]
slug = "ft-archery"
name = "Archery"
kinds = ["feature"]
parents = ["ft-styles"]

[[entry]]
slug = "ft-defence"
name = "Defence"
kinds = ["feature"]
parents = ["ft-styles"]

[[entry]]
slug = "ft-second-wind"
name = "Second wind"
kinds = ["feature"]
parents = ["ft-root"]
prerequisites = [{ stat = "ft_level", comparator = "ge", value = 2 }]

[[entry]]
slug = "ft-fighter"
name = "Fighter"
parents = ["ft-root"]

[[entry]]
slug = "ft-hero"
name = "Hero"
kinds = ["being"]
parents = ["ft-fighter"]
stats = { ft_level = 1 }

[[grant_rule]]
on = "ft-fighter"
label = "Fighting style"
mode = "choose"
min = 1
max = 1
options = ["ft-archery", "ft-defence"]

[[grant_rule]]
on = "ft-fighter"
label = "Second wind"
mode = "all"
options = ["ft-second-wind"]
"""


def test_features_rules_and_grants(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("grants")
    tenant = make_tenant(stack, token, kind="play")
    (tmp_path / "ft.toml").write_text(DOCUMENT, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    applied = cli("apply", str(tmp_path / "ft.toml"), "-t", tenant, "--yes")
    assert applied.exit_code == 0, applied.output
    again = cli("plan", str(tmp_path / "ft.toml"), "-t", tenant)
    assert again.exit_code == 0, again.output

    exported = tomllib.loads(cli("export", "ft", "-t", tenant).stdout)
    assert {r["label"] for r in exported["grant_rule"]} == {"Fighting style", "Second wind"}
    wind = next(e for e in exported["entry"] if e["slug"] == "ft-second-wind")
    assert wind["prerequisites"] == [{"stat": "ft_level", "comparator": "ge", "value": 2.0}]

    rules = json.loads(
        cli("grant-rule", "list", "--on", "ft-fighter", "-t", tenant, "--json").stdout
    )
    assert len(rules["grant_rules"]) == 2
    shown = cli("grant-rule", "show", "ft-fighter:Fighting style", "-t", tenant)
    assert 'mode = "choose"' in shown.output

    state = json.loads(cli("grants", "show", "ft-hero", "-t", tenant, "--json").stdout)
    assert [c["label"] for c in state["open_choices"]] == ["Fighting style"]

    unanswered = cli("grants", "apply", "ft-hero", "-t", tenant)
    assert unanswered.exit_code == 2, unanswered.output  # a choice is open, nothing was written

    picked = cli(
        "grants", "apply", "ft-hero", "-t", tenant, "--pick", "Fighting style=Archery", "--yes"
    )
    assert picked.exit_code == 0, picked.output
    held = json.loads(cli("grants", "show", "ft-hero", "-t", tenant, "--json").stdout)["held"]
    assert [h["feature"]["name"] for h in held] == ["Archery"]  # level 1: no second wind yet

    awarded = cli("feature", "award", "ft-defence", "--to", "ft-hero", "-t", tenant, "--yes")
    assert awarded.exit_code == 0, awarded.output
    off = cli("feature", "deactivate", "ft-defence", "--on", "ft-hero", "-t", tenant, "--yes")
    assert off.exit_code == 0, off.output
    gone = cli("feature", "remove", "ft-defence", "--from", "ft-hero", "-t", tenant, "--yes")
    assert gone.exit_code == 0, gone.output

    feature = json.loads(cli("feature", "show", "ft-archery", "-t", tenant, "--json").stdout)
    assert [r["label"] for r in feature["granted_by"]] == ["Fighting style"]
    listed = json.loads(cli("feature", "list", "-t", tenant, "--system", "ft", "--json").stdout)
    assert {f["name"] for f in listed["features"]} == {"Archery", "Defence", "Second wind"}
    archery = next(f for f in listed["features"] if f["name"] == "Archery")
    assert archery["slug"] == "ft-archery" and archery["under"] == ["Fighting styles"]
    table = " ".join(cli("feature", "list", "-t", tenant, "--system", "ft").output.split())
    assert "Archery ft-archery Fighting styles" in table
