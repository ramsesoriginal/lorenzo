# 0316 - Collaborative Events, Facts and participant audiences

Status: accepted, agreed with the maintainer on 2026-10-21. Narrow follow-up to
RFC 0028 and RFC 0044; supersedes the Event/Fact role restrictions in ADRs 0305,
0313, 0314 and 0315 where explicitly stated below.

## Decision

Authors and GMs manage Events and Facts throughout their library. Being a GM in
any campaign is sufficient, including standalone entries and entries concerning
other campaigns. Owners/Organizers retain their existing full-visibility standing;
existing administrative opt-outs are respected. This is not a general widening of
access to beings, inventory, calendars or other libraries.

Management includes entry details, date associations, participation, Information,
entry audiences, ordering/causal assertions and learning records. Event managers
read the complete shared Event graph, including private assertions, so validation
cannot reveal a graph they cannot inspect. Players retain reader-scoped shared
order and cannot edit assertions or learning records, even on their own Events.
Learning references require sight of their being and source Information; Event
management does not grant access to unrelated private source Information.

Players may create Events and Facts and edit entries they created. Creation
identity is the existing entity.created_by, never inferred from timestamps or
participation. Current library participation is required; creator identity alone
is not a cross-library or permanent access grant. Copies use the existing copy
engine's destination authorship semantics, not a new transferable creator right.
A creator sees their entry and can manage its details and outer audience, but
cannot read, publish or edit someone else's restricted Information through this
standing. Creation retries retain existing client-id collision rules.

Readers of an Event or Fact may append their own ordinary notes and edit their
own notes while they can see the containing entry. Visibility alone does not
permit editing another person's Information, replacing its description or picture,
changing its audience, or reordering other people's notes. Other entry kinds keep
their current authoring rules. Both outer and inner gates remain independently
enforced on reads, payloads, previews, link resolution, counts and pagination.

Events have optional live participant sharing for their outer audience and for
individual Information bundles. Recipients are users reached through existing
player-to-being control, using the Event's current explicit participating beings.
Removing participation removes that access unless another grant applies. This
records present access, not learning, lived order, memory or historical knowledge.
Group membership is not inferred from participation. Facts have no participants
and cannot use this audience. Sharing an Event never opens all its notes; sharing
a note never silently opens its Event. Explicit grants remain additive and
editable with the existing atomic, conditional audience operations.

Event creation offers Restricted / Participants / Everyone in this library,
defaulting to Restricted, and the Event page offers the same quick controls.
The initial entry and chosen visibility are saved atomically. Changes to notes,
participation and audiences retain conflict checks and never silently overwrite
a concurrent edit. Reader responses and caches must be reauthorized against
current participation. Wider Event management alone does not qualify for the
existing full-visibility private-body cache retention.

Groups can contain all beings, including NPCs with no Character component, as
explicitly agreed after checking ADR 0031. Player ownership and roster seats still
require Characters. The existing group_member member key now references Being
through its composite same-tenant FK; legacy column and API field names containing
"character" remain accepted for compatibility, and now accept being ids. Ordinary
group writes retain per-member standing: tracked Characters use existing character
management and bare beings use existing NPC/holder management. Group knowledge
remains one-level; this does not add nested-group inheritance. Removing Character
tracking preserves membership; deleting the Being removes its membership.

GMs and Authors can create a named ordinary group from an Event's participants.
The app previews the exact current beings before confirmation. Creation copies
membership once, under a version precondition and in one transaction; later
participation changes do not synchronize the group. Retry-safe client ids prevent
duplicate groups and must not add members to an unrelated existing group. Creating
the group grants no Event or Information access automatically.

Any new tenant tables force RLS, use composite same-tenant foreign keys and join
the copyable-table registry. Audience flags travel with repository copies and releases and remain local after
copying; upstream updates never silently change sharing. Old releases default false.
No source identities, private learning records or participant counts leak through
reader exports or activity summaries.

## Delivery and validation

One reusable documentation subbranch claims this decision. Three implementation
PRs are stacked: role/creator permissions and reader notes; live participant
audiences and creation visibility; snapshot group creation. Each is a tested
API-and-Calendars vertical slice with generated client contracts as needed.

Test real Author, GM, player, opted-out administrator and unrelated-tenant cases;
creator versus other-note authorship; complete staff and filtered reader graphs;
learning source visibility; participant access removal and independent gates;
atomic creation and stale writes; copy/release compatibility; and real-API browser
creation, note editing, visibility and group-preview workflows on desktop/phone.
Clocks, historical reads, separate belief graphs and Fact participants are absent.
