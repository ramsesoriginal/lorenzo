# 0318 - Explicit Session and play order

Status: accepted with the maintainer on 2026-10-21; RFC 0046 slice 3.

## Decision

Session order is explicitly authored within its campaign. Scene appearances have preparation
order, and recorded played order is independent of that mutable outline. A GM can review and
copy preparation into a played record; subsequent plan edits do not rewrite it. Appearance
status is planned, played or skipped. Events have ordered presentation occurrences within a
Scene appearance; an Event may be presented in several Scenes or Sessions. Direct Session
Event references are not play steps until placed explicitly. No play step is a new story Event.

Presentation order is never used as Event-order evidence, personal lived order, calendar time,
learning or proof of historical state. A late Session's flashback can present an early Event
without changing the Event graph. Neither created_at nor real-world dates define play order.
Partial/unrecorded play is preserved rather than completed with invented steps.

Assigned Session GMs author play records with version preconditions and atomic reorder writes.
Players read permitted played material; hidden appearances/Events do not produce placeholders,
global ranks, counts or pagination gaps. Records and attendance remain local on repository copy.

## Validation

Real-API/browser tests cover flashbacks, a continued Scene, repeated Event presentation,
plan/record independence, skipped Scenes, stale and concurrent reorder, independent target
visibility, tenant isolation and no inferred Event/learning/lived-order writes.
