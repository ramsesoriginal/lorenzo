# 0313 - Event participation, browsing and calendar addresses

Status: accepted, agreed with the maintainer on 2026-10-21. A further narrow slice of
[RFC 0028](../rfcs/0028-time-causality-and-calendars.md), after ADRs 0308–0312.

## Decision

### Participation and Event browsing

`event_participant(tenant_id, event_entity_id, being_entity_id)` is a simple many-to-many
relationship, keyed by `(event_entity_id, being_entity_id)`. Both ends have composite
same-tenant foreign keys to their StoryEvent and Being components. It has FORCE RLS and a
copyable-table entry. There is no surrogate participation id, date, position, clock or learning
record in this slice. Extra appearances of the same being at one Event and participation by
objects remain later decisions. Membership and containment do not expand participation.

Full-visibility Owners/Organizers can list and edit participation, with conditional writes and
endpoint locks. Removing a participation does not delete either entry. Individual Event/Being
deletion or Being demotion is refused while referenced, with an opaque existing-reference
error; tenant deletion works. A reviewed repository purge explicitly removes incident
participations and reports their effects only to full-visibility staff. Copies and release
documents remap both ends, preserve the association and report missing dependencies; old
releases have no participations. Existing copied-association policy applies, without implicit
upstream synchronization.

Calendars gains a standalone Events page: create an undated Event, search, filter by being,
and open the existing Event page to edit Information, dates, participation and order. Ordinary
Event authoring retains existing permissions. Structured participation/ordered/causal browsing
keeps ADR 0312's full-visibility Owner/Organizer gate, including administrative opt-outs.
Causal browsing selects an Event and follows only `causes` ancestors and descendants. Branches
remain branches; an order-only assertion never becomes causation. Ordered browsing derives
the full graph's order before filtering and pagination, with causal/ruled/linearized basis
information. Filtering never invents an edge between displayed neighbours. Beings displays
linked Event titles below Inventory only to staff who pass this same gate. Reader-facing
ordered disclosure remains outside scope.

### Slugs and addresses

Calendars, calendar periods and Events already use entity slugs. Their existing editors and
API remain the source of truth. Calendars accepts a tenant, calendar, period or Event address
by UUID or exact slug, checks the resolved kind, preserves existing id URLs, and generates
URLs using a defined slug preferentially. This deliberately differs from ADR 0135's generated
inventory links, which remain ids. Internal identities, cache keys and remembered selections
use resolved UUIDs. UUID-shaped inputs are ids unless explicitly addressed as slugs. Changing
or clearing a slug has ADR 0107's existing effect: old slug links stop resolving; no alias or
redirect history is added.

LorenzoScript's existing entity links resolve calendar, Event and period kinds to Calendars;
missing and inaccessible targets both remain plain text. The reserved calendar directive now
resolves partial and full dates, for example:

```text
{{cal pal-vaz 3286}}
{{cal pal-vaz 3286/Quirm}}
{{cal pal-vaz 3286/6/16}}
{{cal pal-vaz 3286/Quirm/16}}
```

Month/festival numbers are one-based positions in the definition's full authored segment
sequence, including festivals and conditional segments: absence in a year does not renumber
later segments. Names match Unicode-normalized, case-folded display names uniquely. Stable
segment keys are also accepted; explicit `name:` and `key:` prefixes disambiguate numeric names
or colliding names/keys. Percent encoding permits slashes in names. Coordinates have the
existing year/day bounds and must exist in that calendar/year. Invalid, ambiguous, missing and
inaccessible references stay unresolved. A link opens a computed view and never materializes
a period or reveals whether an inaccessible period exists. Period Information retains its
own audience. Existing unrecognized calendar expressions and legacy string resolvers retain
their plain/text behavior. Syntax examples and TypeScript/Python reference extraction tests
remain aligned.

### Responsiveness

Use bounded, viewer/tenant/visibility-scoped local caches, in-flight deduplication, newest-read
wins, explicit invalidation after writes and bounded prefetch on likely navigation. Reuse the
inventory app's proven patterns rather than building an offline synchronization system.
Cache identities are UUIDs, never mutable slugs. Private Information is session-scoped rather
than copied into a durable catalog-style localStorage cache. Caches are not authorization:
account/library/role/opt-out changes and denied reads invalidate relevant state, and entering
a protected view revalidates its access before cached private data is drawn. Clear private
state at sign-out. Prefetch is bounded, respects permissions and never authors periods or
changes the selected date. Failure leaves a usable ordinary network path, not a new offline
access grant.

## Delivery and validation

Use stacked tested vertical PRs: participation and Event browsing/creation; slug-aware URLs
and LorenzoScript references; the Beings Event section; responsive caching/prefetch. Reuse one
feature documentation subbranch. Every new tenant table has RLS, same-tenant FKs and repository
classification; test role/opt-out disclosure, copy/release/purge, concurrent stale edits,
causal branches, filtered order, named/numeric/ambiguous/leap dates, no-write links, old URLs,
slug changes, cache invalidation and real-API phone/desktop workflows. No clocks, lived order,
timed knowledge, state history, confidence/verdicts or new app is introduced.
