"""Templates, campaigns and beings against the real API (ADR 0487): a template in a document,
applied, found again and exported; one from a file; a campaign playing the system; a being made
under the system's types and read as the campaign shows it."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack

DOCUMENT = """
format = 1
name = "kt"

[system]
slug = "kt"
name = "Squad Tactics"
root = "kt-root"

[[group]]
name = "kt_profile"
system = true

[[stat]]
name = "kt_move"
group = "kt_profile"
type = "int"

[[stat]]
name = "kt_wounds"
group = "kt_profile"
type = "int"
min = 1

[[entry]]
slug = "kt-root"
name = "Squad Tactics"

[[entry]]
slug = "kt-operative"
name = "Operative"
kinds = ["item"]
parents = ["kt-root"]

[[entry]]
slug = "kt-gunner"
name = "Gunner"
parents = ["kt-operative"]
stats = { kt_move = 6, kt_wounds = 8 }

[[template]]
name = "Datacard"
system = true
kind = "being"
ancestor = "kt-operative"

[[template.slot]]
kind = "stats"
label = "Profile"
group = "kt_profile"
"""

NEUTRAL_TEMPLATE = """
[[template]]
name = "Plain card"
kind = "being"

[[template.slot]]
kind = "stats"
label = "Numbers"
stats = ["kt_move", { stat = "kt_wounds", label = "W" }]
"""


def test_templates_campaigns_and_beings(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("templates")
    tenant = make_tenant(stack, token, kind="play")
    (tmp_path / "kt.toml").write_text(DOCUMENT, encoding="utf-8")
    (tmp_path / "card.toml").write_text(NEUTRAL_TEMPLATE, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    applied = cli("apply", str(tmp_path / "kt.toml"), "-t", tenant, "--yes")
    assert applied.exit_code == 0, applied.output
    assert cli("plan", str(tmp_path / "kt.toml"), "-t", tenant).exit_code == 0
    exported = tomllib.loads(cli("export", "kt", "-t", tenant).stdout)
    assert [t["name"] for t in exported["template"]] == ["Datacard"]
    assert exported["template"][0]["slot"][0]["group"] == "kt_profile"

    made = cli("template", "create", "--from", str(tmp_path / "card.toml"), "-t", tenant, "--yes")
    assert made.exit_code == 0, made.output
    listed = json.loads(cli("template", "list", "-t", tenant, "--json").stdout)
    assert {t["name"] for t in listed["templates"]} == {"Datacard", "Plain card"}
    shown = cli("template", "show", "Plain card", "-t", tenant)
    assert 'label = "W"' in shown.output

    campaign = cli(
        "campaign", "create", "League", "--slug", "league", "--system", "kt", "-t", tenant, "--yes"
    )
    assert campaign.exit_code == 0, campaign.output
    being = cli(
        "being",
        "create",
        "Hale",
        "--parent",
        "kt-gunner",
        "--slug",
        "hale",
        "-t",
        tenant,
        "--yes",
        "--json",
    )
    assert being.exit_code == 0, being.output

    matching = json.loads(cli("template", "matching", "hale", "-t", tenant, "--json").stdout)
    assert {t["name"] for t in matching["templates"]} == {"Datacard", "Plain card"}
    view = json.loads(cli("template", "view", "hale", "Datacard", "-t", tenant, "--json").stdout)
    profile = {s["name"]: s["value"] for s in view["slots"][0]["stats"]}
    assert profile == {"kt_move": 6, "kt_wounds": 8}

    sheet = json.loads(
        cli("being", "show", "hale", "-t", tenant, "--campaign", "league", "--json").stdout
    )
    assert sheet["sheet"]["template"]["name"] == "Datacard"

    cleared = cli("campaign", "set-system", "league", "-t", tenant, "--none", "--yes", "--json")
    assert cleared.exit_code == 0, cleared.output
    assert json.loads(cleared.stdout)["system_id"] is None
