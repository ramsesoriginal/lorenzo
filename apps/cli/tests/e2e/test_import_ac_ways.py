"""MPMB's ways of working out armour class, imported (RFC 0057, ADR 0490): an armour entry of the
sheet's `firstlist` or with an AC formula becomes a feature under the D&D starter's armour class
features, and a character who holds it gets that armour class."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e.helpers import FIXTURES, by_slug, make_tenant, run_cli, tenant_id
from e2e.stack import Stack

PARTY = """
format = 1
name = "party"
requires = ["dnd5e"]

[[entry]]
slug = "sister"
name = "Sister"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 14, dnd5e_wisdom = 16 }

[[entry]]
slug = "shelly"
name = "Shelly"
kinds = ["being"]
parents = ["dnd5e-character"]

[[entry]]
slug = "adept"
name = "Adept"
kinds = ["being"]
parents = ["dnd5e-character"]
stats = { dnd5e_dexterity = 14, dnd5e_wisdom = 16 }
"""


def test_an_imported_way_of_working_out_armour_class_is_a_feature(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token("ac-import")
    library = make_tenant(stack, token, "repository")

    def ok(*args: str) -> Any:
        result = run_cli(stack, token, tmp_path, *args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    for starter in ("neutral", "dnd5e"):
        ok("apply", "--starter", starter, "-t", library, "--yes")
    importing = (
        "import", "mpmb", "apply", "--tenant", library, str(FIXTURES / "ac-ways.js"),
        "--review-queue", str(tmp_path / "rq.json"), "--proposed-map", str(tmp_path / "pm.toml"),
    )  # fmt: skip
    ok(*importing, "--yes")
    again = json.loads(ok(*importing[:2], "plan", *importing[3:], "--json").stdout)

    features = json.loads(
        ok("feature", "list", "-t", library, "--system", "dnd5e", "--json").stdout
    )["features"]
    imported = {f["slug"]: f for f in features if f["slug"] and f["slug"].startswith("basic-")}
    # The robe of focus is armour worn, so it stays an item: only the sheet's ways are features.
    assert set(imported) == {"basic-armour-robe-of-stillness", "basic-armour-turtle-shell"}
    assert imported["basic-armour-turtle-shell"]["values"] == {"dnd5e_ac_natural": 17}
    assert imported["basic-armour-robe-of-stillness"]["under"] == ["Armor class features (D&D 5e)"]
    assert {i["status"] for i in again["items"]} <= {"exists", "skipped"}  # a second run adds none

    party = tmp_path / "party.toml"
    party.write_text(PARTY, encoding="utf-8")
    ok("apply", str(party), "-t", library, "--yes")
    ok(
        "feature",
        "award",
        "basic-armour-robe-of-stillness",
        "--to",
        "sister",
        "-t",
        library,
        "--yes",
    )
    ok("feature", "award", "basic-armour-turtle-shell", "--to", "shelly", "-t", library, "--yes")

    def armor_class(being: str) -> object:
        found = ok(
            "formula", "preview", "dnd5e_armor_class", "--on", being, "-t", library, "--json"
        )
        return json.loads(found.stdout)["value"]

    assert armor_class("sister") == 15  # 10 + Dexterity +2 + Wisdom +3
    assert armor_class("shelly") == 17  # a natural armour class, without Dexterity

    with stack.api(token) as api:
        tid = tenant_id(api, library)
        worn = api.post(
            f"/tenants/{tid}/item-instances",
            json={
                "prototype_id": by_slug(api, tid, "basic-armour-robe-of-focus")["id"],
                "container_entity_id": by_slug(api, tid, "adept")["id"],
                "active": True,
            },
        )
        assert worn.status_code == 201, worn.text
    assert armor_class("adept") == 15  # the robe, worn, gives 10 + Dexterity +2 + Wisdom +3
