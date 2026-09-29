# apps/cli

The `lorenzo` command-line tool. Its first feature is the MPMB standard-item importer of [RFC 0025](../../docs/rfcs/0025-lorenzo-cli-mpmb-item-importer.md); the stack is recorded in [ADR 0137](../../docs/adr/0137-lorenzo-cli-app-python-client-and-auth.md).

Python 3.14, run and tested on Linux (WSL included). Native Windows is not a supported target.

## Run it

```bash
mise run //apps/cli:dev -- --help
```

or, from this directory, `uv run lorenzo --help`.

The tool needs an access token for `apps/api`. Until `lorenzo login` works against a registered Authgear client (see below), supply one directly:

```bash
export LORENZO_API_URL=http://localhost:8000
export LORENZO_TOKEN=...   # the token that `mise run //apps/api:dev-token` prints
uv run lorenzo tenant show <tenant-id-or-slug>
```

Or pipe a token in with `--token-stdin`. A token from the stored login is used last.

## Commands

| Command | What it does |
| --- | --- |
| `lorenzo tenant show <tenant>` | Reads one tenant (its `kind`, whether it is published) - the first call through the generated client |
| `lorenzo login` / `lorenzo login --no-browser` / `lorenzo logout` | Stores or forgets a login (needs the Authgear client, see below) |
| `lorenzo inspect [--base FILE...] FILE...` | Shows what the JavaScript host reads from MPMB files (files, per-list counts and which file each entry came from, stubbed sheet names), without touching a tenant. Needs no login |
| `lorenzo seed --tenant <tenant>` | Creates the item taxonomy, stat groups and definitions, and the weight recipe an import needs, in a repository tenant. Safe to run again; `--dry-run` first |

`plan` and `apply` arrive with the later slices of RFC 0025.

## Seeding a tenant

An import needs somewhere to put things: item prototypes to descend from (weapon, container, martial...) and the stat definitions the values are written to. `lorenzo seed` creates them once ([ADR 0143](../../docs/adr/0143-lorenzo-seed-taxonomy-and-stats.md)):

```bash
uv run lorenzo seed --tenant my-repository --dry-run   # what would be created (exit 2 if anything)
uv run lorenzo seed --tenant my-repository --yes       # create it
```

It writes to an existing `repository` tenant. A `play` tenant is refused, because a tenant's kind can't be changed and nothing in it could ever be published; `--allow-play-tenant` writes there anyway. The seed is in `src/lorenzo_cli/seed/builtin.toml`, tagged by layer (`core`, and `dnd5e` for D&D 5e's categories and dice, chosen with `--layer`). Stat names and types can't be changed once a tenant has them, so read that file before the first run against a tenant that matters.

## Reading MPMB files

MPMB's additional-content files are executable JavaScript, so they are evaluated, not parsed ([ADR 0138](../../docs/adr/0138-lorenzo-cli-js-host.md)). `lorenzo_cli.evalworker` runs an embedded V8 (`mini-racer`) in a subprocess that is given no credentials and is killed on a timeout, and returns plain JSON in which a `RegExp` is `{"$re": [source, flags]}` and a function is `{"$fn": text}` (never called).

Homebrew is written against lists that already hold the sheet's SRD data, and some files patch it, so pass the sheet's own files first as `--base`:

```bash
git clone https://github.com/morepurplemorebetter/MPMBs-Character-Record-Sheet /tmp/mpmb
uv run lorenzo inspect \
  --base /tmp/mpmb/_variables/ListsSources.js --base /tmp/mpmb/_variables/Lists.js \
  --base /tmp/mpmb/_variables/ListsGear.js my-homebrew.js
```

The sheet's data is GPL-3.0 and is not shipped with Lorenzo. `tests/corpus/` holds the golden fixtures every engine must reproduce; `LORENZO_UPSTREAM_CORPUS=/tmp/mpmb uv run pytest tests/test_evalworker_upstream.py` runs the worker against the real thing.

## The API client

`src/lorenzo_cli/client/models.py` is generated from `apps/api`'s OpenAPI document and committed. After changing `apps/api`'s routes or schemas:

```bash
mise run //apps/cli:generate-schema
```

CI's `client-drift` job runs `check-schema`, which fails on any difference. `src/lorenzo_cli/client/ops.py` lists the operations the CLI calls; a test checks each against the dumped schema.

## Login needs an Authgear client

`login` uses the authorization code flow with PKCE against a public Authgear client on a fixed loopback port. That client has to be registered on the Authgear project first (an operations step, see [docs/operations](../../docs/operations/local-authgear-setup.md)). Until then `login` says so and exits; tokens through `LORENZO_TOKEN` or `--token-stdin` work regardless.

Environment: `LORENZO_API_URL` (the API base URL), `LORENZO_TOKEN`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`.

## Tests

`mise run test` runs everything. `tests/e2e/` starts the real `apps/api` on a fresh database behind a fake Authgear and runs the CLI against it; it needs Postgres (`docker compose -f infra/docker-compose.yml up -d`, or CI's service) and skips without it. `LORENZO_REQUIRE_E2E=1` makes a missing stack a failure instead, as CI does.
