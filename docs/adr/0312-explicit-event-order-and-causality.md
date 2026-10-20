# 0312 - Explicit Event order and causal relationships

Status: accepted, decided with the maintainer on 2026-10-20. A narrow next slice of
[RFC 0028](../rfcs/0028-time-causality-and-calendars.md), building on ADR 0309.

## Decision

Existing Event entries gain two explicit directed relationship kinds: `order` (happened
before) and `causes`. Causes imply before; before alone never implies causation. Both kinds
participate in one acyclic order graph. A path consisting entirely of causes is a recorded
causal chain. A mixed path establishes order, not a new causal assertion. Parallel kinds on
one pair remain distinct assertions. They are authored setting/campaign assertions; character
belief, confidence and verdicts remain separate Information/RFC 0029 work.

Authored relationships are the source of truth. Dates, imports, wall time, entry creation order
and session/play order supply no implicit edges. Comparing an Event with itself returns same.
Other comparisons always return before or after, with a basis: `causal` for a causes-only
path, `ruled` for an ordering path involving an explicit order assertion, or `linearized` when
no recorded path decides it. Prefer a causal proof where one exists. Explanations identify the
actual directed path and relationship kinds; linearized explanations explicitly say there is
no recorded ordering path.

Order is a deterministic topological extension, using Event UUIDs to break unconstrained ties.
It is derived on demand in this slice, not a new persistent rank or independently editable
fact. The same graph and Event identities rebuild the same order. This accepts A2's
rebuildability principle without adopting Candidate A's stored numeric key or Candidate B's
ranked date evidence. A simple graph read/derivation is measured on a synthetic 200-session
fixture before introducing an incremental cache. Existing untimed workflows gain no graph
rows, locks or queries. Ordinary notes remain Information; Facts are not silently Events.

## Access and integrity

Only tenant Owners/Organizers using full Event visibility may read comparisons or relationships,
or author relationships. Existing administrative visibility opt-outs remain effective. Players,
restricted readers and Authors do not receive a comparison, order panel, path, counts or hints
about this graph in this slice. The reason is substantive: even refusing a cycle can reveal a
hidden ordering constraint. Reader-facing disclosure and independently restricted relationships
need their own design before extending access. This does not change ordinary Event identity,
Information, dates or grants.

`event_relationship` is tenant content with FORCE RLS and composite same-tenant foreign keys to
both StoryEvent markers. Database checks reject self-links, invalid kinds and cycles across
the union of relationship kinds. Graph writes take a per-tenant transaction advisory lock;
API writes acquire it before reading/checking versions. Conditional writes and endpoint row
locks prevent stale edits from silently replacing relationships. Duplicate assertions are
idempotent. Adding/removing assertions may change a derived linearization; that is never
reported as newly discovered causation and does not rewrite date associations or knowledge.

An Event referenced by ordering relationships cannot be deleted until those relationships are
explicitly removed. Whole-tenant deletion still works. This is not the later history-bearing
subject end/purge model. The relationship table is registered in copyable tables; copies and
release documents remap both endpoints and preserve kinds, reporting missing dependencies.
Existing copied-relation policy applies: copied assertions remain local and are not silently
synchronized on upstream updates. Derived positions are never copied as historical evidence;
unconstrained linearized ties can differ when copies receive new identities.

## First vertical slice

The API lists/adds/removes Event relationships and compares a bounded requested set of pairs,
with basis and proof paths. Lorenzo Calendars' existing Event page has an Order and causes
section, incoming/outgoing assertions, an Event picker and a comparison explanation. Existing
information, audience and date editors remain authoritative. Structured order is absent from
other entry kinds and from readers who do not meet the full-visibility administrative gate.

Tests cover pure/mixed/transitive paths, same and linearized comparisons, deterministic
rebuilds, date independence, a 200-session fixture, stale writes, self-links, mixed cycles,
two-connection races, raw database constraints, tenant isolation, administrative opt-outs,
copy/release round trips and deletion/purge, and real-API desktop/phone authoring. No causal
or historical claim is inferred from the calendar sample.

## Remaining open

This does not accept the rest of RFC 0028's baseline, either complete candidate, participation
identity or a native self-meeting model. Participations/lived order, clocks/rates/readings,
timeline branches, declared loops, timed knowledge, historical state, continuity/retcon reports
and player-facing causal disclosure remain separately decided slices. The first implementation
contains no default clock, timeline, learning event or historical change.
