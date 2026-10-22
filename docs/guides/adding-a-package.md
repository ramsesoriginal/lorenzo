# Adding a package

Generic code (anything not specific to one app's domain logic) doesn't go in an `apps/*/utils` grab-bag. It becomes its own small package under `packages/`, with its own README, tests, and version.

## Steps

1. Create `packages/<name>/` — a real Python package (`uv init --lib`) or npm package (`pnpm init`), whichever language fits.
2. Wire it to the apps that use it:
   - Python: there is no root `pyproject.toml` and no uv workspace. The package is its own uv project with its own lockfile, and each Python app that uses it declares it as a path source in its own `pyproject.toml`, for example `lorenzo-calendar = { path = "../../packages/calendar-engine" }` under `[tool.uv.sources]` in `apps/api/pyproject.toml` (see [ADR 0003](../adr/0003-polyglot-monorepo-tooling.md) for why a shared workspace was left out).
   - JS/TS: `pnpm-workspace.yaml` already includes `packages/*`, so nothing to add there. An app or package that uses it lists it as `"workspace:*"` in its `package.json`.
3. Add a `release-please-config.json` entry so it gets its own version/changelog.
4. Give it a `mise.toml` with its `lint` and `test` tasks (and `build` or `dev` where they apply); CI treats every directory under `packages/` with a `mise.toml` as a node. Then add the directory to `[monorepo].config_roots` in the root `mise.toml`. That list is written by hand, and a package missing from it is skipped by `mise run lint`, `test` and `check` at the repo root.
5. Add it to Dependabot in `.github/dependabot.yml`: an npm package goes in the `directories` list of the one `npm` entry (see [adding-an-app.md](adding-an-app.md) for why one entry), a Python one gets its own `uv` entry. Both keep the `<eco>-minor-patch` / `<eco>-major` groups.
6. **Tell CI who depends on it** ([ADR 0148](../adr/0148-dependency-aware-pr-ci.md), `.github/ci-graph.toml`): a change to a package runs every node that uses it, computed from the dependency graph. Nodes that list it in their `package.json` (`workspace:*`) or as a uv path source are found automatically, from their `mise.toml` and manifests. **Anything else is declared in `.github/ci-graph.toml`: a package in a language CI can't read as `[nodes."packages/<name>"]` (the `discover` job fails until it is), a consumer it can't see as `depends_on` on that consumer's entry, and a client generated from `apps/api`'s OpenAPI schema (a future `packages/python-api-client` or a Kotlin client) as `generated_from = ["apps/api"]` plus a `check-schema` task, so the drift check covers it.** `python3 -m unittest discover -s .github/scripts` checks the file.
7. Create its `pkg:<name>` label (`gh label create "pkg:<name>" --color <hex> --description "packages/<name>"`), add it to the scope table in [labels-milestones-and-metadata.md](labels-milestones-and-metadata.md), and put it on the PR that adds the package.

## When *not* to do this

If it's only ever going to be used by one app, it's not generic yet — leave it where it is until a second consumer actually shows up. Speculative reuse is how grab-bags get born in the first place.
