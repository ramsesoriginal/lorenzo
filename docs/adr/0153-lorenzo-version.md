# 0153 - `lorenzo --version`

Status: accepted

Follow-up to [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md). The first of a set of small CLI additions decided together on 2026-10-03: [ADR 0154](0154-lorenzo-tenant-list.md) to [0161](0161-lorenzo-api-passthrough.md).

## Context

The CLI installs from this repository (`uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"`), and its generated client is tied to one version of `apps/api`'s schema ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)). When a command misbehaves, the first question is which CLI is running, and today nothing answers it. `lorenzo --help` doesn't say, and the version in `pyproject.toml` is only visible to someone with a checkout.

## Decision

`lorenzo --version` prints `lorenzo <version>` on one line and exits 0.

- **The version is the installed package's own**, read from its metadata (`importlib.metadata.version("lorenzo-cli")`), so there is no second copy to keep in step. release-please already bumps `pyproject.toml` ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).
- **It is an eager option on the top-level command.** It is answered before any other option is read, so it needs no API URL, no login, and no network.
- **There is no `-V` and no `version` subcommand.** One spelling, the one every other command line uses.

## Not in scope

- **Asking the API for its version** and warning when the two have drifted apart. `FastAPI`'s own version is in the OpenAPI document, so this is possible later, but it is a check on every run or a command of its own, and neither has been asked for.
- **A commit hash.** An install from `main` between releases reports the last released version. Pinning to a tag (`@cli-v0.1.0`) is how to know exactly what was installed.

## Consequences

- A bug report can say which version it is about.
- Until release-please's first release of `apps/cli`, the answer is `0.0.0`.
