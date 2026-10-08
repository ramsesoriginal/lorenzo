"""Teaching the map at a terminal, against the real API (ADR 0144)."""

from __future__ import annotations

import json
from pathlib import Path

from e2e.helpers import FIXTURES, SharedRepository, by_slug, parent_names, run_cli, tenant_id
from e2e.stack import Stack
from e2e.test_import import seeded_tenant

WEAPONS = str(FIXTURES / "weapons.js")


def teach(stack: Stack, token: str, tmp_path: Path, tenant: str, *args: str, answers: str):
    return run_cli(
        stack,
        token,
        tmp_path,
        "apply",
        "--tenant",
        tenant,
        "--teach",
        "--review-queue",
        str(tmp_path / "review-queue.json"),
        "--proposed-map",
        str(tmp_path / "proposed.map.toml"),
        WEAPONS,
        *args,
        answers=answers,
    )


CATEGORY_ANSWERS = "c\nproficiency\nhb-legendary\nLegendary weapon\n"


def test_an_unknown_value_is_asked_once_used_at_once_and_offered_to_the_map(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    map_file = tmp_path / "mine.map.toml"
    map_file.write_text('schema = 1\n[attributes.weapons]\nflavour = "drop"\n')

    # Create a category for "Legendary", then agree to import, then agree to save the row.
    result = teach(
        stack,
        token,
        tmp_path,
        tenant,
        "--map",
        str(map_file),
        answers=CATEGORY_ANSWERS + "y\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("What should it be?") == 1
    assert "weapons.type = 'Legendary' (1 item(s): Moon whip)" in result.output
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        whip = by_slug(api, tid, "basic-weapons-moon-whip")
        assert parent_names(whip) == ["Legendary weapon", "Melee weapon", "Whip"]
    saved = map_file.read_text()
    assert 'flavour = "drop"' in saved  # what was there is kept
    assert '"legendary" = { disposition = "create-under"' in saved
    assert (tmp_path / "proposed.map.toml").read_text().startswith("[classify.weapons.type]")
    # The file is now enough on its own: nothing is left to ask or to do.
    again = run_cli(
        stack,
        token,
        tmp_path,
        "plan",
        "--tenant",
        tenant,
        WEAPONS,
        "--map",
        str(map_file),
        "--json",
    )
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["header"]["counts"]["held"] == 0


def test_a_value_left_alone_stays_held_and_nothing_is_written_to_the_map(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    map_file = tmp_path / "mine.map.toml"
    map_file.write_text('schema = 1\n[attributes.weapons]\nflavour = "drop"\n')

    result = teach(stack, token, tmp_path, tenant, "--map", str(map_file), answers="l\ny\n")

    assert result.exit_code == 1  # still one item held for review
    assert map_file.read_text() == 'schema = 1\n[attributes.weapons]\nflavour = "drop"\n'
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        assert (
            api.get(
                f"/tenants/{tid}/entities/resolve", params={"slug": "basic-weapons-moon-whip"}
            ).json()
            == []
        )
        assert by_slug(api, tid, "basic-weapons-purple-sword")["name"] == "Purple sword"


def test_a_row_is_not_appended_when_the_map_already_has_that_table(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    map_file = tmp_path / "mine.map.toml"
    original = (
        'schema = 1\n[classify.weapons.type]\nnet = "attach-form-only"\n'
        '[attributes.weapons]\nflavour = "drop"\n'
    )
    map_file.write_text(original)

    result = teach(
        stack, token, tmp_path, tenant, "--map", str(map_file), answers=CATEGORY_ANSWERS + "y\ny\n"
    )

    assert result.exit_code == 0, result.output
    # The output wraps at the terminal's width, and the paths in it differ from run to run (a
    # parallel worker's is longer), so a phrase can fall across a line break: compare it unwrapped.
    said = " ".join(result.output.split())
    assert "Not appended" in said and "wouldn't be valid TOML" in said
    assert map_file.read_text() == original  # never left half-edited
    assert '"legendary"' in (tmp_path / "proposed.map.toml").read_text()


def test_without_a_terminal_teach_asks_nothing(
    stack: Stack, tmp_path: Path, shared_repository: SharedRepository
) -> None:
    token, tenant = shared_repository.token, shared_repository.slug

    result = run_cli(
        stack,
        token,
        tmp_path,
        "plan",
        "--tenant",
        tenant,
        "--teach",
        "--review-queue",
        str(tmp_path / "q.json"),
        "--proposed-map",
        str(tmp_path / "p.toml"),
        WEAPONS,
    )

    assert result.exit_code == 1
    assert "What should it be?" not in result.output
