"""The library document against the real API (ADR 0498, ADR 0499): applied, applied again with
nothing to do, exported back to the same document, and edited one row at a time."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack

DOCUMENT = """
format = 1
name = "ds"

[system]
slug = "ds"
name = "Dust and Sun"
root = "ds-root"

[[group]]
name = "ds_vitals"
system = true
position = 0

[[stat]]
name = "ds_stamina"
group = "ds_vitals"
type = "int"
min = 0
max = 20
position = 0

[[stat]]
name = "ds_wounds"
group = "ds_vitals"
type = "int"
max_hint = "ds_stamina"
position = 1

[[stat]]
name = "ds_bite"
group = "ds_vitals"
type = "dice"
position = 2

[[entry]]
slug = "ds-root"
name = "Dust and Sun"
description = "Everything of Dust and Sun descends from this."

[[entry]]
slug = "ds-hunter"
name = "Hunter"
parents = ["ds-root"]
stats = { ds_stamina = 12, ds_bite = "1d6" }

[[entry]]
slug = "ds-stalker"
name = "Stalker"
parents = ["ds-hunter"]

[[entry]]
slug = "ds-keen-eye"
name = "Keen eye"
kinds = ["feature"]
parents = ["ds-root"]
"""


def test_a_document_is_applied_once_found_again_and_exported_back(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("library-document")
    tenant = make_tenant(stack, token)
    path = tmp_path / "ds.toml"
    path.write_text(DOCUMENT, encoding="utf-8")

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    planned = cli("plan", str(path), "-t", tenant, "--json")
    assert planned.exit_code == 2, planned.output
    counts = json.loads(planned.stdout)["counts"]
    assert counts["create"] > 0 and counts["remove"] == 0

    nobody = cli("apply", str(path), "-t", tenant)
    assert nobody.exit_code == 2 and "--yes" in nobody.output  # nothing to ask, nothing written

    applied = cli("apply", str(path), "-t", tenant, "--yes", "--json")
    assert applied.exit_code == 0, applied.output
    result = json.loads(applied.stdout)["result"]
    assert result["failed"] == [] and len(result["done"]) == counts["create"] + counts["change"]

    again = cli("plan", str(path), "-t", tenant)
    assert again.exit_code == 0, again.output  # a second apply finds what the first made

    exported = cli("export", "ds", "-t", tenant)
    assert exported.exit_code == 0, exported.output
    back = tomllib.loads(exported.stdout)
    sent = tomllib.loads(DOCUMENT)
    assert back["system"] == sent["system"]
    assert [s["name"] for s in back["stat"]] == [s["name"] for s in sent["stat"]]
    # The leaf Stalker is content under the root, not vocabulary, so it is not exported.
    assert [e["slug"] for e in back["entry"]] == ["ds-root", "ds-hunter", "ds-keen-eye"]
    hunter = next(e for e in back["entry"] if e["slug"] == "ds-hunter")
    assert hunter["stats"]["ds_stamina"] == 12
    assert hunter["stats"]["ds_bite"].lower() in ("d6", "1d6")  # the API's own notation

    # The export applies to the library it came from with nothing to do.
    (tmp_path / "back.toml").write_text(exported.stdout, encoding="utf-8")
    assert cli("plan", str(tmp_path / "back.toml"), "-t", tenant).exit_code == 0


def test_systems_and_the_vocabulary_one_row_at_a_time(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token("library-rows")
    tenant = make_tenant(stack, token)

    def cli(*args: str):  # noqa: ANN202
        return run_cli(stack, token, tmp_path, *args)

    made = cli("system", "create", "wg", "Wrath", "-t", tenant, "--yes", "--json")
    assert made.exit_code == 0, made.output
    assert json.loads(made.stdout)["slug"] == "wg"
    assert cli("system", "create", "Bad Slug", "X", "-t", tenant, "--yes").exit_code == 1

    group = cli("stat-group", "create", "wg_attributes", "-t", tenant, "--system", "wg", "--yes")
    assert group.exit_code == 0, group.output
    refused = cli(
        "stat-definition", "create", "strength", "-t", tenant,
        "--group", "wg_attributes", "--type", "int", "--yes",
    )  # fmt: skip
    assert refused.exit_code == 1 and "wg_strength" in refused.output
    bounded = cli(
        "stat-definition", "create", "wg_strength", "-t", tenant,
        "--group", "wg_attributes", "--type", "int", "--min", "1", "--max", "12", "--yes",
    )  # fmt: skip
    assert bounded.exit_code == 0, bounded.output

    listed = json.loads(
        cli("stat-definition", "list", "-t", tenant, "--system", "wg", "--json").stdout
    )
    strength = next(s for s in listed["stat_definitions"] if s["name"] == "wg_strength")
    assert (strength["min_value"], strength["max_value"]) == (1, 12)
    table = cli("stat-group", "list", "-t", tenant)
    assert "wg_attributes" in table.output and "wg" in table.output

    shown = json.loads(cli("system", "show", "wg", "-t", tenant, "--json").stdout)
    assert shown["groups"] == ["wg_attributes"]
    still_used = cli("system", "delete", "wg", "-t", tenant, "--yes")
    assert still_used.exit_code == 1 and "wg_attributes" in still_used.output


def test_the_schema_needs_no_login(stack: Stack, tmp_path: Path) -> None:
    schema = run_cli(stack, "", tmp_path, "schema", "document")
    assert schema.exit_code == 0
    assert json.loads(schema.stdout)["title"] == "Lorenzo library document"
    plan = json.loads(run_cli(stack, "", tmp_path, "schema", "output", "plan").stdout)
    assert "actions" in plan["properties"]
