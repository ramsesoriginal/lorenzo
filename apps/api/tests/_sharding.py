"""Splitting the suite over CI runners by what its tests cost (ADR 0148).

`TEST_SHARD=2/4` runs the second of four groups of tests. A test's weight is what it took to run, in
seconds of a worker, as recorded in `shard-weights.json`; the tests go heaviest first, each to the
group with the least so far, the same on every runner. A group is not a group of files: one file
(`test_kind_matrix.py`) is a quarter of the suite's time, and a count of tests per file, which this
used to split by, put it and little else on one runner (1,045 s against 414 s).

New weights come from a run that reports every duration:

    uv run pytest -n 4 --no-cov -q --durations=0 > durations.txt
    uv run python tests/_sharding.py durations.txt > tests/shard-weights.json

A test or a file with no weight yet costs the median of the others until it is recorded.
"""

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

WEIGHTS_FILE = Path(__file__).with_name("shard-weights.json")

# A test that costs this many seconds is recorded on its own; the others share their file's total.
HEAVY = 4.0

_DURATION = re.compile(r"^\s*([\d.]+)s (?:call|setup|teardown)\s+(\S.*?)\s*$")


def load_weights(path: Path = WEIGHTS_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def item_weights(nodeids: list[str], weights: dict[str, Any]) -> dict[str, float]:
    """The weight of each test: its own if it is recorded, else its file's remaining total spread
    over the file's other tests, else the default (a file nobody has timed)."""
    own: dict[str, float] = weights.get("tests", {})
    files: dict[str, float] = weights.get("files", {})
    default: float = weights.get("default", 0.3)

    by_file: dict[str, list[str]] = defaultdict(list)
    for nodeid in nodeids:
        by_file[nodeid.split("::")[0]].append(nodeid)

    result: dict[str, float] = {}
    for file, ids in by_file.items():
        recorded = [i for i in ids if i in own]
        rest = [i for i in ids if i not in own]
        for nodeid in recorded:
            result[nodeid] = own[nodeid]
        if not rest:
            continue
        if file in files:
            pool = max(files[file] - sum(own[i] for i in recorded), 0.0)
            per_test = pool / len(rest)
        else:
            per_test = default
        for nodeid in rest:
            result[nodeid] = max(per_test, 0.01)
    return result


def assign(nodeids: list[str], weights: dict[str, Any], total: int) -> dict[str, int]:
    """The group (0-based) of each test: heaviest first to the lightest group, ties by name."""
    by_weight = item_weights(nodeids, weights)
    loads = [0.0] * total
    owner: dict[str, int] = {}
    for nodeid in sorted(by_weight, key=lambda i: (-by_weight[i], i)):
        lightest = loads.index(min(loads))
        owner[nodeid] = lightest
        loads[lightest] += by_weight[nodeid]
    return owner


def record(durations: str) -> dict[str, Any]:
    """The weights file for the output of `pytest --durations=0`: what each test took (setup, call
    and teardown), the total of each file, and the median per test of the files as the default."""
    per_test: dict[str, float] = defaultdict(float)
    for line in durations.splitlines():
        match = _DURATION.match(line)
        if match and "::" in match.group(2):
            per_test[match.group(2)] += float(match.group(1))
    per_file: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for nodeid, seconds in per_test.items():
        file = nodeid.split("::")[0]
        per_file[file] += seconds
        count[file] += 1
    return {
        "comment": (
            "Seconds of a worker per test file, and per test for those of HEAVY seconds or more, "
            "from `pytest --durations=0` (tests/_sharding.py). `default`: the median per test of "
            "the files, for a test no one has timed."
        ),
        "default": round(statistics.median(per_file[f] / count[f] for f in per_file), 2),
        "files": {f: round(per_file[f], 1) for f in sorted(per_file)},
        "tests": {n: round(s, 1) for n, s in sorted(per_test.items()) if s >= HEAVY},
    }


if __name__ == "__main__":
    json.dump(record(Path(sys.argv[1]).read_text(encoding="utf-8")), sys.stdout, indent=1)
    sys.stdout.write("\n")
