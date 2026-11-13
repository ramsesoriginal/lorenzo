# 0458 - The vocabulary check: the route and its first findings

Status: accepted, built (2026-11-12). Slice V1 of [RFC 0055](../rfcs/0055-vocabulary-check.md). Reads what
[ADR 0037](0037-effective-stat-resolution.md), [ADR 0279](0279-stat-hints.md), [ADR 0403](0403-stat-scales.md) and
[ADR 0443](0443-the-api-answers-what-it-used-to-ignore-crash-on-or-return-out-of-order.md) decided and changes none of it.

## Context

The resolution rules are decided and stay, but nothing says where their consequences surprise an author: a computed value beyond its
scale, a value beyond the stat it is hinted against, a chain of formulas too long to follow. This slice adds the one read that says so.

## Decision

- **One route, `GET /tenants/{t}/vocabulary-check`,** at the vocabulary's tier (any member reads it). It writes, records and refuses
  nothing, and there is no new table. A repository is a tenant, so the same route checks a repository.
- **Parameters.** `code` (repeatable; the findings built so far), `entry_id` (one entry, 404 if the caller cannot read it) or
  `parent_id` with `recursive`, `kind`, `stat_definition_id` (404 for one that is not the library's), and `page` and `size` (at most
  100). The entries and their order are those of `GET /entities` with the same filters.
- **The answer is a page of findings** `{items, total, page, size, pages}`: `items` are the findings of a page of the entries scanned,
  `total` and `pages` count entries. A finding is `{code, severity, entry_id, stat_definition_id, message, details}`; `message` is a
  sentence, `details` the numbers and ids behind it. An entry the caller cannot read is not scanned or named.
- **Findings built here.**
  - `computed-outside-scale` (`info`): a stat whose value is computed (a formula decides it) is below its minimum or above its maximum
    ([ADR 0403](0403-stat-scales.md): bounds check what is written, never what is computed). `details`: `value`, `minimum`, `maximum`.
  - `above-hint` (`info`): a numeric value above the value of its maximum hint, or below that of its minimum hint, both read on the same
    entry as the entry read gives them ([ADR 0279](0279-stat-hints.md): hints are clues, not limits). A hinted stat with no value says
    nothing. `details`: `value`, `hint` (`maximum` or `minimum`), `hinted_stat_definition_id`, `hinted_value`.
  - `formula-chain-depth` (`info`): a stat with more than 50 formulas below it in the longest chain of the definition-level graph, one
    finding for the top of each chain. It is about the library and no entry (`entry_id` is null): it comes on the first page, and only
    when no entry, parent or kind is asked for. `details`: `length`.
- **Severity.** `info` is what the rules produce on purpose; `warning` is what an author most likely did not mean (the later findings).
- **Cost.** A page of entries is read as the bulk read reads it (one pass for every entry of the page, `load_effective_rows`,
  shared with it), with no query for each entry; the definition-level graph is one query. A test says the statements of a scan do not
  grow with the entries.

## Design

`vocabulary_check.py` holds the findings (`scan_entries`, `vocabulary_findings`), `routers/vocabulary_check.py` the route. The bulk
read's loading moves to `effective_stats.load_effective_rows` and the chain walk of `stat_evaluation` to `formula_chains_below`, both
unchanged in what they do.

## Validation and delivery

A test for each: a computed value outside its scale (and a stored one not reported); a value above a maximum hint and below a minimum
one, and a hint with no value; a chain of 60 formulas as one finding and 40 as none, and no repeat on a filter or a later page; each
filter; the paging, counting entries; a reader's view; and that a scan does not cost more statements for more entries. The OpenAPI change
is the route and its schemas; the CLI models and `packages/api-client` are regenerated.

## Not in scope

`unset-input`, `own-value-shadows-formula` (V2), `tie` (V3), warnings on writes (V4); any lint, pane or command-line check.

## Consequences

- An author, an app or a lint can ask what is odd about a library and get the answer from the code that resolves the stats.
- One more route to keep in step with the resolution rules.
