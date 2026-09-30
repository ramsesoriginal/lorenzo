# Adding a package

Generic code (anything not specific to one app's domain logic) doesn't go in an `apps/*/utils` grab-bag. It becomes its own small package under `packages/`, with its own README, tests, and version.

## Steps

1. Create `packages/<name>/` — a real Python package (`uv init --lib`) or npm package (`pnpm init`), whichever language fits.
2. Add it to the relevant workspace:
   - Python: create a root `pyproject.toml` with `[tool.uv.workspace]` (`members = ["packages/*"]`, plus any Python app that needs to depend on it) if one doesn't exist yet. Each Python app stays a standalone uv project with its own lockfile until it actually needs a workspace package — introducing the workspace before there's anything to share caused real rework once already (see [ADR 0003](../adr/0003-polyglot-monorepo-tooling.md)).
   - JS/TS: add `"packages/*"` to `pnpm-workspace.yaml`, if it isn't there yet.
3. Add a `release-please-config.json` entry so it gets its own version/changelog.
4. Add a `mise.toml` if it needs its own dev/test tasks, and list it in the root `mise.toml`'s `[monorepo].config_roots` (already there, alongside `apps/api`).
5. **Tell CI who depends on it** ([ADR 0148](../adr/0148-dependency-aware-pr-ci.md), `.github/ci-graph.toml`): a change to a package runs every node that uses it, computed from the dependency graph. Nodes that list it in their `package.json` (`workspace:*`) or as a uv path source are found automatically. **Anything else is declared in `.github/ci-graph.toml`: a package in a language CI can't read as `[nodes."packages/<name>"]` (the `discover` job fails until it is), a consumer it can't see as `depends_on` on that consumer's entry, and a client generated from `apps/api`'s OpenAPI schema (a future `packages/python-api-client` or a Kotlin client) as `generated_from = ["apps/api"]` plus a `check-schema` task, so the drift check covers it.** `python3 -m unittest discover -s .github/scripts` checks the file.
6. Create its `pkg:<name>` label (`gh label create "pkg:<name>" --color <hex> --description "packages/<name>"`), add it to the scope table in [labels-milestones-and-metadata.md](labels-milestones-and-metadata.md), and put it on the PR that adds the package.

## When *not* to do this

If it's only ever going to be used by one app, it's not generic yet — leave it where it is until a second consumer actually shows up. Speculative reuse is how grab-bags get born in the first place.
