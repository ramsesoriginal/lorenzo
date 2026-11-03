# Releasing

Fully automated by release-please ([ADR 0003](../adr/0003-polyglot-monorepo-tooling.md)) — this doc explains what the automation does, in case it needs debugging. Every app and package is a release-please component: it is declared in [`release-please-config.json`](../../release-please-config.json), and [`.release-please-manifest.json`](../../.release-please-manifest.json) holds its current version, several still at `0.0.0`. A `CHANGELOG.md` exists only where release-please has generated one, besides the hand-curated root file. Each component is tagged separately (`git tag` lists them).

## The flow

1. Commits land on `main` via merge commits (see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), each following Conventional Commits.
2. `release.yml` runs release-please on every push to `main`. It opens/updates a standing manifest release PR covering the packages that changed, with the version bump and changelog entry computed from commit messages since the last release.
3. Merging a release PR (still a merge commit) triggers release-please to tag that version and publish a GitHub Release for that package.

You don't have to merge a release PR right away — it just keeps accumulating commits until you do, so it's fine to batch several fixes into one version bump.

## Versioning

Each registered app/package is versioned independently (see `.release-please-manifest.json` / `release-please-config.json`) — one reaching `1.2.0` says nothing about another's version.

## What this doesn't do

Publish built artifacts anywhere (a container registry, PyPI, npm). It also doesn't deploy anything itself — `apps/api`'s own `deploy-api.yml` triggers independently, on any push touching `apps/api/**`, `packages/calendar-engine/**` or `packages/map-engine/**`, regardless of whether that push came from a release-please merge or anything else (see [docs/operations/deployment-setup.md](deployment-setup.md)).

## Known rough edges

- **"GitHub Actions is not permitted to create or approve pull requests"** — a one-time repo setting, not a bug; see [docs/operations/github-setup.md](github-setup.md).
- **A run occasionally fails with `state cannot be changed. There is already an open pull request from ... to main.`** — a previously observed upstream bug ([googleapis/release-please#2566](https://github.com/googleapis/release-please/issues/2566)), not something wrong in this repo. No data is lost when it happens; re-running the workflow (Actions → Release → Run workflow) produces a clean release PR.
- **Python lockfile synchronization** — release-please bumps `pyproject.toml` but does not itself update the local project version in `uv.lock`. `release.yml` now has a `sync-lockfile` job that runs `uv lock` for `apps/api`, `apps/cli`, `packages/calendar-engine`, `packages/converters` and `packages/map-engine` and commits any fixes to the release branch. It uses `RELEASE_PLEASE_PUSH_TOKEN` ([how to create it](github-setup.md#release-workflow-push-token)) so the fix-up push starts CI; `uv lock --check` remains the lint guard if synchronization fails.
