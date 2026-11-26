"""Which commit on main a push is compared with (ADR 0148). Run: python3 -m unittest discover -s .github/scripts"""

import unittest

import last_green


def run(sha: str, conclusion: str = "success", event: str = "push", branch: str = "main") -> dict:
    return {"head_sha": sha, "conclusion": conclusion, "event": event, "head_branch": branch}


class Pick(unittest.TestCase):
    def test_the_newest_green_run_is_the_baseline(self) -> None:
        self.assertEqual(last_green.pick([run("b"), run("a")], "c"), "b")

    def test_a_red_or_cancelled_run_is_never_one(self) -> None:
        runs = [run("c", "failure"), run("b", "cancelled"), run("a")]
        self.assertEqual(last_green.pick(runs, "d"), "a")

    def test_the_commit_itself_is_never_one(self) -> None:
        # a re-run of the run that is going on would compare the commit with itself
        self.assertEqual(last_green.pick([run("c"), run("b")], "c"), "b")

    def test_a_pull_requests_run_is_not_one(self) -> None:
        self.assertEqual(last_green.pick([run("p", event="pull_request"), run("a")], "c"), "a")

    def test_the_nightly_run_counts(self) -> None:
        self.assertEqual(last_green.pick([run("n", event="schedule"), run("a")], "c"), "n")

    def test_a_run_of_another_branch_is_not_one(self) -> None:
        self.assertEqual(last_green.pick([run("x", branch="feat/x"), run("a")], "c"), "a")

    def test_none_when_nothing_is_green(self) -> None:
        self.assertIsNone(last_green.pick([], "c"))
        self.assertIsNone(last_green.pick([run("a", "failure")], "c"))


if __name__ == "__main__":
    unittest.main()
