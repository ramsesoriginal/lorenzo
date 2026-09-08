# Releasing

Fully automated by release-please ([ADR 0003](../adr/0003-polyglot-monorepo-tooling.md)) — this doc explains what the automation does, in case it needs debugging. `apps/api` is registered in `release-please-config.json` and has tagged real releases (starting `api-v0.2.0`) since its commits first landed on `main`.

## The flow

1. Commits land on `main` via merge commits (see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), each following Conventional Commits.
2. `release.yml` runs release-please on every push to `main`. It opens/updates a standing "release PR" per package that changed, with the version bump and changelog entry computed from commit messages since the last release.
3. Merging a release PR (still a merge commit) triggers release-please to tag that version and publish a GitHub Release for that package.

You don't have to merge a release PR right away — it just keeps accumulating commits until you do, so it's fine to batch several fixes into one version bump.

## Versioning

Each app/package is versioned independently (see `.release-please-manifest.json` / `release-please-config.json`) — one reaching `1.2.0` says nothing about another's version.

## What this doesn't do

Publish built artifacts anywhere (a container registry, PyPI, npm). It also doesn't deploy anything itself — `apps/api`'s own `deploy-api.yml` triggers independently, on any push touching `apps/api/**`, regardless of whether that push came from a release-please merge or anything else (see [docs/operations/deployment-setup.md](deployment-setup.md)).

## Known rough edges

- **"GitHub Actions is not permitted to create or approve pull requests"** — a one-time repo setting, not a bug; see [docs/operations/github-setup.md](github-setup.md).
- **A run occasionally fails with `state cannot be changed. There is already an open pull request from ... to main.`** — a confirmed, currently-open upstream bug ([googleapis/release-please#2566](https://github.com/googleapis/release-please/issues/2566)), not something wrong in this repo. No data is lost when it happens; re-running the workflow (Actions → Release → Run workflow) produces a clean release PR.
- **Merging a release PR can leave `apps/api/uv.lock` stale** — release-please only bumps `pyproject.toml`'s version, not the lockfile, which separately records the local project's own version. `apps/api/mise.toml`'s `lint` task runs `uv lock --check` specifically to catch this before merge now, so it should surface as a normal CI failure on the release PR rather than a deploy-time surprise.
