"""`lorenzo tenant delete` against the real API (ADR 0184): starting a stack over, in the order
that works, and what it says when it can't."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from plain import plain

from e2e.helpers import run_cli, tenant_id
from e2e.stack import Stack


def slugs(stack: Stack, token: str) -> set[str]:
    with stack.api(token) as api:
        page, found = 1, set()
        while True:
            body = api.get("/tenants", params={"page": page, "size": 100}).json()
            found |= {t["slug"] for t in body["items"]}
            if page >= body["pages"]:
                return found
            page += 1


class Mine:
    def __init__(self, stack: Stack, work: Path) -> None:
        self.stack, self.work = stack, work
        self.token = stack.creator_token("delete-" + uuid.uuid4().hex[:6])
        tag = uuid.uuid4().hex[:6]
        self.core, self.equipment, self.table = f"core-{tag}", f"eq-{tag}", f"table-{tag}"

    def cli(self, *args: str, **kwargs: Any) -> Any:
        return run_cli(self.stack, self.token, self.work, *args, **kwargs)

    def ok(self, *args: str) -> Any:
        result = self.cli(*args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def build(self) -> None:
        self.ok("tenant", "create", "Core", "--slug", self.core)
        self.ok("seed", "--tenant", self.core, "--layer", "core", "--yes")
        self.ok("repo", "publish", "--tenant", self.core)
        self.ok("tenant", "create", "Equipment", "--slug", self.equipment)
        self.ok("repo", "offer", self.equipment, "--tenant", self.core, "--yes")
        self.ok("seed", "--tenant", self.equipment, "--layer", "equipment", "--yes")
        self.ok("repo", "publish", "--tenant", self.equipment)
        self.ok("tenant", "create", "Table", "--slug", self.table, "--kind", "play")
        self.ok("repo", "offer", self.table, "--tenant", self.equipment, "--yes")


def test_a_stack_is_deleted_from_the_top_down_and_built_again_under_the_same_slugs(
    stack: Stack, tmp_path: Path
) -> None:
    mine = Mine(stack, tmp_path)
    mine.build()

    # Built on, so refused: the grants are what stand in the way, and the output says how to go on.
    first = mine.cli("tenant", "delete", mine.core, "--yes")
    second = mine.cli("tenant", "delete", mine.equipment, "--yes")
    for refused, slug in ((first, mine.core), (second, mine.equipment)):
        assert refused.exit_code == 1
        said = " ".join(plain(refused.output).split())
        assert "is still granted to" in said and "HTTP 409" in said
        assert f"lorenzo repo subscribers --tenant {slug}" in said
    assert {mine.core, mine.equipment, mine.table} <= slugs(stack, mine.token)

    # The table first, then what it drew on, then what that drew on; the last one asks first.
    assert mine.cli("tenant", "delete", mine.table, "--yes").exit_code == 0
    assert mine.cli("tenant", "delete", mine.equipment, "--yes").exit_code == 0
    wrong = mine.cli("tenant", "delete", mine.core, answers="not-the-slug\n")
    assert wrong.exit_code == 1 and "Nothing was deleted." in plain(wrong.output)
    typed = mine.cli("tenant", "delete", mine.core, answers=f"{mine.core}\n")
    assert typed.exit_code == 0, typed.output
    assert not {mine.core, mine.equipment, mine.table} & slugs(stack, mine.token)

    # The slugs are free again, and the whole thing works as it did.
    mine.build()
    assert {mine.core, mine.equipment, mine.table} <= slugs(stack, mine.token)


def test_json_says_which_tenant_was_deleted(stack: Stack, tmp_path: Path) -> None:
    mine = Mine(stack, tmp_path)
    mine.ok("tenant", "create", "Core", "--slug", mine.core)
    with stack.api(mine.token) as api:
        expected = tenant_id(api, mine.core)

    result = mine.cli("tenant", "delete", mine.core, "--yes", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == expected
    assert mine.core not in slugs(stack, mine.token)


def test_an_owner_without_the_tenant_creator_role_is_told_so(stack: Stack, tmp_path: Path) -> None:
    mine = Mine(stack, tmp_path)
    mine.ok("tenant", "create", "Core", "--slug", mine.core)
    roleless = stack.authgear.token("roleless-" + uuid.uuid4().hex[:6])
    with stack.api(roleless) as api:
        me = api.get("/me").json()["id"]
    with stack.api(mine.token) as api:
        granted = api.post(
            f"/tenants/{tenant_id(api, mine.core)}/memberships",
            json={"user_id": me, "role": "owner"},
        )
        assert granted.status_code == 201, granted.text

    refused = run_cli(stack, roleless, tmp_path, "tenant", "delete", mine.core, "--yes")

    assert refused.exit_code == 1
    assert "tenant-creator role" in plain(refused.output)
    assert "HTTP 403" in plain(refused.output)
    assert mine.core in slugs(stack, mine.token)
