"""`lorenzo repo`: publish, grant, list, copy-plan, copy and updates (ADR 0159)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from repo_world import (
    DEFINITION_COLLISION,
    DEFINITION_ID,
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
    collision,
    field_change,
    problem,
    removed,
    row_change,
    runtime,
)
from rich.console import Console
from typer.testing import CliRunner

from lorenzo_cli.client.models import SubscriberOut
from lorenzo_cli.main import app
from lorenzo_cli.repo_report import print_subscribers

runner = CliRunner()


def said(result: object) -> str:
    """Everything printed, with the terminal's wrapping and boxes taken out."""
    import re

    text = getattr(result, "output")  # noqa: B009 - the runner's Result has no public type here
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", text).split())


def run(tmp_path: Path, world: World, *args: str, interactive: bool | None = None, **kw: object):  # noqa: ANN201
    return runner.invoke(
        app, ["repo", *args], obj=runtime(tmp_path, world, interactive=interactive), **kw
    )


# --- publish and unpublish -----------------------------------------------------------


def test_publishing_a_draft_says_it_is_published(tmp_path: Path) -> None:
    world = World(published_at=None)
    result = run(tmp_path, world, "publish", "--tenant", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert world.writes() == [("PUT", f"/tenants/{REPO_ID}/published")]
    assert "sunken-vale is published" in said(result)


def test_publishing_again_says_it_announced_an_update(tmp_path: Path) -> None:
    result = run(tmp_path, World(), "publish", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert "update" in said(result)


def test_publish_json_is_the_tenant(tmp_path: Path) -> None:
    result = run(tmp_path, World(), "publish", "-t", "sunken-vale", "--json")

    assert json.loads(result.stdout)["slug"] == "sunken-vale"


def test_a_play_tenant_cannot_be_published_and_nothing_is_sent(tmp_path: Path) -> None:
    world = World()
    result = run(tmp_path, world, "publish", "--tenant", "table-one")

    assert result.exit_code == 1
    assert "not a repository" in said(result)
    assert world.writes() == []


def test_unpublishing_withdraws_it_and_says_copies_stay(tmp_path: Path) -> None:
    world = World()
    result = run(tmp_path, world, "unpublish", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert world.writes() == [("DELETE", f"/tenants/{REPO_ID}/published")]
    assert "draft again" in said(result)
    assert "stay theirs" in said(result)


# --- grant, revoke, subscribers ------------------------------------------------------


def test_granting_to_one_of_your_tenants_by_slug(tmp_path: Path) -> None:
    world = World()
    result = run(tmp_path, world, "grant", "table-one", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert world.writes() == [("PUT", f"/tenants/{REPO_ID}/subscribers/{TARGET_ID}")]
    assert "Granted sunken-vale to table-one" in said(result)
    assert "members have been told" in said(result)


def test_granting_by_id_needs_no_lookup(tmp_path: Path) -> None:
    world = World()
    run(tmp_path, world, "grant", str(STRANGER_ID), "-t", "sunken-vale")

    assert ("PUT", f"/tenants/{REPO_ID}/subscribers/{STRANGER_ID}") in world.writes()
    assert not any(r.url.path == "/tenants" and r.url.params.get("page") for r in world.log[1:])


def test_a_grant_that_exists_is_fine_and_said_so(tmp_path: Path) -> None:
    result = run(tmp_path, World(granted=True), "grant", "table-one", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert "already had access" in said(result)


def test_granting_an_unpublished_repository_says_nothing_is_visible_yet(tmp_path: Path) -> None:
    result = run(tmp_path, World(published_at=None), "grant", "table-one", "-t", "sunken-vale")

    assert "isn't published yet" in said(result)
    assert "lorenzo repo publish --tenant sunken-vale" in said(result)


def test_an_unknown_slug_to_grant_says_to_ask_for_the_id(tmp_path: Path) -> None:
    world = World()
    result = run(tmp_path, world, "grant", "somebody-elses", "-t", "sunken-vale")

    assert result.exit_code == 1
    assert "ask its members for its id" in said(result)
    assert world.writes() == []


def test_revoking_finds_the_subscriber_by_slug_in_the_repositorys_own_list(tmp_path: Path) -> None:
    world = World(granted=True)
    result = run(tmp_path, world, "revoke", "table-one", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert world.writes() == [("DELETE", f"/tenants/{REPO_ID}/subscribers/{TARGET_ID}")]
    assert "stays its own" in said(result)


def test_revoking_what_was_never_granted_is_named(tmp_path: Path) -> None:
    world = World(granted=False)
    result = run(tmp_path, world, "revoke", "table-one", "-t", "sunken-vale")

    assert result.exit_code == 1
    assert "holds no grant" in said(result)
    assert world.writes() == []


def test_subscribers_lists_each_with_its_id(tmp_path: Path) -> None:
    result = run(tmp_path, World(granted=True), "subscribers", "-t", "sunken-vale")

    assert result.exit_code == 0, result.output
    assert "table-one" in result.output
    assert str(TARGET_ID) in said(result)
    empty = run(tmp_path, World(granted=False), "subscribers", "-t", "sunken-vale")
    assert "isn't granted to any tenant" in said(empty)


def test_subscribers_say_who_copied_it_and_who_kept_a_copy_without_an_invitation() -> None:
    day = datetime(2026, 10, 3, tzinfo=UTC)
    rows = [
        SubscriberOut(
            tenant_id=uuid.UUID(int=1),
            name="Invited",
            slug="invited",
            granted_at=day,
            granted_by=None,
            copied_at=None,
            synced_at=None,
        ),
        SubscriberOut(
            tenant_id=uuid.UUID(int=2),
            name="Kept",
            slug="kept",
            granted_at=None,
            granted_by=None,
            copied_at=day,
            synced_at=day,
        ),
    ]
    console = Console(width=140, record=True)

    print_subscribers(console, rows)
    lines = console.export_text().splitlines()
    invited = next(line for line in lines if "invited" in line and "Invited" in line)
    kept = next(line for line in lines if "Kept" in line)

    assert "2026-10-03" in invited and "no longer" not in invited
    assert "no longer" in kept
    assert "2026-10-03" in kept


def test_subscribers_json_is_an_array(tmp_path: Path) -> None:
    result = run(tmp_path, World(granted=True), "subscribers", "-t", "sunken-vale", "--json")

    assert [row["slug"] for row in json.loads(result.stdout)] == ["table-one"]


# --- list ----------------------------------------------------------------------------


def test_list_shows_state_and_flags_a_repository_that_published_since(tmp_path: Path) -> None:
    world = World(granted=True, copied=True, published_at="2026-10-04T00:00:00Z")
    result = run(tmp_path, world, "list", "-t", "table-one")

    assert result.exit_code == 0, result.output
    assert "sunken-vale" in said(result)
    assert "updated since" in said(result)
    quiet = run(tmp_path, World(granted=True, copied=True), "list", "-t", "table-one")
    assert "updated since" not in said(quiet)


def test_list_with_nothing_says_so(tmp_path: Path) -> None:
    result = run(tmp_path, World(), "list", "-t", "table-one")

    assert "No repository is granted to “table-one”" in said(result)


def test_list_json_is_the_apis_rows(tmp_path: Path) -> None:
    result = run(tmp_path, World(granted=True), "list", "-t", "table-one", "--json")

    rows = json.loads(result.stdout)
    assert rows[0]["repository"]["slug"] == "sunken-vale"
    assert rows[0]["copied_at"] is None


# --- copy-plan -----------------------------------------------------------------------


def test_copy_plan_that_could_go_ahead_exits_zero(tmp_path: Path) -> None:
    world = World(granted=True)
    result = run(tmp_path, world, "copy-plan", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 0, result.output
    assert "12 entities" in said(result)
    assert world.writes() == []
    assert str(REPO_ID) in world.log[-1].url.path  # the slug became the id


def test_copy_plan_that_needs_choices_exits_two_and_lists_them_with_ids(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION, SLUG_COLLISION])
    result = run(tmp_path, world, "copy-plan", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 2, result.output
    text = said(result)
    assert "stat_group “Physical”" in text
    assert str(GROUP_ID) in text
    assert "choose rename, merge, skip" in text
    assert "choose rename, skip" in text  # a slug can't be merged


def test_copy_plan_that_would_be_refused_exits_one_and_says_why(tmp_path: Path) -> None:
    ungranted = run(
        tmp_path, World(granted=False, copied=True), "copy-plan", str(REPO_ID), "-t", "table-one"
    )
    assert ungranted.exit_code == 1
    assert "already copied here" in said(ungranted)
    assert "lorenzo repo updates" in said(ungranted)

    world = World(granted=False)
    result = run(tmp_path, world, "copy-plan", str(REPO_ID), "-t", "table-one")
    assert result.exit_code == 1
    assert "isn't granted to this tenant" in said(result)


def test_copy_plan_json_is_the_plan_and_keeps_the_exit_code(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION])
    result = run(tmp_path, world, "copy-plan", "sunken-vale", "-t", "table-one", "--json")

    assert result.exit_code == 2
    document = json.loads(result.stdout)
    assert document["collisions"][0]["source_id"] == str(GROUP_ID)
    assert document["steps"][0]["entities"] == 12


def test_an_unknown_repository_slug_says_where_to_look(tmp_path: Path) -> None:
    result = run(tmp_path, World(granted=True), "copy-plan", "nope", "-t", "table-one")

    assert result.exit_code == 1
    assert "no repository “nope”" in said(result)
    assert "lorenzo repo list --tenant table-one" in said(result)


# --- copy ----------------------------------------------------------------------------


def test_a_dry_run_asks_for_nothing_writes_nothing_and_says_what_would_be_copied(
    tmp_path: Path,
) -> None:
    world = World(granted=True)
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--dry-run")

    assert result.exit_code == 0, result.output
    assert world.bodies("POST", "/copy") == [{"dry_run": True}]
    assert "Would copy Sunken Vale: 12 entities" in said(result)
    assert not world.copied


def test_copy_asks_first_at_a_terminal_and_a_no_copies_nothing(tmp_path: Path) -> None:
    world = World(granted=True)
    result = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", interactive=True, input="n\n"
    )

    assert result.exit_code == 1
    assert "Copy Sunken Vale into table-one?" in said(result)
    assert world.writes() == []


def test_copy_goes_ahead_on_a_yes_at_the_prompt_and_with_the_flag(tmp_path: Path) -> None:
    world = World(granted=True)
    asked = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", interactive=True, input="y\n"
    )
    assert asked.exit_code == 0, asked.output
    assert world.copied
    assert "Copied Sunken Vale: 12 entities" in said(asked)

    other = World(granted=True)
    flagged = run(tmp_path, other, "copy", "sunken-vale", "-t", "table-one", "--yes")
    assert flagged.exit_code == 0, flagged.output
    assert other.copied


def test_copy_that_cannot_ask_needs_yes_and_json_never_asks(tmp_path: Path) -> None:
    world = World(granted=True)
    quiet = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", interactive=False)
    assert quiet.exit_code == 1
    assert "--yes" in said(quiet)

    json_run = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--json", interactive=True
    )
    assert json_run.exit_code == 1
    assert world.writes() == []


def test_copy_json_is_the_apis_answer(tmp_path: Path) -> None:
    world = World(granted=True)
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["steps"][0]["name"] == "Sunken Vale"


def test_a_collision_without_a_choice_stops_with_nothing_copied_and_exit_two(
    tmp_path: Path,
) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION])
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes")

    assert result.exit_code == 2
    assert not world.copied
    assert "Nothing was copied" in said(result)
    assert str(GROUP_ID) in said(result)
    assert "--on-collision" in said(result)


def test_on_collision_merge_answers_every_collision_that_allows_it(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION, DEFINITION_COLLISION])
    result = run(
        tmp_path,
        world,
        "copy",
        "sunken-vale",
        "-t",
        "table-one",
        "--yes",
        "--on-collision",
        "merge",
    )

    assert result.exit_code == 0, result.output
    assert world.copied
    sent = world.bodies("POST", "/copy")[-1]["resolutions"]
    assert {(r["kind"], r["action"]) for r in sent} == {
        ("stat_group", "merge"),
        ("stat_definition", "merge"),
    }


def test_a_slug_cannot_be_merged_so_it_stays_open_for_a_choice(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION, SLUG_COLLISION])
    result = run(
        tmp_path,
        world,
        "copy",
        "sunken-vale",
        "-t",
        "table-one",
        "--yes",
        "--on-collision",
        "merge",
    )

    assert result.exit_code == 2
    assert not world.copied
    text = said(result)
    assert "slug “longsword”" in text
    assert "stat_group" not in text  # the merged one is not asked about again


def test_a_choices_file_decides_and_wins_over_the_flag(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION, SLUG_COLLISION])
    file = tmp_path / "choices.json"
    file.write_text(
        json.dumps(
            [
                {
                    "kind": "slug",
                    "source_id": str(SLUG_ID),
                    "action": "rename",
                    "name": "longsword-2",
                },
                {"kind": "stat_group", "source_id": str(GROUP_ID), "action": "skip"},
            ]
        )
    )
    result = run(
        tmp_path,
        world,
        "copy",
        "sunken-vale",
        "-t",
        "table-one",
        "--yes",
        "--on-collision",
        "merge",
        "--choices",
        str(file),
    )

    assert result.exit_code == 0, result.output
    sent = {r["kind"]: r for r in world.bodies("POST", "/copy")[-1]["resolutions"]}
    assert sent["slug"]["name"] == "longsword-2"
    assert sent["stat_group"]["action"] == "skip"  # the file, not --on-collision


def test_a_choices_file_may_wrap_the_list_in_resolutions(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[SLUG_COLLISION])
    file = tmp_path / "choices.json"
    file.write_text(
        json.dumps({"resolutions": [{"kind": "slug", "source_id": str(SLUG_ID), "action": "skip"}]})
    )
    result = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes", "--choices", str(file)
    )

    assert result.exit_code == 0, result.output


def test_a_file_choice_that_cannot_work_is_refused_by_the_api_and_said_so(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[SLUG_COLLISION])
    file = tmp_path / "choices.json"
    file.write_text(json.dumps([{"kind": "slug", "source_id": str(SLUG_ID), "action": "merge"}]))
    result = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes", "--choices", str(file)
    )

    assert result.exit_code == 1
    assert "That choice can't be applied (HTTP 422)" in said(result)
    assert not world.copied


@pytest.mark.parametrize("content", ["not json", '{"nothing": 1}', '[{"kind": "slug"}]'])
def test_a_bad_choices_file_is_said_plainly(tmp_path: Path, content: str) -> None:
    world = World(granted=True)
    file = tmp_path / "choices.json"
    file.write_text(content)
    result = run(
        tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes", "--choices", str(file)
    )

    assert result.exit_code == 1
    assert str(file) in said(result)
    assert world.writes() == []


def test_open_collisions_with_json_are_a_document_and_exit_two(tmp_path: Path) -> None:
    world = World(granted=True, collisions=[GROUP_COLLISION])
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes", "--json")

    assert result.exit_code == 2
    assert json.loads(result.stdout)["open_collisions"][0]["name"] == "Physical"


def test_a_repository_already_copied_points_at_updates_and_again(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes")

    assert result.exit_code == 1
    assert "not another copy" in said(result)  # the API's own words
    assert "Run `lorenzo repo updates` to take them" in said(result)
    assert "--again keep|purge" in said(result)


def test_again_is_sent_and_a_purge_is_asked_about_in_plain_words(tmp_path: Path) -> None:
    world = World(granted=True, copied=True)
    declined = run(
        tmp_path,
        world,
        "copy",
        "sunken-vale",
        "-t",
        "table-one",
        "--again",
        "purge",
        interactive=True,
        input="n\n",
    )
    assert declined.exit_code == 1
    assert "deletes what the earlier copy created" in said(declined)
    assert world.writes() == []

    world.previous = {
        "mode": "purge",
        "entities": 9,
        "stat_groups": 1,
        "stat_definitions": 3,
        "also_removed": {"entity_stat": 4},
    }
    done = run(
        tmp_path,
        world,
        "copy",
        "sunken-vale",
        "-t",
        "table-one",
        "--again",
        "purge",
        "--yes",
    )
    assert done.exit_code == 0, done.output
    assert world.bodies("POST", "/copy")[-1]["again"] == "purge"
    assert "Also removed with them" in said(done)
    assert "4 entity_stat" in said(done)


def test_a_missing_grant_lists_what_is_missing(tmp_path: Path) -> None:
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
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes")

    assert result.exit_code == 1
    assert "D&D 5e (not granted)" in said(result)


# --- updates -------------------------------------------------------------------------


def world_with(updates: dict[str, list[dict[str, object]]]) -> World:
    world = World(granted=True, copied=True)
    world.updates = {"changed": [], "removed": [], "deleted_locally": [], "added": [], **updates}
    return world


def test_updates_with_nothing_new_exits_zero(tmp_path: Path) -> None:
    result = run(tmp_path, world_with({}), "updates", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 0, result.output
    assert "nothing new" in said(result)


def test_updates_shows_each_row_and_field_and_exits_two(tmp_path: Path) -> None:
    world = world_with(
        {
            "changed": [row_change(1, "Longsword", "clean", "conflict")],
            "added": [
                added(1, "Glaive"),
                added(2, "Maul", collision("slug", SLUG_ID, "maul", ["rename", "skip"])),
            ],
            "removed": [removed(1, "Old Axe")],
        }
    )
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 2
    text = said(result)
    assert "changed entity “Longsword”" in text
    assert "field0: clean" in text and "field1: conflict" in text
    assert "added entity “Glaive”" in text
    assert "“maul” is already in use here" in text
    assert "gone upstream: entity “Old Axe”" in text
    assert "--apply" in text
    assert world.writes() == []


def test_things_deleted_here_are_shown_but_are_not_something_to_take(tmp_path: Path) -> None:
    world = world_with({"deleted_locally": [removed(1, "My Axe")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 0
    assert "1 you deleted here" in said(result)


def test_updates_json_is_the_apis_answer(tmp_path: Path) -> None:
    world = world_with({"changed": [row_change(1, "Longsword", "clean")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--json")

    assert result.exit_code == 2
    assert json.loads(result.stdout)["changed"][0]["name"] == "Longsword"


def test_apply_takes_only_what_needs_no_decision(tmp_path: Path) -> None:
    world = world_with(
        {
            "changed": [
                row_change(1, "Clean", "clean", "clean"),
                row_change(2, "Conflicted", "clean", "conflict"),
                row_change(3, "Only by hand", "not_applicable"),
            ],
            "added": [
                added(1, "Fresh"),
                added(2, "Colliding", collision("slug", SLUG_ID, "x", ["rename", "skip"])),
            ],
            "removed": [removed(1, "Old Axe")],
        }
    )
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    sent = world.bodies("POST", "/updates")
    assert [(a["action"], a["source_id"]) for a in sent[0]["actions"]] == [
        ("apply", str(uuid.UUID(int=101))),
        ("add", str(uuid.UUID(int=301))),
    ]
    assert "dry_run" not in sent[0]
    assert result.exit_code == 2  # something is left for a decision
    text = said(result)
    assert "Took 1 changed, 1 added, 0 detached" in text
    assert "“Conflicted” conflicts with your own edit of field1" in text
    assert "“Colliding” would collide" in text
    assert "1 gone upstream" in text


def test_apply_with_nothing_that_needs_no_decision_sends_nothing(tmp_path: Path) -> None:
    world = world_with({"changed": [row_change(1, "Conflicted", "conflict")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    assert world.writes() == []
    assert result.exit_code == 2
    assert "Nothing to take that needs no decision" in said(result)


def test_apply_with_everything_taken_exits_zero(tmp_path: Path) -> None:
    world = world_with({"changed": [row_change(1, "Clean", "clean")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    assert result.exit_code == 0, result.output


def test_apply_dry_run_is_passed_to_the_api(tmp_path: Path) -> None:
    world = world_with({"changed": [row_change(1, "Clean", "clean")]})
    result = run(
        tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--dry-run"
    )

    assert result.exit_code == 0, result.output
    assert world.bodies("POST", "/updates")[0]["dry_run"] is True
    assert "Would take 1 changed" in said(result)


def test_apply_asks_first_and_cannot_without_yes_when_nobody_can_answer(tmp_path: Path) -> None:
    world = world_with({"changed": [row_change(1, "Clean", "clean")]})
    quiet = run(
        tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", interactive=False
    )
    assert quiet.exit_code == 1
    assert world.writes() == []

    declined = run(
        tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply",
        interactive=True, input="n\n",
    )  # fmt: skip
    assert declined.exit_code == 1
    assert world.writes() == []

    accepted = run(
        tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply",
        interactive=True, input="y\n",
    )  # fmt: skip
    assert accepted.exit_code == 0, accepted.output
    assert len(world.writes()) == 1


def test_apply_json_gives_the_result_and_what_was_left(tmp_path: Path) -> None:
    world = world_with(
        {
            "changed": [row_change(1, "Clean", "clean"), row_change(2, "Conflicted", "conflict")],
            "removed": [removed(1, "Old Axe")],
        }
    )
    result = run(
        tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes", "--json"
    )

    document = json.loads(result.stdout)
    assert result.exit_code == 2
    assert document["result"]["applied"] == 1
    assert [r["name"] for r in document["left"]["conflicts"]] == ["Conflicted"]
    assert document["left"]["removed"] == 1


def test_actions_are_sent_as_given_so_conflicts_and_detaches_can_be_decided(
    tmp_path: Path,
) -> None:
    world = world_with(
        {"changed": [row_change(2, "Conflicted", "conflict")], "removed": [removed(1, "Old Axe")]}
    )
    chosen = [
        {
            "kind": "entity",
            "source_id": str(uuid.UUID(int=102)),
            "action": "apply",
            "take_upstream": ["field0"],
        },
        {"kind": "entity", "source_id": str(uuid.UUID(int=401)), "action": "detach"},
    ]
    file = tmp_path / "actions.json"
    file.write_text(json.dumps({"actions": chosen}))
    result = run(
        tmp_path,
        world,
        "updates",
        "sunken-vale",
        "-t",
        "table-one",
        "--actions",
        str(file),
        "--yes",
    )

    assert result.exit_code == 0, result.output
    sent = world.bodies("POST", "/updates")[0]["actions"]
    assert sent[0]["take_upstream"] == ["field0"]
    assert sent[1]["action"] == "detach"
    assert "Took 1 changed, 0 added, 1 detached" in said(result)


def test_apply_and_actions_cannot_be_combined_and_dry_run_needs_one_of_them(tmp_path: Path) -> None:
    file = tmp_path / "actions.json"
    file.write_text("[]")
    both = run(
        tmp_path,
        world_with({}),
        "updates",
        "sunken-vale",
        "-t",
        "table-one",
        "--apply",
        "--actions",
        str(file),
    )
    assert both.exit_code == 2

    alone = run(tmp_path, world_with({}), "updates", "sunken-vale", "-t", "table-one", "--dry-run")
    assert alone.exit_code == 2


def test_a_bad_actions_file_is_said_plainly(tmp_path: Path) -> None:
    file = tmp_path / "actions.json"
    file.write_text('[{"kind": "entity"}]')
    result = run(
        tmp_path,
        world_with({}),
        "updates",
        "sunken-vale",
        "-t",
        "table-one",
        "--actions",
        str(file),
        "--yes",
    )

    assert result.exit_code == 1
    assert str(file) in said(result)


def test_a_field_change_helper_matches_the_api_shape() -> None:
    assert set(field_change("name", "clean")) == {
        "field", "label", "state", "base", "upstream", "local", "added", "removed",
    }  # fmt: skip


def test_every_request_carries_the_token(tmp_path: Path) -> None:
    world = World(granted=True)
    run(tmp_path, world, "list", "-t", "table-one")

    assert world.log
    assert all(isinstance(r, httpx.Request) for r in world.log)
    assert {r.headers["Authorization"] for r in world.log} == {"Bearer tok"}


def test_the_stranger_tenant_does_not_exist_in_the_world() -> None:
    assert STRANGER_ID != TARGET_ID != REPO_ID
    assert DEFINITION_ID not in (GROUP_ID, SLUG_ID)


# --- attachments (ADR 0172, 0174) ----------------------------------------------------


def test_a_plan_counts_a_steps_attachments_and_lists_the_ones_it_leaves_out(
    tmp_path: Path,
) -> None:
    world = World(granted=True)
    world.step_attachments = 3
    world.step_dropped = [
        {
            "kind": "attachment",
            "source_id": str(uuid.UUID(int=600)),
            "reason": "the item it attaches to isn't here",
        }
    ]
    result = run(tmp_path, world, "copy-plan", "sunken-vale", "-t", "table-one")

    text = said(result)
    assert "7 pieces of information, 3 attachments (granted, published)." in text
    assert f"leaves out attachment {uuid.UUID(int=600)}: the item it attaches to isn't here" in text


def test_a_step_with_one_attachment_says_so_and_one_with_none_says_nothing(
    tmp_path: Path,
) -> None:
    one = World(granted=True)
    one.step_attachments = 1
    none = World(granted=True)

    assert "7 pieces of information, 1 attachment (" in said(
        run(tmp_path, one, "copy-plan", "sunken-vale", "-t", "table-one")
    )
    assert "attachment" not in said(
        run(tmp_path, none, "copy-plan", "sunken-vale", "-t", "table-one")
    )


def test_a_copy_says_how_many_attachments_it_wrote_and_what_it_left_out(tmp_path: Path) -> None:
    world = World(granted=True)
    world.step_attachments = 2
    world.step_dropped = [
        {
            "kind": "attachment",
            "source_id": str(uuid.UUID(int=601)),
            "reason": "it would make a prototype loop here",
        }
    ]
    result = run(tmp_path, world, "copy", "sunken-vale", "-t", "table-one", "--yes")

    assert result.exit_code == 0, result.output
    text = said(result)
    assert (
        "Copied Sunken Vale: 12 entities" in text
        and "7 pieces of information, 2 attachments." in text
    )
    assert f"left out attachment {uuid.UUID(int=601)}: it would make a prototype loop here" in text


def test_updates_lists_the_attachments_added_gone_and_removed_here(tmp_path: Path) -> None:
    world = world_with(
        {
            "attachments_added": [
                attachment(1, "Weapon", "Economic Object"),
                attachment(2, "Longsword", "Longsword 5e", parent_here=False),
            ],
            "attachments_removed": [attachment_ref(3, "Dagger", "Dagger 5e")],
            "attachments_deleted_locally": [attachment_ref(4, "Axe", "Axe 5e")],
        }
    )
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 2
    text = said(result)
    assert "added attachment “Economic Object” on “Weapon”" in text
    assert (
        "added attachment “Longsword 5e” on “Longsword”, but it waits: "
        "the prototype it attaches isn't here" in text
    )
    assert "gone upstream: attachment “Dagger 5e” on “Dagger”" in text
    assert "1 attachment(s) you removed here (nothing to do)." in text
    assert world.writes() == []


def test_only_attachments_deleted_here_is_nothing_new(tmp_path: Path) -> None:
    world = world_with({"attachments_deleted_locally": [attachment_ref(4, "Axe", "Axe 5e")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one")

    assert result.exit_code == 0
    assert "nothing new" in said(result)
    assert "1 attachment(s) you removed here" in said(result)


def test_an_attachment_alone_is_something_to_take(tmp_path: Path) -> None:
    world = world_with({"attachments_added": [attachment(1, "Weapon", "Economic Object")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--json")

    assert result.exit_code == 2
    assert json.loads(result.stdout)["attachments_added"][0]["parent_name"] == "Economic Object"


def test_apply_takes_the_attachments_that_can_be_applied_and_those_whose_row_comes_with_it(
    tmp_path: Path,
) -> None:
    world = world_with(
        {
            "added": [added(1, "Greatsword 5e")],
            "attachments_added": [
                attachment(1, "Weapon", "Economic Object"),
                # Its parent is the entity this same call adds.
                attachment(
                    2,
                    "Longsword",
                    "Greatsword 5e",
                    parent_source=uuid.UUID(int=301),
                    parent_here=False,
                ),
                # Its end is neither here nor coming.
                attachment(3, "Dagger", "Dagger 5e", parent_here=False),
            ],
            "attachments_removed": [attachment_ref(4, "Axe", "Axe 5e")],
        }
    )
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    (sent,) = world.bodies("POST", "/updates")
    assert [a["action"] for a in sent["actions"]] == ["add"]
    assert sent["attachments"] == [
        {
            "child_source_id": str(uuid.UUID(int=601)),
            "parent_source_id": str(uuid.UUID(int=701)),
            "action": "add",
        },
        {
            "child_source_id": str(uuid.UUID(int=602)),
            "parent_source_id": str(uuid.UUID(int=301)),
            "action": "add",
        },
    ]
    assert result.exit_code == 2  # one waits and one is gone upstream
    text = said(result)
    assert "Took 0 changed, 1 added, 0 detached." in text
    assert "Attachments: 2 added, 0 detached." in text
    assert "attachment “Dagger 5e” on “Dagger” waits: the prototype it attaches isn't here" in text
    assert "1 attachment(s) gone upstream (detach is a decision)" in text


def test_apply_with_only_attachments_to_take_exits_zero_and_asks_once(tmp_path: Path) -> None:
    world = world_with({"attachments_added": [attachment(1, "Weapon", "Economic Object")]})
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    assert result.exit_code == 0, result.output
    assert [a["action"] for a in world.bodies("POST", "/updates")[0]["attachments"]] == ["add"]
    assert world.bodies("POST", "/updates")[0]["actions"] == []


def test_apply_json_says_what_it_left_among_the_attachments(tmp_path: Path) -> None:
    world = world_with(
        {
            "attachments_added": [attachment(3, "Dagger", "Dagger 5e", parent_here=False)],
            "attachments_removed": [attachment_ref(4, "Axe", "Axe 5e")],
        }
    )
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--json")

    assert result.exit_code == 2
    left = json.loads(result.stdout)["left"]
    assert left["attachments_waiting"] == [
        {
            "child_source_id": str(uuid.UUID(int=603)),
            "parent_source_id": str(uuid.UUID(int=703)),
            "reason": "the prototype it attaches isn't here",
        }
    ]
    assert left["attachments_removed"] == 1


def test_a_file_can_name_attachments_to_add_and_to_detach(tmp_path: Path) -> None:
    world = world_with({})
    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "actions": [],
                "attachments": [
                    {
                        "child_source_id": str(uuid.UUID(int=604)),
                        "parent_source_id": str(uuid.UUID(int=704)),
                        "action": "detach",
                    }
                ],
            }
        )
    )
    result = run(
        tmp_path,
        world,
        "updates",
        "sunken-vale",
        "-t",
        "table-one",
        "--actions",
        str(decisions),
        "--yes",
    )

    assert result.exit_code == 0, result.output
    (sent,) = world.bodies("POST", "/updates")
    assert sent["attachments"][0]["action"] == "detach"
    assert "Attachments: 0 added, 1 detached." in said(result)


def test_a_file_whose_attachments_are_not_a_list_is_refused(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({"actions": [], "attachments": "all of them"}))
    result = run(
        tmp_path,
        world_with({}),
        "updates",
        "sunken-vale",
        "-t",
        "table-one",
        "--actions",
        str(decisions),
        "--yes",
    )

    assert result.exit_code == 1
    assert '"attachments": [...]' in said(result)


def test_an_attachment_that_could_not_be_applied_is_said_and_stays_on_offer(
    tmp_path: Path,
) -> None:
    world = world_with({"attachments_added": [attachment(1, "Weapon", "Economic Object")]})
    world.not_applied = [
        {
            "kind": "attachment",
            "source_id": str(uuid.UUID(int=601)),
            "field": "prototypes",
            "reason": "it would make a prototype loop here",
            "name": None,
            "label": None,
        }
    ]
    result = run(tmp_path, world, "updates", "sunken-vale", "-t", "table-one", "--apply", "--yes")

    assert (
        f"Couldn't apply an attachment on {uuid.UUID(int=601)}: "
        "it would make a prototype loop here. It stays on offer." in said(result)
    )
