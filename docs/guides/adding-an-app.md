# Adding an app

See [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md) for why this exists: `apps/` can hold any number of web frontends, mobile apps, or bots side by side — there's no fixed slot per type.

## Steps

1. **Name it by purpose, not type.** `apps/gm-console`, not `apps/web`. `apps/loot-bot`, not `apps/bot`. If you can't yet describe what makes this instance different from a hypothetical second one of the same type, that's a sign the scope isn't clear yet — confirm that before scaffolding.
2. **Confirm the language/framework and scope with the user first** — this repo is built structure-first; don't scaffold real code speculatively (see [AGENTS.md](../../AGENTS.md)).
3. **Give it a `mise.toml`** defining at minimum `dev`, `lint`, `test`, `build` tasks (whatever those mean in its language). This is the only contract shared tooling relies on:
   - `ci.yml`'s `discover` job finds it automatically via `apps/<name>/mise.toml` — no edit to `ci.yml` needed.
   - Add it to the root `mise.toml`'s `[monorepo].config_roots` so `mise run lint`/`test`/`dev` at the repo root reach it too.
4. **Register it in the relevant workspace** — `pnpm-workspace.yaml` (already includes `apps/*`, so JS/TS apps need no change) or a uv workspace (see [docs/guides/adding-a-package.md](adding-a-package.md) for when that's warranted).
5. **Add a `release-please-config.json` entry** so it gets independent versioning and a changelog.
6. **Add a Dependabot entry** in `.github/dependabot.yml` for its package ecosystem.
7. **If it's a deployed service**, add its own deploy workflow (e.g. `deploy-<name>.yml`) — don't generalize this into a shared one across apps that might deploy completely differently (a static site vs. a container vs. a mobile app store release).
8. **Add pre-commit hooks** for its language in `.pre-commit-config.yaml` if one doesn't already cover it.

## What this deliberately doesn't cover

Choosing the language/framework itself, and the app's actual domain logic — those are scoped case by case when the app is actually being built, not templated here.
