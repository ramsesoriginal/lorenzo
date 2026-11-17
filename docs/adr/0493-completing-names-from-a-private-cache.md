# 0493 - Completing names from a private cache

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C12 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).

## Context

Tab completes commands and options, not library slugs or the names of systems, stats, templates and features. A completion that asks
the API on every Tab press waits for the network and a token; completion today already takes as long as `--version`.

## Decision

- **Completion reads a cache, never the API.** Library slugs, and per library the system slugs, stat group and stat names, template
  names, feature names and campaign names, are completed from a file under `$XDG_CACHE_HOME/lorenzo/`.
- **Kept current by the reads a person already makes.** Every command that lists or reads these rows writes them to the cache, and
  every write updates it; `lorenzo tenant list` refreshes the slugs. Nothing is fetched only to fill the cache.
- **Keyed and private.** One file per API address and account, readable only by the user, like `credentials.json`; a library's names
  sit under its id. `lorenzo logout` deletes the cache for that address and account.
- **Fast.** The completion path imports neither a command group nor the client ([ADR 0483](0483-the-clis-start-up-and-request-budget.md))
  and reads one small file.

## Consequences

- Tab completes what a person has seen, at once and offline; a row made elsewhere completes once something has listed it.
- The names of a library's private entries are stored on the user's machine, as readable as the token beside them.
