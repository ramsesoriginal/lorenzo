"""`lorenzo repo offer` (ADR 0160): grant, copy in, and be safe to run again."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from repo_world import (
    CORE_ID,
    GROUP_COLLISION,
    GROUP_ID,
    REPO_ID,
    SLUG_COLLISION,
    SLUG_ID,
    STRANGER_ID,
    TARGET_ID,
    World,
    added,
    attachment,
    attachment_ref,
    problem,
    removed,
    row_change,
    runtime,
)
from typer.testing import CliRunner

from lorenzo_cli.main import app

runner = CliRunner()


def said(result: object) -> str:
    text = result.output  # type: ignore[attr-defined]
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", text).split())


def offer(tmp_path: Path, world: World, *args: str, interactive: bool | None = None, **kw: object):  # noqa: ANN201
    return runner.invoke(
        app,
        ["repo", "offer", "table-one", "--tenant", "sunken-vale", *args],
        obj=runtime(tmp_path, world, interactive=interactive),
        **kw,
    )


GRANT = ("PUT", f"/tenants/{REPO_ID}/subscribers/{TARGET_ID}")
COPY = ("POST", f"/tenants/{TARGET_ID}/repositories/{REPO_ID}/copy")
UPDATES = ("POST", f"/tenants/{TARGET_ID}/repositories/{REPO_ID}/updates")


def test_a_fresh_offer_grants_then_copies_in_that_order(tmp_path: Path) -> None:
    world = World()
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 0, result.output
    assert world.writes() == [GRANT, COPY]
    text = said(result)
    assert "Granted sunken-vale to table-one; its members have been told." in text
    assert "Copied Sunken Vale: 12 entities" in text
    assert world.granted and world.copied


def test_offering_again_changes_nothing_and_succeeds(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    result = offer(tmp_path, world, interactive=False)  # nothing to write, so nothing to ask

    assert result.exit_code == 0, result.output
    assert world.writes() == []
    text = said(result)
    assert "table-one already had access to sunken-vale" in text
    assert "already has a copy of sunken-vale" in text


def test_a_grant_that_exists_is_not_repeated_but_the_copy_still_happens(tmp_path: Path) -> None:
    world = World(granted=True)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 0, result.output
    assert world.writes() == [COPY]
    assert "already had access" in said(result)


def test_an_unpublished_repository_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    world = World(published_at=None)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 1
    assert world.writes() == []
    assert "isn't published yet" in said(result)
    assert "lorenzo repo publish --tenant sunken-vale" in said(result)


def test_a_play_tenant_is_not_something_to_offer(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["repo", "offer", "sunken-vale", "--tenant", "table-one", "--yes"],
        obj=runtime(tmp_path, World()),
    )

    assert result.exit_code == 1
    assert "not a repository" in said(result)


def test_a_repository_cannot_be_offered_to_itself(tmp_path: Path) -> None:
    world = World()
    result = runner.invoke(
        app,
        ["repo", "offer", "sunken-vale", "--tenant", "sunken-vale", "--yes"],
        obj=runtime(tmp_path, world),
    )

    assert result.exit_code == 1
    assert "itself" in said(result)
    assert world.writes() == []


def test_a_tenant_you_do_not_belong_to_fails_before_any_grant(tmp_path: Path) -> None:
    world = World()
    result = runner.invoke(
        app,
        ["repo", "offer", str(STRANGER_ID), "--tenant", "sunken-vale", "--yes"],
        obj=runtime(tmp_path, world),
    )

    assert result.exit_code == 1
    assert world.writes() == []


# --- collisions ----------------------------------------------------------------------


def test_collisions_without_a_choice_stop_after_the_grant_and_exit_two(tmp_path: Path) -> None:
    world = World(collisions=[GROUP_COLLISION, SLUG_COLLISION])
    result = offer(tmp_path, world, "--yes", "--on-collision", "merge")

    assert result.exit_code == 2
    assert world.granted and not world.copied
    text = said(result)
    assert "Not copied yet" in text
    assert "the grant stays" in text
    assert "slug “longsword”" in text
    assert "stat_group" not in text  # the merge answered that one


def test_running_it_again_with_the_choice_finishes_without_granting_twice(tmp_path: Path) -> None:
    world = World(collisions=[GROUP_COLLISION, SLUG_COLLISION])
    offer(tmp_path, world, "--yes", "--on-collision", "merge")
    file = tmp_path / "choices.json"
    file.write_text(json.dumps([{"kind": "slug", "source_id": str(SLUG_ID), "action": "skip"}]))

    result = offer(tmp_path, world, "--yes", "--on-collision", "merge", "--choices", str(file))

    assert result.exit_code == 0, result.output
    assert world.copied
    assert world.writes().count(GRANT) == 1
    assert world.writes().count(COPY) == 3  # the first run's refusal and retry, then this one


def test_missing_grants_for_a_bridges_dependencies_are_named(tmp_path: Path) -> None:
    world = World(granted=True)
    world.copy_answer = problem(
        409,
        "repository-copy-needs-grants",
        "Ask each one's owners for access, or to publish it",
        missing=[
            {
                "repository_id": str(STRANGER_ID),
                "name": "D&D 5e",
                "granted": False,
                "published": True,
            }
        ],
    )
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 1
    assert "D&D 5e (not granted)" in said(result)


# --- a copy that appeared in the meantime, and updates -------------------------------


def test_a_copy_that_appears_between_the_check_and_the_copy_is_a_success(tmp_path: Path) -> None:
    world = World(granted=True)
    world.copy_answer = problem(
        409, "repository-already-copied", "This repository has already been copied"
    )
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 0, result.output
    assert "already has a copy" in said(result)


def test_apply_updates_takes_what_needs_no_decision_when_it_is_already_copied(
    tmp_path: Path,
) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [row_change(1, "Clean", "clean"), row_change(2, "Conflicted", "conflict")],
        "removed": [removed(1, "Old Axe")],
        "deleted_locally": [],
        "added": [added(1, "Fresh")],
    }
    result = offer(tmp_path, world, "--apply-updates", "--yes")

    assert result.exit_code == 0, result.output
    assert world.writes() == [UPDATES]
    assert [a["action"] for a in world.bodies("POST", "/updates")[0]["actions"]] == ["apply", "add"]
    text = said(result)
    assert "Took 1 changed, 1 added, 0 detached" in text
    assert "2 update(s) wait for a decision" in text  # the conflict and the removal


def test_without_the_flag_updates_are_counted_and_not_taken(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [row_change(1, "Clean", "clean")],
        "removed": [],
        "deleted_locally": [],
        "added": [],
    }
    result = offer(tmp_path, world, interactive=False)

    assert result.exit_code == 0, result.output
    assert world.writes() == []
    assert "1 update(s) wait for a decision" in said(result)
    assert "lorenzo repo updates sunken-vale --tenant table-one" in said(result)


# --- asking --------------------------------------------------------------------------


def test_it_shows_what_it_will_do_and_asks_once_at_a_terminal(tmp_path: Path) -> None:
    world = World()
    declined = offer(tmp_path, world, interactive=True, input="n\n")

    assert declined.exit_code == 1
    assert world.writes() == []
    text = said(declined)
    assert "grant: to be granted" in text
    assert "copy: to be copied into it" in text
    assert "Offer sunken-vale to table-one?" in text

    accepted = offer(tmp_path, world, interactive=True, input="y\n")
    assert accepted.exit_code == 0, accepted.output
    assert world.writes() == [GRANT, COPY]


def test_without_a_terminal_or_with_json_it_needs_yes(tmp_path: Path) -> None:
    world = World()
    quiet = offer(tmp_path, world, interactive=False)
    assert quiet.exit_code == 1
    assert "--yes" in said(quiet)

    json_run = offer(tmp_path, world, "--json", interactive=True)
    assert json_run.exit_code == 1
    assert world.writes() == []


# --- dry runs and json ---------------------------------------------------------------


def test_a_dry_run_writes_nothing_not_even_the_grant_and_exits_two(tmp_path: Path) -> None:
    world = World()
    result = offer(tmp_path, world, "--dry-run")

    assert result.exit_code == 2
    assert world.writes() == []
    text = said(result)
    assert "can only be planned once the tenant is granted" in text
    assert "Dry run: nothing was written" in text


def test_a_dry_run_after_the_grant_shows_the_copy_plan_and_its_collisions(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION])
    result = offer(tmp_path, world, "--dry-run")

    assert result.exit_code == 2
    assert world.writes() == []
    assert "12 entities" in said(result)
    assert str(GROUP_ID) in said(result)


def test_a_dry_run_with_nothing_to_do_exits_zero(tmp_path: Path) -> None:
    result = offer(tmp_path, World(granted=True, copied=True), "--dry-run")

    assert result.exit_code == 0, result.output
    assert "Nothing to do." in said(result)


def test_a_dry_run_counts_the_updates_it_would_take(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [row_change(1, "Clean", "clean")],
        "removed": [],
        "deleted_locally": [],
        "added": [],
    }
    result = offer(tmp_path, world, "--dry-run", "--apply-updates")

    assert result.exit_code == 2
    assert "1 take(s) need no decision" in said(result)
    assert world.writes() == []


def test_dry_run_json_names_the_steps(tmp_path: Path) -> None:
    result = offer(tmp_path, World(), "--dry-run", "--json")

    assert result.exit_code == 2
    document = json.loads(result.stdout)
    assert document["dry_run"] is True
    assert document["steps"] == ["grant", "copy"]
    assert document["granted"] is False and document["copied"] is False


def test_json_is_one_document_of_what_each_step_did(tmp_path: Path) -> None:
    world = World()
    result = offer(tmp_path, world, "--yes", "--json")

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["repository"] == "sunken-vale"
    assert document["subscriber"] == "table-one"
    assert document["granted"] == "new"
    assert document["copied"] == "copied"
    assert document["copy"]["steps"][0]["entities"] == 12
    assert document["open_collisions"] == []


def test_json_with_open_collisions_lists_them_and_exits_two(tmp_path: Path) -> None:
    world = World(collisions=[GROUP_COLLISION])
    result = offer(tmp_path, world, "--yes", "--json")

    assert result.exit_code == 2
    document = json.loads(result.stdout)
    assert document["copied"] == "already"  # nothing was copied
    assert document["copy"] is None
    assert document["open_collisions"][0]["source_id"] == str(GROUP_ID)


def test_the_ids_in_the_world_are_distinct() -> None:
    assert len({REPO_ID, TARGET_ID, STRANGER_ID, uuid.UUID(int=1)}) == 4


# --- a bridge: what it was built on is offered too (ADR 0163) ---

CORE_GRANT = ("PUT", f"/tenants/{CORE_ID}/subscribers/{TARGET_ID}")


def test_offering_a_bridge_grants_what_it_builds_on_first_then_itself_then_copies(
    tmp_path: Path,
) -> None:
    world = World(bridge=True)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 0, result.output
    assert world.writes() == [CORE_GRANT, GRANT, COPY]
    text = said(result)
    assert "Granted core to table-one, which sunken-vale builds on" in text
    assert "Granted sunken-vale to table-one" in text
    assert world.core_granted and world.granted and world.copied


def test_a_dependency_that_is_already_granted_is_not_granted_again(tmp_path: Path) -> None:
    world = World(bridge=True, core_granted=True)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 0, result.output
    assert world.writes() == [GRANT, COPY]


def test_a_dependency_the_tenant_already_copied_needs_no_grant(tmp_path: Path) -> None:
    world = World(bridge=True, core_copied=True)
    result = offer(tmp_path, world, "--yes", "--json")

    assert result.exit_code == 0, result.output
    assert world.writes() == [GRANT, COPY]
    assert json.loads(result.stdout)["dependencies"] == {"core": "copied"}


def test_a_dependency_that_is_not_published_is_refused_before_anything_is_written(
    tmp_path: Path,
) -> None:
    world = World(bridge=True, core_published=False)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 1
    assert world.writes() == []
    assert "builds on “core”, which isn't published" in said(result)
    assert "lorenzo repo publish --tenant core" in said(result)


def test_a_dependency_only_someone_else_can_grant_says_who_to_ask_and_grants_nothing(
    tmp_path: Path,
) -> None:
    world = World(bridge=True, core_owned=False)
    result = offer(tmp_path, world, "--yes")

    assert result.exit_code == 1
    assert world.writes() == [CORE_GRANT]  # the attempt, refused: nothing was granted
    assert not world.granted and not world.core_granted
    text = said(result)
    assert "only its owners can grant it" in text
    assert f"lorenzo repo grant {TARGET_ID} --tenant core" in text


def test_the_plan_before_asking_names_each_dependency_and_what_it_needs(tmp_path: Path) -> None:
    world = World(bridge=True)
    declined = offer(tmp_path, world, interactive=True, input="n\n")

    assert declined.exit_code == 1
    assert world.writes() == []
    assert "grant core, which sunken-vale builds on: to be granted" in said(declined)


def test_a_dry_run_names_the_dependencies_and_writes_nothing(tmp_path: Path) -> None:
    world = World(bridge=True)
    result = offer(tmp_path, world, "--dry-run", "--json")

    assert result.exit_code == 2
    assert world.writes() == []
    document = json.loads(result.stdout)
    assert document["dependencies"] == {"core": "needs-grant"}
    assert document["steps"] == ["grant:core", "grant", "copy"]


def test_a_dependency_the_caller_cannot_see_is_unknown_in_a_dry_run(tmp_path: Path) -> None:
    world = World(bridge=True, core_owned=False)
    result = offer(tmp_path, world, "--dry-run")

    assert result.exit_code == 2
    assert "to be granted, by you if you own it" in said(result)
    assert world.writes() == []


def test_a_repository_that_copied_nothing_has_no_dependencies(tmp_path: Path) -> None:
    result = offer(tmp_path, World(), "--yes", "--json")

    assert json.loads(result.stdout)["dependencies"] == {}


# --- attachments (ADR 0172, 0174) ----------------------------------------------------


def test_apply_updates_leaves_every_attachment_for_its_own_decision(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [],
        "removed": [],
        "deleted_locally": [],
        "added": [],
        "attachments_added": [
            attachment(1, "Weapon", "Economic Object"),
            attachment(2, "Dagger", "Dagger 5e", parent_here=False),
        ],
        "attachments_removed": [attachment_ref(3, "Axe", "Axe 5e")],
    }
    result = offer(tmp_path, world, "--apply-updates", "--yes")

    # An attachment changes what an item is in the library: none is taken with the rest.
    assert world.writes() == []
    assert "3 update(s) wait for a decision" in said(result)


def test_without_the_flag_attachments_are_counted_with_the_updates_waiting(
    tmp_path: Path,
) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [],
        "removed": [],
        "deleted_locally": [],
        "added": [],
        "attachments_added": [attachment(1, "Weapon", "Economic Object")],
        "attachments_removed": [attachment_ref(3, "Axe", "Axe 5e")],
    }
    result = offer(tmp_path, world, interactive=False)

    assert world.writes() == []
    assert "2 update(s) wait for a decision" in said(result)


def test_a_dry_run_counts_no_attachment_among_the_updates_it_would_take(
    tmp_path: Path,
) -> None:
    world = World(granted=True, copied=True)
    world.updates = {
        "changed": [],
        "removed": [],
        "deleted_locally": [],
        "added": [],
        "attachments_added": [attachment(1, "Weapon", "Economic Object")],
    }
    result = offer(tmp_path, world, "--dry-run", "--apply-updates", "--json")

    # Nothing it would take: the attachment waits for its own decision.
    assert result.exit_code == 0
    assert json.loads(result.stdout)["clean_updates"] == 0
    assert world.writes() == []
