# 0321 - Constant clock ratios and reader-scoped conversion

Status: accepted, agreed with the maintainer on 2026-10-22. Second clock slice of RFC 0028,
building on ADR 0320. This accepts only the scope below, not the old amendment wholesale.

## Decision

A dedicated relationship joins two distinct ticking Clock entries with one exact nonzero signed
ratio, optionally pairing exact anchor readings. The ratio is clock units per reference-clock
unit. A ratio alone converts durations; absolute conversion also needs an anchor. Reverse
conversion is implied; one relationship per unordered pair avoids contradictory duplicates.
Negative ratios express opposite reading directions without consulting causal or lived order.

Relationships start private, sharing requires visible endpoints, and authoring uses ADR 0320's
structured-clock capability. Derived Event readings are calculated on demand from permitted
entered readings, reckonings and relationships. They never become entered data. No traveller,
Session, participation, date association, created_at or updated_at supplies an inferred anchor.

Use exact bounded rational affine conversion, preserving interval inclusion and reversing bounds
for negative ratios. Chains compose, including inverse relationships. Consistent cycles are
valid clock-coordinate statements, not causal loops. Disagreeing permitted paths yield an explicit
conflict, never an arbitrary path. An entered target reading remains primary; disagreeing derived
values are shown as a conflict without rejecting or rewriting recorded evidence. Overlapping
ranges are compatible. No route silently picks a nearest sync point or interpolates dates.

Filter private sources before graph traversal, consistency checks, provenance, counts, response
versions or caching. Hidden data must not affect a reader's answer or error. Return Entered,
Derived, Not reckoned, Conflicting or Limit reached with permitted source provenance. Graph
size, traversal, batch size and rational growth are bounded; exhausted work is not unknown time.
Changes use required If-Match and a per-tenant clock mutation lock for deterministic concurrent
saves. Version details on reader responses contain no private graph revision.

Lorenzo Calendars adds ratio/anchor editing and conversion previews, plus Event reading displays.
Use the existing bounded account/library-scoped cache, invalidate on writes, and retain no private
bodies in durable browser storage. Every relationship participates in RLS, same-tenant FKs,
copy/update/release, dependency-safe deletion and tenant purge in the same vertical PR.

## Validation and delivery

Stack the second API-and-Calendars PR on the explicit-clock PR. Test Fey day34 = mainland day17
at ratio2, deriving mainland day20 from Fey day40; ratio-only durations; inverse/chained/negative
conversion; endpoint inclusivity; exact thirds; consistent cycles and conflicting paths; explicit
reading conflicts; hidden-source noninterference; bounded work; stale/concurrent writes; copy,
release/backward readers/purge; generated contracts and real-API desktop/phone workflows.

Changing rates over history, ageing, today, travel-relative anchors, placement inheritance,
branching and historical state remain outside this slice. Readings never establish order.
