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

## As built (slice C12)

- The client tells an observer of every answered operation; `completion.Recorder` keeps the names of the lists, reads, creates,
  updates and deletes it knows (`list_systems`, `create_template`, `delete_stat_definition`...), and writes the file once, when
  the client closes, and only if something changed. A complete first page replaces a category; a filtered or partial one adds to it.
- Features are the entries of the kind `feature` among the entries a command reads (the library document's export, an entry read).
- The account is a JWT's issuer and subject, read without verifying it, or a digest of any other token; a token piped in with
  `--token-stdin` is not cached.
- Completing a name loads the command's group, since its parameter is where the completer sits: about 280 ms against about 100 ms
  for the root (`tests/test_startup.py` prints both). It reads the cache file only, and makes no request. Completing without
  loading the group would need stand-in parameters in the lazy registry, which is not built.
