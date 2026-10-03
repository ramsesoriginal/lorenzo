"""`lorenzo repo` against the real API: a seeded repository, published, offered, copied, updated
(ADR 0159, 0160). The fake in tests/repo_world.py only checks the CLI's own branches; what the
routes really answer is checked here."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import by_slug, make_tenant, run_cli, tenant_id
from e2e.stack import Stack


class World:
    """A seeded repository, and a play tenant of the same owner to draw on it."""

    def __init__(self, stack: Stack, tmp_path: Path, *, published: bool = True) -> None:
        self.stack = stack
        self.tmp_path = tmp_path
        self.token = stack.creator_token(f"owner-{uuid.uuid4().hex[:8]}")
        self.repository = make_tenant(stack, self.token, "repository")
        self.target = make_tenant(stack, self.token, "play")
        seeded = self.cli("seed", "--tenant", self.repository, "--yes")
        assert seeded.exit_code == 0, seeded.output
        if published:
            published_ok = self.cli("repo", "publish", "--tenant", self.repository)
            assert published_ok.exit_code == 0, published_ok.output

    def cli(self, *args: str, answers: str | None = None) -> Any:
        return run_cli(self.stack, self.token, self.tmp_path, *args, answers=answers)

    def json(self, *args: str) -> Any:
        result = self.cli(*args, "--json")
        return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else None

    def api(self) -> httpx.Client:
        return self.stack.api(self.token)

    def ids(self) -> tuple[str, str]:
        with self.api() as api:
            return tenant_id(api, self.repository), tenant_id(api, self.target)

    def entity(self, tenant: str, slug: str) -> dict[str, Any]:
        with self.api() as api:
            return by_slug(api, tenant_id(api, tenant), slug)

    def rename(self, tenant: str, entity: dict[str, Any], name: str) -> None:
        """Rename an item through the API, with the ETag it asks for."""
        with self.api() as api:
            tid = tenant_id(api, tenant)
            path = f"/tenants/{tid}/items/{entity['id']}"
            etag = api.get(path).headers["ETag"]
            response = api.patch(path, json={"name": name}, headers={"If-Match": etag})
            assert response.status_code == 200, response.text


def test_a_repository_is_offered_and_copied_and_offering_again_changes_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    world = World(stack, tmp_path, published=False)

    refused = world.cli("repo", "offer", world.target, "--tenant", world.repository, "--yes")
    assert refused.exit_code == 1
    assert "isn't published yet" in " ".join(refused.output.split())
    assert world.json("repo", "subscribers", "--tenant", world.repository)[1] == []  # no grant

    assert world.cli("repo", "publish", "--tenant", world.repository).exit_code == 0
    code, document = world.json(
        "repo", "offer", world.target, "--tenant", world.repository, "--yes"
    )

    assert code == 0, document
    assert document["granted"] == "new"
    assert document["copied"] == "copied"
    assert document["copy"]["steps"][0]["entities"] > 20  # the seeded taxonomy came across
    weapon = world.entity(world.target, "weapon")  # as the tenant's own, by its slug
    assert weapon["name"]

    held = world.json("repo", "list", "--tenant", world.target)[1]
    assert held[0]["repository"]["slug"] == world.repository
    assert held[0]["copied_at"] is not None

    code, again = world.json("repo", "offer", world.target, "--tenant", world.repository, "--yes")
    assert code == 0
    assert again["granted"] == "existing"
    assert again["copied"] == "already"
    assert again["copy"] is None


def test_names_already_in_use_need_a_choice_and_merging_answers_them(
    stack: Stack, tmp_path: Path
) -> None:
    world = World(stack, tmp_path)
    repository_id, target_id = world.ids()
    with world.api() as api:
        group = api.post(
            f"/tenants/{target_id}/stat-groups", json={"name": "physical", "priority": 0}
        ).json()
        made = api.post(
            f"/tenants/{target_id}/stat-definitions",
            json={"name": "weight", "stat_group_id": group["id"], "value_type": "float"},
        )
        assert made.status_code == 201, made.text
    assert world.cli("repo", "grant", world.target, "--tenant", world.repository).exit_code == 0

    code, plan = world.json("repo", "copy-plan", world.repository, "--tenant", world.target)
    assert code == 2
    assert {c["kind"] for c in plan["collisions"]} == {"stat_group", "stat_definition"}
    assert {c["name"] for c in plan["collisions"]} == {"physical", "weight"}

    nothing = world.cli("repo", "copy", world.repository, "--tenant", world.target, "--yes")
    assert nothing.exit_code == 2
    assert "Nothing was copied" in " ".join(nothing.output.split())
    assert world.json("repo", "list", "--tenant", world.target)[1][0]["copied_at"] is None

    dry = world.cli(
        "repo", "copy", world.repository, "--tenant", world.target,
        "--on-collision", "merge", "--dry-run",
    )  # fmt: skip
    assert dry.exit_code == 0, dry.output
    assert "Would copy" in dry.output
    assert world.json("repo", "list", "--tenant", world.target)[1][0]["copied_at"] is None

    copied = world.cli(
        "repo", "copy", world.repository, "--tenant", world.target,
        "--on-collision", "merge", "--yes",
    )  # fmt: skip
    assert copied.exit_code == 0, copied.output
    with world.api() as api:
        groups = api.get(f"/tenants/{target_id}/stat-groups", params={"size": 100}).json()["items"]
    assert [g["name"] for g in groups].count("physical") == 1  # merged, not duplicated
    assert repository_id != target_id

    again = world.cli("repo", "copy", world.repository, "--tenant", world.target, "--yes")
    assert again.exit_code == 1
    assert "not another copy" in " ".join(again.output.split())  # the API's own words
    assert "lorenzo repo updates" in " ".join(again.output.split())


def test_updates_are_found_taken_and_a_conflict_waits_until_it_is_named(
    stack: Stack, tmp_path: Path
) -> None:
    world = World(stack, tmp_path)
    repository_id, target_id = world.ids()
    assert (
        world.cli("repo", "offer", world.target, "--tenant", world.repository, "--yes").exit_code
        == 0
    )
    assert world.json("repo", "updates", world.repository, "--tenant", world.target)[0] == 0

    # The repository changes a name and adds a stat group, and announces it.
    weapon = world.entity(world.repository, "weapon")
    world.rename(world.repository, weapon, "Weapon, revised")
    with world.api() as api:
        added = api.post(
            f"/tenants/{repository_id}/stat-groups", json={"name": "lore", "priority": 0}
        )
        assert added.status_code == 201, added.text
    assert world.cli("repo", "publish", "--tenant", world.repository).exit_code == 0

    listed = world.json("repo", "list", "--tenant", world.target)[1]
    assert listed[0]["repository"]["published_at"] > listed[0]["copied_at"]
    shown = world.cli("repo", "list", "--tenant", world.target)
    assert "updated since" in " ".join(shown.output.split())

    code, updates = world.json("repo", "updates", world.repository, "--tenant", world.target)
    assert code == 2
    changed = {row["name"]: row for row in updates["changed"]}
    assert [f["state"] for f in changed["Weapon"]["fields"]] == ["clean"]
    assert [(a["kind"], a["name"]) for a in updates["added"]] == [("stat_group", "lore")]

    taken = world.cli(
        "repo", "updates", world.repository, "--tenant", world.target, "--apply", "--yes"
    )
    assert taken.exit_code == 0, taken.output
    assert world.entity(world.target, "weapon")["name"] == "Weapon, revised"
    with world.api() as api:
        names = [
            g["name"]
            for g in api.get(f"/tenants/{target_id}/stat-groups", params={"size": 100}).json()[
                "items"
            ]
        ]
    assert "lore" in names
    assert world.json("repo", "updates", world.repository, "--tenant", world.target)[0] == 0

    # Now both sides rename it: the tenant's own edit is not taken without being named.
    world.rename(world.target, world.entity(world.target, "weapon"), "Mine")
    world.rename(world.repository, world.entity(world.repository, "weapon"), "Theirs")
    assert world.cli("repo", "publish", "--tenant", world.repository).exit_code == 0

    code, conflict = world.json("repo", "updates", world.repository, "--tenant", world.target)
    assert code == 2
    row = next(r for r in conflict["changed"] if r["name"] == "Mine")
    assert [f["state"] for f in row["fields"]] == ["conflict"]

    left = world.cli(
        "repo", "updates", world.repository, "--tenant", world.target, "--apply", "--yes"
    )
    assert left.exit_code == 2  # nothing was clean, and the conflict is left
    assert "conflicts with your own edit" in " ".join(left.output.split())
    assert world.entity(world.target, "weapon")["name"] == "Mine"

    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            [
                {
                    "kind": "entity",
                    "source_id": row["source_id"],
                    "action": "apply",
                    "take_upstream": ["name"],
                }
            ]
        )
    )
    named = world.cli(
        "repo", "updates", world.repository, "--tenant", world.target,
        "--actions", str(actions), "--yes",
    )  # fmt: skip
    assert named.exit_code == 0, named.output
    assert world.entity(world.target, "weapon")["name"] == "Theirs"


def test_grant_publish_unpublish_and_revoke_round_trip(stack: Stack, tmp_path: Path) -> None:
    world = World(stack, tmp_path, published=False)
    _, target_id = world.ids()

    granted = world.cli("repo", "grant", world.target, "--tenant", world.repository)
    assert granted.exit_code == 0, granted.output
    assert "isn't published yet" in " ".join(granted.output.split())
    again = world.cli("repo", "grant", world.target, "--tenant", world.repository)
    assert "already had access" in " ".join(again.output.split())
    subscribers = world.json("repo", "subscribers", "--tenant", world.repository)[1]
    assert [s["tenant_id"] for s in subscribers] == [target_id]

    # A draft is invisible to the tenant it is granted to, whatever the grant says.
    code, _ = world.json("repo", "copy-plan", world.repository, "--tenant", world.target)
    assert code == 1

    assert world.cli("repo", "publish", "--tenant", world.repository).exit_code == 0
    assert world.json("repo", "copy-plan", world.repository, "--tenant", world.target)[0] == 0

    assert world.cli("repo", "unpublish", "--tenant", world.repository).exit_code == 0
    assert world.json("repo", "copy-plan", world.repository, "--tenant", world.target)[0] == 1

    revoked = world.cli("repo", "revoke", world.target, "--tenant", world.repository)
    assert revoked.exit_code == 0, revoked.output
    assert world.json("repo", "subscribers", "--tenant", world.repository)[1] == []


def test_a_slug_that_is_not_one_of_the_tenants_repositories_is_named(
    stack: Stack, tmp_path: Path
) -> None:
    world = World(stack, tmp_path)

    result = world.cli("repo", "copy-plan", "no-such-repository", "--tenant", world.target)

    assert result.exit_code == 1
    assert "no repository “no-such-repository”" in " ".join(result.output.split())
