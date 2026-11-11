# 0055 - A vocabulary check: what a library's stats get wrong without saying so

Status: proposed (2026-11-11), Decision open on the questions at the end. It reads what
[RFC 0016](0016-stats-computed-values-and-crud-api.md), [ADR 0037](../adr/0037-effective-stat-resolution.md),
[ADR 0266](../adr/0266-stat-tie-break-by-parent-order.md), [ADR 0279](../adr/0279-stat-hints.md) and
[ADR 0403](../adr/0403-stat-scales.md) already decided and changes none of it.

## Purpose

Tell an author, through the API, where a library's stats give a surprising number or none, without anything being refused or
changed. The resolution rules are decided and stay; what is missing is a way to see their consequences.

## Decided inputs

1. **A read, not a gate.** Nothing is refused, written or recorded by the check.
2. **Data model and API only.** No app, frontend or command-line change is part of this RFC; a lint or a pane is their own
   work, and reads this.
3. **Every finding is something tested** against the API (2026-11-10), not a style rule.

## What goes wrong today (tried against the API)

- **An unset input leaves the result unset.** A `sum` with one term that has no value has no value, the stat is absent from
  the entry read and its explanation is not found.
- **A default and a trait at one distance tie.** A default on a base prototype and a race stat at the same hop from a being:
  parent order decided, and a being silently lost a +2. The fix, acquiring a higher-priority group, is easy to forget.
- **An own value shadows a formula.** A value written on an entry that has a formula only on a prototype is stored and wins;
  nothing says a formula was passed over, and a relationship type's formula was shadowed even by a bulk write.
- **A computed value is outside its scale.** A net standing of 250 showed against a scale of -100 to 100, as designed.
- **A value is beyond its hint.** A current value of 500 against a maximum of 120 was accepted, as designed.
- **A chain is long.** Reads fail beyond about 520 formulas (fixed separately).

## Hard invariants

- **Read-only.** No write, no activity entry, no stored finding.
- **Resolution does not change.** The check reports what the rules in ADR 0037 and 0266 already did.
- **A reader sees what the reader may read.** An entry the caller cannot read is not scanned or named; a finding reads the
  entry's stats by the rules the entity read uses.
- **Tenant isolation is by RLS** (ADR 0002). There is no new table.

## Design (proposed)

### 1. One route

`GET /tenants/{t}/vocabulary-check`, at the vocabulary's tier (any member), takes:

| Parameter | Meaning |
| --- | --- |
| `code` (repeatable) | only these findings; default all |
| `entry_id`, or `parent_id` with `recursive` | only this entry, or the entries under it |
| `kind` | only entries with this kind |
| `stat_definition_id` | only this stat |
| `page`, `size` | pages of entries scanned, `size` at most 100 |

It answers a page of findings: `{items: [{code, severity, entry_id, stat_definition_id, message, details}], total, page,
size, pages}`. `severity` is `warning` or `info`. A repository is a tenant, so the same route checks a repository.

### 2. The findings

Entry-level, per entry and stat, from the same loading as the bulk effective-stat read
([ADR 0387](../adr/0387-the-bulk-effective-stat-read.md)):

| Code | Says | `details` |
| --- | --- | --- |
| `unset-input` | a computed stat has no value because an input has none | the formula's entry, its kind, the inputs without a value |
| `own-value-shadows-formula` | the entry's own value wins over a formula an ancestor holds | the own value, the formula's entry |
| `tie` | two or more candidates for a stat sit at the same distance, and a rule broke the tie | the winner, the others, and the reason: group priority, parent order or id |
| `computed-outside-scale` | a computed value is outside the stat's minimum or maximum | the value, the bounds |
| `above-hint` | a value is above its maximum hint or below its minimum hint | the value, the hinted stat and its value |

Vocabulary-level, with no entries:

| Code | Says | `details` |
| --- | --- | --- |
| `formula-chain-depth` | a formula's chain of formulas below it is longer than 50 | the length and the stat |

A finding names the stats and entries by id; the message is a sentence in the problem style the API already uses.

### 3. Cost

The check is for authors, not a hot path. It scans a page of entries by the bulk read's path, with no query per entry, and
the slice carries a statement-count test ([ADR 0285](../adr/0285-api-reads-that-cost-what-they-read.md)). `tie` needs the
candidates a stat had, which the effective-stat view does not return today; the slice that adds it states how it reads
them (a variant of the view's walk) and measures it before it is exposed.

## Compatibility

A pure addition: one route, no new table, no change to any existing request or response.

## Delivery

Each slice is its own ADR.

1. **V1.** The route, paging and filters; `computed-outside-scale`, `above-hint` and `formula-chain-depth`.
2. **V2.** `unset-input` and `own-value-shadows-formula`.
3. **V3.** `tie`.

## Not in scope

- A lint, a pane or any drawing of findings, and a command-line check: the apps' and the CLI's own work.
- Refusing a write because of a finding, a warning in the response of a write, a stored or scheduled check, and automatic
  fixes.
- Findings about style, naming or unused stats.

## Open questions

1. **Warnings on writes.** A `PUT` of a stat or a formula could answer with the findings for the stat it wrote
   (`warnings`), without refusing: left out here (proposal), or added in a slice of its own.
2. **`tie` cost.** If reading every candidate cannot be made cheap, `tie` is limited to one entry or one parent subtree per
   request (proposal), rather than a page of entries.
3. **Severity.** `warning` for `unset-input`, `own-value-shadows-formula` and `tie`; `info` for the other three
   (proposal).

## Alternatives considered

- **Refuse at write time.** An unset input and a shadowing value are legitimate while an author is part-way through; refusing
  would stop the work and change the API.
- **A stored report.** It would be stale at once, and needs a table and a trigger for every stat write.
- **Only a command-line lint.** It would have to rebuild the resolution in another language; the API already has it.

## Consequences

- An author, an app or a lint can ask "what is wrong here" and get the answer from the code that resolves the stats.
- One route to keep in step with the resolution rules whenever they change.
- Findings that the rules produce on purpose (a computed value outside a scale, a value above a hint) are `info`, so they do
  not read as errors.
