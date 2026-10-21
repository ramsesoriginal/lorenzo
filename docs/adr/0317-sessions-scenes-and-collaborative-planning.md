# 0317 - Sessions, Scenes and collaborative planning

Status: accepted with the maintainer on 2026-10-21; RFC 0046 slices 1-2.

## Decision

Session, Scene and Scene appearance are entity kinds. They receive ordinary entry identity,
slugs, Information bundles and the existing entry features, with explicit kind combinations
and access gates. Narrative Scenes do not represent physical containment or prototype links.
A Scene is reusable and has no required campaign or Session. An appearance has exactly one
Session and one Scene, its own preparation position and its own Information anchor. Notes
on a Scene describe the shared Scene; notes on an appearance belong to that group's Session.
The interface presents an appearance as a Scene inside a Session, not a third top-level tool.

A Session belongs to exactly one campaign. It records one or more assigned GMs, zero or more
campaign players and separately selected Characters controlled by those players. NPCs belong
on the Scene participant list, not in the player roster. Creating or editing this roster
never promotes a being or changes campaign roles or Character control. Campaign GMs may
create a Session and are initially assigned. Assigned Session GMs manage preparation and
read its restricted notes; existing Owner/Organizer privileges and opt-outs remain. Another
GM's library-wide Event/Fact standing does not grant Session notes or management.

A real-world date and in-world starting period are optional while preparing. The real-world
field is a civil date, not a timestamp or ordering claim. Start is an explicit period role;
additional associated periods do not imply a continuous range. Scenes have an optional period.

Session rostered readers can append and edit their own ordinary notes, with two choices:
Me and Session GMs, or Session participants. There is no additional author-only tier here.
The author is identified explicitly; GM access does not imply authorship. Shared means the
Session's current audience, not everyone in the library. Removal revokes roster-derived
access; this is not a historical attendance or permanent memory grant. Manager-only preparation
and hidden appearances may coexist with a shared Session. A Scene's separate audience is
never opened by adding it to an outline. Appearances require Session access, and references
require sight of both ends; hidden rows never affect reader counts, pagination or positions.
Current campaign participation is required for roster-derived access; administrative opt-outs
must not be bypassed by the generic entity or Information surfaces, payloads or cached 304s.

Scene has n:m Facts, Events and participating beings. Session has n:m Facts, Events, periods
and Scene appearances. Direct references are distinct from references through Scenes. None
of these relations infers Event participation, learning, occurrence, causal order or sharing.
Reusing a Scene leaves each appearance's notes separate. A single Scene can appear repeatedly.

Lorenzo Sessions is a static Astro app using shared brand, Authgear, typed API client,
Information editor and app-link registry. It offers My Sessions across permitted libraries,
Session preparation/rosters, ordered Scene outline, dates and notes on desktop and phone.
Routes accept ids or slugs and prefer defined slugs. No durable private cache/offline grant.

Scenes and their authored references are repository content. Sessions, attendance and
appearances are local. Exclusion covers their Entity, Information, payload and audience rows,
not just marker tables. Copies remap Scene references; missing dependencies are reported.
Release/version compatibility and public reads retain both entry and Information gates.

All tenant tables force RLS, use same-tenant composite FKs and join the copyable registry.
Creation and outline changes are atomic and retry-safe. Conditional edits retain drafts on
conflict. Referenced entries cannot disappear through generic kind removal or deletion;
whole-tenant deletion remains supported. No inventory hot-path time joins are introduced.

## Validation

Test GM preparation/player notes end to end, a Session with no players or dates, two groups
using one Scene, private/shared notes and removed roster access, unrelated GMs/players,
opt-outs, hidden links and counts, SQL/Python visibility parity, same-tenant constraints/RLS,
concurrent writes, deletion, copy/release filtering and idempotent retries. Register the app's
tasks, label, workspace, release, dependencies, app links and dedicated real-API browser suite.
