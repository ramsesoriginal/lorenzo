# Adding a package

Generic code (anything not specific to one app's domain logic) doesn't go in an `apps/*/utils` grab-bag. It becomes its own small package under `packages/`, with its own README, tests, and version.

## Steps

1. Create `packages/<name>/` — a real Python package (`uv init --lib`) or npm package (`pnpm init`), whichever language fits.
2. Add it to the relevant workspace:
   - Python: create a root `pyproject.toml` with `[tool.uv.workspace]` (`members = ["packages/*"]`, plus any Python app that needs to depend on it) if one doesn't exist yet. Each Python app stays a standalone uv project with its own lockfile until it actually needs a workspace package — introducing the workspace before there's anything to share caused real rework once already (see [ADR 0003](../adr/0003-polyglot-monorepo-tooling.md)).
   - JS/TS: add `"packages/*"` to `pnpm-workspace.yaml`, if it isn't there yet.
3. Add a `release-please-config.json` entry so it gets its own version/changelog.
4. Add a `mise.toml` if it needs its own dev/test tasks, and list it in the root `mise.toml`'s `[monorepo].config_roots` (already there, alongside `apps/api`).
5. **Tell CI who depends on it** ([ADR 0148](../adr/0148-dependency-aware-pr-ci.md)): a change to a package runs every app that uses it, and that set is computed from the dependency graph. Apps that list it in their `package.json` (`workspace:*`) or as a uv path source are found automatically. **Anything else (another language, or a client generated from `apps/api`'s OpenAPI schema such as a future `packages/python-api-client` or a Kotlin client) is declared in `.github/ci-graph.yml`, and CI fails on a node in a language it can't read until it is.** A generated client also gets a `check-schema` task so the `client-drift` job picks it up.
6. Create its `pkg:<name>` label (`gh label create "pkg:<name>" --color <hex> --description "packages/<name>"`), add it to the scope table in [labels-milestones-and-metadata.md](labels-milestones-and-metadata.md), and put it on the PR that adds the package.

## When *not* to do this

If it's only ever going to be used by one app, it's not generic yet — leave it where it is until a second consumer actually shows up. Speculative reuse is how grab-bags get born in the first place.
