# Releasing

Fully automated by release-please ([ADR 0003](../adr/0003-polyglot-monorepo-tooling.md)) — this doc explains what the automation will do, in case it needs debugging. `apps/api` is registered in `release-please-config.json`, but the automation hasn't actually run yet — it only triggers on pushes to `main`, and this work is still on a feature branch. It'll start producing a release PR the first time `apps/api`'s commits land on `main`.

## The flow, once triggered

1. Commits land on `main` via merge commits (see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), each following Conventional Commits.
2. `release.yml` runs release-please on every push to `main`. It opens/updates a standing "release PR" per package that changed, with the version bump and changelog entry computed from commit messages since the last release.
3. Merging a release PR (still a merge commit) triggers release-please to tag that version and publish a GitHub Release for that package.

## Versioning

Each app/package is versioned independently (see `.release-please-manifest.json` / `release-please-config.json`) — one reaching `1.2.0` says nothing about another's version.

## What this doesn't do

Publish built artifacts anywhere (a container registry, PyPI, npm) or deploy anything — deployment is each app's own workflow, added when that app is scaffolded (see [docs/guides/adding-an-app.md](../guides/adding-an-app.md)).
