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


def full(conclusion: str, created: str, event: str = "schedule", branch: str = "main") -> dict:
    return {"conclusion": conclusion, "created_at": created, "event": event, "head_branch": branch}


class FullRunRed(unittest.TestCase):
    def test_a_red_nightly_is_red(self) -> None:
        self.assertTrue(last_green.full_run_red([full("failure", "2026-11-26T01:41")]))

    def test_the_newest_finished_one_decides(self) -> None:
        runs = [full("failure", "2026-11-25T01:41"), full("success", "2026-11-26T01:41")]
        self.assertFalse(last_green.full_run_red(runs))
        self.assertTrue(last_green.full_run_red([*runs, full("failure", "2026-11-27T01:41")]))

    def test_a_green_manual_run_ends_it(self) -> None:
        runs = [full("failure", "2026-11-26T01:41"), full("success", "2026-11-26T09:00", "workflow_dispatch")]
        self.assertFalse(last_green.full_run_red(runs))

    def test_a_cancelled_or_unfinished_run_says_nothing(self) -> None:
        runs = [full("success", "2026-11-25T01:41"), full("cancelled", "2026-11-26T01:41"), full(None, "2026-11-27T01:41")]  # type: ignore[arg-type]
        self.assertFalse(last_green.full_run_red(runs))

    def test_no_run_yet_is_not_red(self) -> None:
        self.assertFalse(last_green.full_run_red([]))

    def test_a_run_of_another_branch_or_event_is_ignored(self) -> None:
        runs = [full("failure", "2026-11-26T01:41", branch="feat/x"), full("failure", "2026-11-26T02:00", "push")]
        self.assertFalse(last_green.full_run_red(runs))


if __name__ == "__main__":
    unittest.main()
