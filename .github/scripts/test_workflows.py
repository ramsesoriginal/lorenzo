"""The workflows, as text (ADR 0148). Run: python3 -m unittest discover -s .github/scripts"""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"


def jobs(text: str) -> dict[str, str]:
    """Each job of a workflow file (the two-space keys under `jobs:`) with its text."""
    found: dict[str, list[str]] = {}
    current = None
    in_jobs = False
    for line in text.splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if in_jobs and re.match(r"^[a-z]", line):
            in_jobs = False
        match = re.match(r"^  ([a-zA-Z0-9_-]+):\s*$", line)
        if in_jobs and match:
            current = match.group(1)
            found[current] = []
        elif in_jobs and current:
            found[current].append(line)
    return {name: "\n".join(lines) for name, lines in found.items()}


class Timeouts(unittest.TestCase):
    """A job that hangs holds one of the twenty places an account has until GitHub's own limit of six
    hours, or the next push cancels it: a macOS build ran 953 s of the 100 it needs."""

    def test_every_job_says_how_long_it_may_take(self) -> None:
        missing = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in jobs(path.read_text(encoding="utf-8")).items():
                match = re.search(r"^    timeout-minutes: (\d+)\s*$", body, re.M)
                if match is None:
                    missing.append(f"{path.name}: {name}")
                elif not 1 <= int(match.group(1)) <= 60:
                    missing.append(f"{path.name}: {name} ({match.group(1)} minutes)")
        self.assertEqual(missing, [], "a job needs `timeout-minutes` of 1 to 60 under its `runs-on`")

    def test_the_jobs_are_found(self) -> None:
        self.assertIn("discover", jobs((WORKFLOWS / "ci.yml").read_text(encoding="utf-8")))
        self.assertIn("test", jobs((WORKFLOWS / "ci.yml").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
