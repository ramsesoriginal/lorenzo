# 0315 - Reader-scoped Event order and explicit sharing

Status: accepted, agreed with the maintainer on 2026-10-21. Next narrow slice of
[RFC 0028](../rfcs/0028-time-causality-and-calendars.md), following ADRs 0312–0314.

## Decision

Authors, campaign GMs and players can read permitted parts of the shared canonical Event
order. There are no separately authored player/GM graphs or beliefs in this slice. Creating,
removing or sharing ordering/causal relationships remains restricted to full-visibility tenant
Owners/Organizers, including opt-outs. Participation and learning retain their existing gates.

An `is_shared` boolean on each `event_relationship` is false by default, including existing
rows. Staff explicitly shares a relationship with readers who can see both Event entries.
This grants no Event existence/name or Information access. Each relationship kind on a pair
is shared separately, so happened-before can be shared without disclosing a causal assertion.
This first control shares with all readers of both endpoints; selected relationship recipients
and campaign-specific relationship audiences remain later decisions. Existing entry audiences
and role/GM policies determine endpoint access; GM standing is never widened tenant-wide.

Full-visibility staff derives order from the complete canonical graph. Other readers derive
order from visible Event nodes and only shared edges whose two endpoints are visible. Filtering
happens before linearization, path search, causal traversal, counts and pagination. Name/causal
filters then operate on that authorized graph, preserving permitted intermediate evidence.
A hidden node or private edge cannot influence a reader's tie ordering, proof, path length,
counts, page boundaries or response revision. Reader relationships expose no staff revision.

For Arrival -> hidden meeting -> Departure, a reader with only Arrival and Departure sees no
path through the meeting, even if its incident edges are shared. A separately authored and
shared Arrival-before-Departure assertion may disclose that relative order without the meeting.
Pairs remain always comparable with the existing causal/ruled/linearized/identity labels;
linearized means no permitted recorded path, never evidence of chronology. Different readers
can receive different linearized display orders. Dates and participation infer nothing.

Sharing edits use the existing graph lock, UUID-ordered endpoint locks, required If-Match and
endpoint revisions; duplicate requests are no-ops. Legacy assertion PUT retries do not reset
sharing. Hidden/missing Event reads have the same 404. Read APIs accept tenant participants,
while write capabilities remain separately explicit. Private relationship actions and sharing
changes are excluded from opted-out activity logs before pagination. Shared reader responses
carry no hidden counts, placeholders, global positions, private flags or hidden Event metadata.

Repository copies preserve explicit sharing on copied assertions; release documents advance
to format 9 and older documents default all relationships to private. Sharing is local after
copy, with no implicit upstream synchronization. Tenant RLS and same-tenant Event keys remain
unchanged. Public previews do not gain a new graph export.

## App and validation

Calendars offers reader Event lists in story order, causal browsing, relationship lists and
comparisons using the reader's authorized graph. The Event panel explains this view and keeps
all write controls staff-only. Staff rows offer Share relationship / Make relationship private
and explain the both-endpoint requirement. Existing participant/learning panels stay staff-only.
Beings' participating Event section remains restricted because participation is not shared here.
Existing private-cache scope and fresh capability checks remain; reader bodies are fetched
fresh, and no comparison POST enables durable private caching or an offline access grant.

Test private defaults, sharing kinds independently, stale/concurrent writes, hidden/missing
endpoints, private-edge and hidden-node noninterference (including adversarial UUID ordering),
transitive proofs and causal branches, filtered pagination, Author/GM/player/opt-out boundaries,
unchanged Information/entry audiences, retained participation/learning restrictions, copy/release
backwards compatibility and real-API desktop/phone staff/reader workflows. Deliver one tested
API-and-Calendars vertical PR stacked on this feature's documentation review; maintainer merges.
