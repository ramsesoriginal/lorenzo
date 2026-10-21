# 0319 - Personal lived order as Event evidence

Status: accepted with the maintainer on 2026-10-21; RFC 0046 slice 4.

## Decision

A lived-before assertion relates two existing Event participations of the same being.
It records that the being experienced the earlier Event before the later one. This is
explicit author-declared evidence and constrains the shared Event graph, but implies no
causation. The being and both participations remain its provenance. Positions and timestamps
are not foreign-key targets and cannot redefine participation identity.

Lived assertions are separate from ordinary order rulings and causal assertions. Several
beings may support one Event ordering; deleting one support never removes another or an
independent ruling. The union is cycle-checked using the existing per-tenant graph lock and
DB integrity guarantees, including raw SQL and concurrent writers. Conflicts require correction;
no acknowledgement permits a cycle. No backfill comes from dates or play/Scene/roster order.

Use current Event-order manager restrictions for editing, and require access to the being.
Lived evidence is private until explicitly shared; reader derivation filters unauthorized
assertions before order/path/count computations. Proofs cannot disclose a hidden being or
private source. Full Event management never grants unrelated private Being Information.
Comparisons retain basis distinctions: lived evidence is order evidence, not a causes-only
proof. Unplaced participations remain unplaced; a linearized display is never recorded life.

The Sessions app provides explicit lived-order editing and an optional reviewed proposal from
played Events; saving must name the selected being and participations. Existing Event/Being
views link to permitted records. No learning grant/history, ageing or clock is inferred.
Repeated presentation of an Event is supported by ADR 0318; a being participating in the same
Event twice remains a separate future decision. Causal loops and branching remain excluded.

Lived assertions are authored content: repository copy/release remaps the being and both
Event participations, preserves independent support, reports missing dependencies and does
not silently synchronize local ordering on upstream updates. New tenant tables force RLS,
use composite same-tenant participation keys and join the registry. Dependent assertions
block direct participation deletion; tenant purge explicitly removes dependencies safely.

## Validation

Test causal/order/lived mixed cycles, raw writes and two-connection races, explicit source
provenance, independently removable support, hidden beings and assertions, reader graph
noninterference, stale edits, copy/release compatibility, participation deletion/purge, and
an end-to-end flashback whose presentation and lived order differ without contradiction.
