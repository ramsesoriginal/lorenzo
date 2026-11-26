#!/usr/bin/env python3
"""The commit on main that CI last passed on, to compare a push to main with (ADR 0148).

    last_green.py --repo OWNER/NAME --sha HEAD_SHA

Prints the commit, or nothing when there is none to trust (the caller then runs everything): none
found, or the last nightly run is red.

A push to main runs what changed since that commit, not since the push before it: when the push
before it was red, what it broke is still part of the difference, and so is tested again until it
is green. Cancelled and failed runs are never a baseline; a run on the same commit is not one
either (a re-run of it would compare the commit with itself and test nothing).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# The events that run the whole suite or what changed since a green one: a pull request's run is of
# a merge commit that is not on main.
EVENTS = ("push", "schedule", "workflow_dispatch")


def pick(runs: list[dict], sha: str) -> str | None:
    """`runs` newest first, as GitHub lists them."""
    for run in runs:
        if run.get("conclusion") != "success" or run.get("event") not in EVENTS:
            continue
        if run.get("head_branch") != "main" or run.get("head_sha") in (None, "", sha):
            continue
        return run["head_sha"]
    return None


def full_run_red(runs: list[dict]) -> bool:
    """Is the last finished run of the whole suite (the nightly, or one started by hand) red?

    While it is, a push runs everything: the night found something that no change of the day explains,
    and a push that compared only with the last green commit would not look at it again. A green
    nightly (or a green manual run) ends it. A run still going, or cancelled, says nothing."""
    finished = [
        run for run in runs
        if run.get("head_branch") == "main"
        and run.get("event") in ("schedule", "workflow_dispatch")
        and run.get("conclusion") in ("success", "failure", "timed_out")
    ]
    if not finished:
        return False
    return max(finished, key=lambda run: run.get("created_at", ""))["conclusion"] != "success"


def runs_of(repo: str, *params: str) -> list[dict]:
    proc = subprocess.run(
        ["gh", "api", "--method", "GET", f"repos/{repo}/actions/workflows/ci.yml/runs", "-f", "branch=main", *params],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return []
    return json.loads(proc.stdout).get("workflow_runs", [])


def fetch(repo: str) -> list[dict]:
    return runs_of(repo, "-f", "status=success", "-f", "per_page=50")


def fetch_full_runs(repo: str) -> list[dict]:
    return [
        run
        for event in ("schedule", "workflow_dispatch")
        for run in runs_of(repo, "-f", f"event={event}", "-f", "status=completed", "-f", "per_page=5")
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    if full_run_red(fetch_full_runs(args.repo)):
        print("The last nightly (or manual full) run is red: everything runs.", file=sys.stderr)
        return 0
    found = pick(fetch(args.repo), args.sha)
    if found:
        print(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
