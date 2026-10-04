"""The parents a bridge adds to its copies, against the real API (ADR 0172, 0174): what `repo
copy-plan`, `repo copy`, `repo updates` and `repo contents` say about them, and what `--apply` and
`--actions` do with them.

The stack is RFC 0033's, small: an equipment repository (Weapon, Longsword), a rules repository
(a system root), and a bridge that copied both and attached its own prototypes to the equipment's
items, and the rules' root to a form. A table that takes the bridge gets them on the items it has.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import by_slug, make_tenant, parent_names, run_cli, tenant_id
from e2e.stack import Stack


def said(result: Any) -> str:
    return " ".join(result.output.split())


def make_item(api: httpx.Client, tid: str, name: str, slug: str, *parents: str) -> str:
    response = api.post(
        f"/tenants/{tid}/items",
        json={"name": name, "slug": slug, "prototype_ids": list(parents)},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["entity_id"])


def set_parents(api: httpx.Client, tid: str, item_id: str, *parents: str) -> None:
    """A parent set replaces the item's own, so an attachment is the old set and one more."""
    item = api.get(f"/tenants/{tid}/items/{item_id}")
    response = api.put(
        f"/tenants/{tid}/items/{item_id}/prototypes",
        json={"prototype_ids": list(parents)},
        headers={"If-Match": item.headers["etag"]},
    )
    assert response.status_code == 200, response.text


class Levels:
    """Equipment and rules repositories, and a bridge over both with three attachments."""

    def __init__(self, stack: Stack, tmp_path: Path) -> None:
        self.stack = stack
        self.tmp_path = tmp_path
        self.token = stack.creator_token("attachments-owner")
        self.equipment = make_tenant(stack, self.token, "repository")
        self.rules = make_tenant(stack, self.token, "repository")
        self.bridge = make_tenant(stack, self.token, "repository")
        with stack.api(self.token) as api:
            equipment, rules = tenant_id(api, self.equipment), tenant_id(api, self.rules)
            weapon = make_item(api, equipment, "Weapon", "weapon")
            make_item(api, equipment, "Longsword", "longsword", weapon)
            make_item(api, rules, "D&D 5e", "dnd5e")
        self.ok("repo", "publish", "--tenant", self.equipment)
        self.ok("repo", "publish", "--tenant", self.rules)
        self.ok("repo", "offer", self.bridge, "--tenant", self.equipment, "--yes")
        self.ok("repo", "offer", self.bridge, "--tenant", self.rules, "--yes")
        with stack.api(self.token) as api:
            bridge = tenant_id(api, self.bridge)
            root = by_slug(api, bridge, "dnd5e")["id"]
            weapon = by_slug(api, bridge, "weapon")["id"]
            longsword = by_slug(api, bridge, "longsword")["id"]
            longsword_5e = make_item(api, bridge, "Longsword 5e", "longsword-5e", root)
            economic = make_item(api, bridge, "Economic Object", "economic-object", root)
            set_parents(api, bridge, longsword, weapon, longsword_5e)
            set_parents(api, bridge, weapon, economic, root)
        self.ok("repo", "publish", "--tenant", self.bridge)

    def cli(self, *args: str) -> Any:
        return run_cli(self.stack, self.token, self.tmp_path, *args)

    def ok(self, *args: str) -> Any:
        result = self.cli(*args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def json(self, *args: str) -> tuple[int, Any]:
        result = self.cli(*args, "--json")
        return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else None

    def table(self, *, grant: bool = True) -> str:
        slug = make_tenant(self.stack, self.token, "play")
        if grant:
            for repository in (self.equipment, self.rules, self.bridge):
                self.ok("repo", "grant", slug, "--tenant", repository)
        return slug

    def parents(self, tenant: str, slug: str) -> list[str]:
        with self.stack.api(self.token) as api:
            return parent_names(by_slug(api, tenant_id(api, tenant), slug))


def test_a_plan_a_copy_and_the_contents_of_a_bridge_count_its_attachments(
    stack: Stack, tmp_path: Path
) -> None:
    levels = Levels(stack, tmp_path)
    table = levels.table()
    levels.ok("repo", "copy", levels.equipment, "--tenant", table, "--yes")
    assert levels.parents(table, "weapon") == []

    code, plan = levels.json("repo", "copy-plan", levels.bridge, "--tenant", table)
    assert code == 0, plan
    assert [s["attachments"] for s in plan["steps"]] == [0, 0, 3]
    text = said(levels.ok("repo", "copy-plan", levels.bridge, "--tenant", table))
    assert "3 attachments (granted, published)." in text

    copied = said(levels.ok("repo", "copy", levels.bridge, "--tenant", table, "--yes"))
    assert "3 attachments." in copied
    # The items the table had before the bridge have the bridge's prototypes now.
    assert levels.parents(table, "longsword") == ["Longsword 5e", "Weapon"]
    assert levels.parents(table, "weapon") == ["D&D 5e", "Economic Object"]

    contents = levels.json("repo", "contents", "--tenant", levels.bridge)[1]
    assert contents["holds"]["attachments"] == 3
    assert "Attaches 3 parent(s) to items it copied" in said(
        levels.ok("repo", "contents", "--tenant", levels.bridge)
    )
    assert (
        levels.json("repo", "contents", "--tenant", levels.equipment)[1]["holds"]["attachments"]
        == 0
    )


def test_updates_take_an_attachment_with_the_row_it_points_at_and_detach_only_when_named(
    stack: Stack, tmp_path: Path
) -> None:
    levels = Levels(stack, tmp_path)
    table = levels.table()
    levels.ok("repo", "copy", levels.bridge, "--tenant", table, "--yes")
    assert levels.json("repo", "updates", levels.bridge, "--tenant", table)[0] == 0

    # The bridge adds a prototype and attaches it to the form, and drops one attachment.
    with stack.api(levels.token) as api:
        bridge = tenant_id(api, levels.bridge)
        weapon = by_slug(api, bridge, "weapon")
        longsword = by_slug(api, bridge, "longsword")
        heavy = make_item(api, bridge, "Heavy Object", "heavy-object")
        set_parents(api, bridge, weapon["id"], *[p["id"] for p in weapon["prototypes"]], heavy)
        set_parents(
            api,
            bridge,
            longsword["id"],
            *[p["id"] for p in longsword["prototypes"] if p["name"] != "Longsword 5e"],
        )
    levels.ok("repo", "publish", "--tenant", levels.bridge)

    code, shown = levels.json("repo", "updates", levels.bridge, "--tenant", table)
    assert code == 2
    (waiting,) = shown["attachments_added"]
    assert (waiting["parent_name"], waiting["child_name"], waiting["applicable"]) == (
        "Heavy Object",
        "Weapon",
        False,
    )
    assert [(a["parent_name"], a["child_name"]) for a in shown["attachments_removed"]] == [
        ("Longsword 5e", "Longsword")
    ]
    text = said(levels.cli("repo", "updates", levels.bridge, "--tenant", table))
    assert (
        "added attachment “Heavy Object” on “Weapon”, but it waits: "
        "the prototype it attaches isn't here" in text
    )
    assert "gone upstream: attachment “Longsword 5e” on “Longsword”" in text

    # --apply takes the new prototype and, in the same call, the attachment to it. The one gone
    # upstream is left.
    applied = levels.cli("repo", "updates", levels.bridge, "--tenant", table, "--apply", "--yes")
    assert applied.exit_code == 2, applied.output
    text = said(applied)
    assert "Took 0 changed, 1 added, 0 detached." in text
    assert "Attachments: 1 added, 0 detached." in text
    assert "1 attachment(s) gone upstream (detach is a decision)" in text
    assert levels.parents(table, "weapon") == ["D&D 5e", "Economic Object", "Heavy Object"]
    assert levels.parents(table, "longsword") == ["Longsword 5e", "Weapon"]

    # Naming it detaches it, and the table keeps the parent: updating never takes one away.
    gone = shown["attachments_removed"][0]
    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "actions": [],
                "attachments": [
                    {
                        "child_source_id": gone["child_source_id"],
                        "parent_source_id": gone["parent_source_id"],
                        "action": "detach",
                    }
                ],
            }
        )
    )
    detached = levels.cli(
        "repo", "updates", levels.bridge, "--tenant", table, "--actions", str(decisions), "--yes"
    )
    assert detached.exit_code == 0, detached.output
    assert "Attachments: 0 added, 1 detached." in said(detached)
    assert levels.parents(table, "longsword") == ["Longsword 5e", "Weapon"]
    assert levels.json("repo", "updates", levels.bridge, "--tenant", table)[0] == 0
