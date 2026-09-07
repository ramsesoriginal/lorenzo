# 0005 - Git branching and merge strategy

Status: accepted

## Context

Preference: commit early and often, work in multiple short-lived feature branches, and keep the branch topology visible in history permanently — it doubles as a visible development-history diagram.

## Decision

- Trunk-based: branch off `main` as `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`.
- Every change lands via a PR into `main`, even solo — it's the CI gate, not a review formality.
- PRs merge with a **real merge commit**. Squash and rebase merging are disabled at the repo level (`.github/rulesets/main.json`), so `git log --graph` keeps showing actual branch shape instead of a flattened line.
- Branches are **not** deleted on merge — history stays browsable by branch, not just by commit.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/), enforced by a commit-msg hook — this is what drives release-please's version bumps and changelogs.

## Consequences

- `main`'s history has real merge commits and surviving branch refs — expect `git log --graph --all` to look like an actual graph, not a line.
- Old branches accumulate. That's the point, but branch *names* need to stay meaningful (the slug is the only label once a branch is done); pruning genuinely stale ones later (tag, then delete) is an open question, not decided here.
- Solo-authored PRs need `required_approving_review_count: 0` in the ruleset (GitHub won't let you approve your own PR) — raise it once there's a second maintainer.
