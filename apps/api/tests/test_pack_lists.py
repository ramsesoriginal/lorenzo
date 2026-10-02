"""A pack's contents list - ADR 0149. The parser against tests/data/pack_lists.json,
the examples the CLI's own parser is held to as well, plus the counting and the
limits."""

import json
from pathlib import Path
from typing import Any

import pytest

from lorenzo_api.packs import (
    MAX_INSTANCES,
    MAX_LOOSE,
    MAX_QUANTITY,
    PackLine,
    PackNode,
    count_instances,
    list_problems,
    nest,
    parse_pack_list,
)

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "data" / "pack_lists.json").read_text(encoding="utf-8")
)["cases"]


def _tree(nodes: list[PackNode]) -> list[dict[str, Any]]:
    return [
        {
            "label": node.line.label,
            "quantity": node.line.quantity,
            "children": _tree(node.children),
        }
        for node in nodes
    ]


def _nodes(text: str) -> list[PackNode]:
    return nest(parse_pack_list(text))


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_reads_the_lines_every_example_says(case: dict[str, Any]) -> None:
    expected = [
        PackLine(depth, quantity, label, slug) for depth, quantity, label, slug in case["lines"]
    ]
    assert parse_pack_list(case["text"]) == expected


@pytest.mark.parametrize(
    "case",
    [case for case in CASES if "tree" in case],
    ids=[c["name"] for c in CASES if "tree" in c],
)
def test_nests_the_lines_every_example_says(case: dict[str, Any]) -> None:
    assert _tree(_nodes(case["text"])) == case["tree"]


def test_the_hundred_character_slug_is_exactly_that() -> None:
    [line] = parse_pack_list(
        next(case for case in CASES if case["name"] == "a slug is 100 characters at most")["text"]
    )
    assert line.slug is not None
    assert len(line.slug) == 100


def test_a_container_is_made_once_per_unit() -> None:
    nodes = _nodes("- 2 x [Backpack](bp)\n  - 5 x [Rations](r)\n  - 2 x [Torch](t)")
    # Two backpacks, each with two stacks.
    assert count_instances(nodes, group=False) == 6
    assert count_instances(nodes, group=True) == 6


def test_a_top_level_stack_is_one_instance_for_a_being_and_one_per_unit_for_a_group() -> None:
    nodes = _nodes("- 5 x [Torch](t)\n- 1 x [Rope](r)")
    assert count_instances(nodes, group=False) == 2
    assert count_instances(nodes, group=True) == 6


def test_units_of_a_container_inside_a_container_multiply() -> None:
    nodes = _nodes("- 2 x [Chest](c)\n  - 3 x [Pouch](p)\n    - 4 x [Coin](k)")
    # 2 chests, each with 3 pouches, each holding one stack of coins.
    assert count_instances(nodes, group=False) == 2 * (1 + 3 * (1 + 1))


def test_a_good_list_has_no_problems() -> None:
    nodes = _nodes("- 1 x [Backpack](bp)\n  - 5 x [Rations](r)\n- 2 x [Torch](t)")
    assert list_problems(nodes, group=False) == []
    assert list_problems(nodes, group=True) == []


def test_a_line_without_a_link_is_a_problem_wherever_it_is() -> None:
    nodes = _nodes("- 1 x [Backpack](bp)\n  - 1 x Alms box\n- 1 x Censer")
    assert list_problems(nodes, group=False) == [
        "“Alms box” has no link to an item",
        "“Censer” has no link to an item",
    ]


def test_a_quantity_over_the_limit_is_a_problem() -> None:
    nodes = _nodes(f"- {MAX_QUANTITY + 1} x [Arrow](a)")
    assert list_problems(nodes, group=False) == [
        f"“Arrow”: {MAX_QUANTITY + 1} is more than {MAX_QUANTITY}"
    ]
    assert list_problems(_nodes(f"- {MAX_QUANTITY} x [Arrow](a)"), group=False) == []


def test_a_groups_loose_stack_has_its_own_limit() -> None:
    over = _nodes(f"- {MAX_LOOSE + 1} x [Arrow](a)")
    assert list_problems(over, group=False) == []
    [problem] = list_problems(over, group=True)
    assert problem.startswith("“Arrow”: a group holds")
    assert list_problems(_nodes(f"- {MAX_LOOSE} x [Arrow](a)"), group=True) == []
    # Inside a container it is one stack for a group too.
    inside = _nodes(f"- 1 x [Quiver](q)\n  - {MAX_LOOSE + 1} x [Arrow](a)")
    assert list_problems(inside, group=True) == []


def test_too_many_instances_is_a_problem() -> None:
    nodes = _nodes(f"- {MAX_INSTANCES} x [Backpack](bp)\n  - 1 x [Rope](r)")
    assert count_instances(nodes, group=False) == 2 * MAX_INSTANCES
    [problem] = list_problems(nodes, group=False)
    assert problem.startswith(f"the list would create {2 * MAX_INSTANCES} instances")
    at_the_limit = _nodes(f"- {MAX_INSTANCES // 2} x [Backpack](bp)\n  - 1 x [Rope](r)")
    assert list_problems(at_the_limit, group=False) == []
