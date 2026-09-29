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
export LORENZO_TOKEN=$(cd ../api && uv run python scripts/get_dev_token.py | tail -n +3 | head -n 1)
uv run lorenzo tenant show <tenant-id-or-slug>
```

Or pipe a token in with `--token-stdin`. A token from the stored login is used last.

## Commands

| Command | What it does |
| --- | --- |
| `lorenzo tenant show <tenant>` | Reads one tenant (its `kind`, whether it is published) - the first call through the generated client |
| `lorenzo login` / `lorenzo login --no-browser` / `lorenzo logout` | Stores or forgets a login (needs the Authgear client, see below) |

`seed`, `plan` and `apply` arrive with the later slices of RFC 0025.

## The API client

`src/lorenzo_cli/client/models.py` is generated from `apps/api`'s OpenAPI document and committed. After changing `apps/api`'s routes or schemas:

```bash
mise run //apps/cli:generate-schema
```

CI's `client-drift` job runs `check-schema`, which fails on any difference. `src/lorenzo_cli/client/ops.py` lists the operations the CLI calls; a test checks each against the dumped schema.

## Login needs an Authgear client

`login` uses the authorization code flow with PKCE against a public Authgear client on a fixed loopback port. That client has to be registered on the Authgear project first (an operations step, see [docs/operations](../../docs/operations/local-authgear-setup.md)). Until then `login` says so and exits; tokens through `LORENZO_TOKEN` or `--token-stdin` work regardless.

Environment: `LORENZO_API_URL` (the API base URL), `LORENZO_TOKEN`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`.
