# 0314 - Optional Event learning records

Status: accepted, agreed with the maintainer on 2026-10-21. A narrow slice of
[RFC 0028](../rfcs/0028-time-causality-and-calendars.md), following ADRs 0304–0306 and 0312–0313.

## Decision

An explicit `event_learning(tenant_id, event_entity_id, being_entity_id, information_id)`
records that a participating being learned particular authored Information at an Event.
The triple is its identity; several beings can learn the same Information and a being can
have several recorded learning occasions. A composite same-tenant reference requires the
Event/Being participation, and another references Information. Tenant RLS is forced.
These are author-declared story records, not timestamps inferred from application activity.

Learning records are independent of Knowledge audience grants. They neither require nor
create a grant, change an Information or entry audience, infer learning from participation,
expand current/former group membership, or add Event order/causality constraints. Existing
untimed workflows remain unchanged. No record means unknown learning history, not ignorance.
A later edit to Information retains its identity: this slice does not snapshot earlier text
or claim that current wording was the wording learned. Removing a record corrects provenance;
it does not mean forgetting, revoke access, or erase participation.

All structured learning reads and writes require the existing full-visibility tenant
Owner/Organizer capability, including opt-outs. Author membership or campaign GM standing
alone is insufficient. No records, counts, summaries or hidden dependency identities are
returned to other readers. Ordinary Information and entry reads retain both audience gates.

The API supports filtered, paginated learning reads by Event, being and Information, and
idempotent conditional PUT/DELETE of a triple. Writes lock endpoint entities in UUID order,
then Information; the Event revision guards concurrent record and participation edits.
Missing If-Match is 428 and stale is 412. Audit entries identify the Event, not text.
Removing a referenced participation, Information, or entry is refused with an opaque
existing-reference error until the learning association is removed. Tenant deletion works.

Repositories may hold authored learning records. Copies remap all three ends, report a
missing dependency and never create grants; associations copy once with no implicit upstream
synchronization. Release documents advance a version; older releases have no learning records.
Explicit repository purge removes incident records before their dependencies and reports
counts only to full-visibility staff, following ADR 0313.

Lorenzo Calendars adds a Learning section on staff Event pages: choose an existing participant,
find an entry and select one of its Information bundles, then record or remove the association.
Being entry pages show recorded learning occasions and Information cards offer an on-demand
learning-source list, behind the same fresh capability gate. Selection and drafts survive
conflicts; a refresh obtains the current Event version. Existing private cache invalidation
and navigation guards apply. Ordinary readers have no learning surface or background requests.

## Boundaries and validation

This is learning provenance, not an authoritative historical access ledger. No forgetting,
group/Player learning, permanent memory inference, as-of knowledge verdicts, separate lived
sequence, clocks, confidence or role-scoped Event graph is introduced. No migration invents
learning dates or backfills records.

Test real API/browser authoring and removal, independently unchanged audiences, public
Information without a grant, repeated occasions, filters/pagination, participant prerequisites,
role/opt-out denial, same-tenant references/RLS, stale/concurrent writes, deletion guards,
copy/release compatibility/purge, and ordinary-reader absence. Deliver documentation then
one complete tested API-and-app vertical PR stacked on it; maintainer merges both.
