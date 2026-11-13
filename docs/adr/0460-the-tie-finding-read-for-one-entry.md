# 0460 - The `tie` finding, read for one entry

Status: accepted, built (2026-11-12). Slice V3 of [RFC 0055](../rfcs/0055-vocabulary-check.md). Builds on
[ADR 0458](0458-the-vocabulary-check-route-and-its-first-findings.md) (the route),
[ADR 0037](0037-effective-stat-resolution.md) and [ADR 0266](0266-stat-tie-break-by-parent-order.md) (what decides which ancestor's
stat an entry gets). Resolution does not change.

## Context

Two ancestors of one entry at the same distance, both setting a stat, are decided by a rule, silently: a being lost a +2 because a
default and a race trait sat at one hop and the parent order put the default first. The effective-stat view returns the winner only, so
the candidates were not readable.

## Decision

- **`tie`** (`warning`): a stat that two or more entries on the entry's prototype walk set at the same distance, with the same kind
  (both a stored value, or both a formula), so that a rule had to choose among them. A stored value against a formula at one distance
  is a rule of its own (the value first) and is not reported; neither is a nearer entry beating a further one, or an own value.
- **`details`**: `winner` and `others`, each `{entry_id, distance, computed}` (`entry_id` null with `hidden` true for an entry the caller
  may not see, ADR 0437), and `reason`, why the winner beat the next candidate: `group priority` (its holder has acquired a group of
  higher priority), `parent order` (the places taken from the entry down, ADR 0266) or `id` (all equal, the last resort).
- **One entry per request.** `tie` is read only with `entry_id`: it is in the default set then, and left out of it without one, and a
  `code` that names it without `entry_id` is a 422 (`vocabulary-check-entry-required`). `stat_definition_id` narrows it.
- **How the candidates are read.** The view's walk is repeated for the one entry (an ancestor reached by two ways counts once, by the
  first way the view's order finds: fewest hops, then the places), with the rows of `entity_stat` and `computed_stat` of every ancestor
  and the highest group priority of each, ordered as the view orders them. That is four statements for the entry however many stats
  it has, and the finding is never made for a page of entries, which is why it is not.
- Nothing is refused, written or stored.

## Design

`tie_findings` in `vocabulary_check.py`: a recursive walk with the stored places, the priorities, the two candidate tables, then a
sort by `(hops, formula, -priority, places, id)` as the view does; a stat is tied when its first candidates agree on distance and kind.
A test holds the order of the view and the finding together: swapping the parents flips the winner it names.

## Validation and delivery

A test for each: two parents at one distance (the parent order, the winner and the others, swapping the parents), a group priority that
decided, a parent against a grandparent and an own value (no tie), the 422 without an entry and the default set, a stat narrowing it,
and the statements not growing with the stats. The OpenAPI change is `tie` among the codes; the CLI models and `packages/api-client` are
regenerated.

## Not in scope

A tie for a page of entries; a tie among reasons of the `id` kind beyond naming it; warnings on writes (V4).

## Consequences

- "Why did I get that number?" has an answer when the answer is a rule that picked one of several: the winner, the others and why.
- The view's order is stated twice (in SQL and here); the test that swaps the parents is what keeps them in step.
