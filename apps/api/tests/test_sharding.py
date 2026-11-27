"""ADR 0148: the suite is split over CI runners by what each test costs, not by how many."""

import _sharding

WEIGHTS = {
    "default": 0.5,
    "files": {"tests/test_big.py": 40.0, "tests/test_small.py": 2.0},
    "tests": {"tests/test_big.py::test_slow[a]": 10.0, "tests/test_big.py::test_slow[b]": 10.0},
}


def _ids() -> list[str]:
    big = ["tests/test_big.py::test_slow[a]", "tests/test_big.py::test_slow[b]"]
    big += [f"tests/test_big.py::test_other[{n}]" for n in range(10)]  # 20 s over 10 tests
    small = [f"tests/test_small.py::test_{n}" for n in range(4)]
    return big + small + ["tests/test_new.py::test_untimed"]


def test_a_test_with_a_weight_of_its_own_keeps_it_and_the_others_share_what_is_left() -> None:
    weights = _sharding.item_weights(_ids(), WEIGHTS)
    assert weights["tests/test_big.py::test_slow[a]"] == 10.0
    assert weights["tests/test_big.py::test_other[3]"] == 2.0  # (40 - 20) / 10
    assert weights["tests/test_small.py::test_1"] == 0.5  # 2 / 4


def test_a_test_in_a_file_nobody_has_timed_costs_the_default() -> None:
    assert _sharding.item_weights(_ids(), WEIGHTS)["tests/test_new.py::test_untimed"] == 0.5


def test_every_test_is_in_exactly_one_group() -> None:
    owner = _sharding.assign(_ids(), WEIGHTS, 3)
    assert sorted(owner) == sorted(_ids())
    assert set(owner.values()) == {0, 1, 2}


def test_the_groups_are_of_equal_cost_though_one_file_is_most_of_it() -> None:
    weights = _sharding.item_weights(_ids(), WEIGHTS)
    owner = _sharding.assign(_ids(), WEIGHTS, 2)
    loads = [sum(w for i, w in weights.items() if owner[i] == group) for group in (0, 1)]
    assert abs(loads[0] - loads[1]) <= 2.0, loads  # not 40 s against 3


def test_the_split_is_the_same_whatever_the_order_the_tests_are_collected_in() -> None:
    forward = _sharding.assign(_ids(), WEIGHTS, 4)
    backward = _sharding.assign(list(reversed(_ids())), WEIGHTS, 4)
    assert forward == backward


def test_the_weights_come_back_out_of_a_durations_report() -> None:
    report = "\n".join(
        [
            "12.00s call     tests/test_a.py::test_x[1]",
            " 1.00s setup    tests/test_a.py::test_x[1]",
            " 0.50s call     tests/test_a.py::test_y",
            " 2.00s call     tests/test_b.py::test_z",
            "(3 durations < 0.005s hidden.  Use -vv to show these durations.)",
            "3160 passed in 784.14s (0:13:04)",
        ]
    )
    weights = _sharding.record(report)
    assert weights["files"] == {"tests/test_a.py": 13.5, "tests/test_b.py": 2.0}
    assert weights["tests"] == {"tests/test_a.py::test_x[1]": 13.0}  # heavy ones by themselves
    assert weights["default"] > 0
