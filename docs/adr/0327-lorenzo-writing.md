# 0327 - Lorenzo Writing: manuscripts, editions and carriers

Status: accepted with the maintainer on 2026-10-23. Implements the decisions of
[RFC 0047](../rfcs/0047-lorenzo-writing.md); delivery is a stack of tested vertical PRs.

## Context

Library and repository authors need a quiet place to write stories and books, beginning with
prose, pictures or outlines and introducing structure when useful. Bench's unbuilt manuscript
view (RFC 0042 W-G) leaves chapter ordering undecided and its docked workbench is a different
interface. Existing Scenes, Information bundles, LorenzoScript and entity identity provide the
foundation, but editions, composition, reviewer grants and prose updates need explicit semantics.

## Decision

Lorenzo Writing is apps/writing, a static Astro app with plain TypeScript, shared app-shell,
brand classes/tokens, Authgear, typed API client and the existing LorenzoScript/Information
editors. The writing surface is primary; outline/details are requested in-page, not permanent
panes or floating windows. A short toolbar, Write/Preview and focus mode are sufficient initially.

Carrier, Book, Edition, Chapter and independent Scene telling are entity kinds. A Book creates
its first Edition atomically; later Editions independently copy its manuscript. Unassigned
Chapter drafts are valid; assigned Chapter trees belong to one Edition/Book. Composition orders
stable own text/picture elements, Chapters and Scene tellings, independently of containment,
inheritance and Event order. Books can use Scenes directly; Carriers can use Chapters/Scenes
without Books. Each entry can carry its own designated manuscript Information bundle alongside
ordinary descriptions and notes. Shared Scene text and a particular telling's text stay distinct.

Carrier forms and artifacts use ordinary multiple prototype inheritance. Coverage relates a
Carrier to whole editions or stable elements, with its own order and direct prose, and can cross
Books. No character-offset anchors or seeded binding/material taxonomy. Variant wording belongs
to an edition; physical inventory is an explicit additional capability.

Authors read/write manuscripts in libraries and repositories without unrelated campaign powers.
Book-specific reviewer grants admit named signed-in users to selected editions without library
membership; manuscript descendants/tellings are in scope, unrelated references/research are not.
A reviewer's notes are for themselves and the Book's authors by default. Revocation, both audience
gates, hidden identities, counts, protected bytes and cached responses must remain consistent.

Draft recovery persists unsent work per account. Conditional autosave retains conflicting versions;
server revisions recover saved work and checkpoint restructuring/updates. This does not implement
live collaborative editing or full offline browsing. Splits/extraction/joins are atomic and
retry-safe, preserve valid LorenzoScript, and cannot broaden audiences. A join preserves source
identity/notes/permissions with a guarded redirect to a stable destination section, not duplicate
editable prose. Removing a placement preserves its referenced entry.

Numbering is per-level presentation with starts/restarts/overrides/boundaries and unnumbered
sections. Structural contents have depth/inclusion/template choices. Index/glossary Chapters are
authored text. Counts cover manuscript scopes; manuscript-length and net-new writing-session goals
are separate, structural moves count zero, and optional timers are personal rather than campaign
Sessions. Name/date matching produces reviewable suggestions only and no inferred world facts.

Manuscript content/structure copies and releases with remapped references. Explicit repository
updates extend to manuscript prose with base/local/upstream conflicts and atomic dependent changes,
never background replacement or upstream audience widening. Personal goals/recovery/reviewer grants
are excluded. Initial exports are lossless LorenzoScript and basic PDF; all other formats and the
advanced features listed in RFC 0047 remain deferred.

## Delivery and validation

RFC 0047 W1-W10 define the accepted vertical slices. Use one feature worktree, a reusable docs
subbranch into main, and stacked implementation PRs naming their predecessor; no autonomous PR
merge. Record mechanism decisions on that same docs branch before implementing the affected slice.
Every tenant table forces RLS, uses same-tenant FKs and joins the copyable registry. Refresh generated
clients for new kinds and prove copy/release behavior before publishing combinations. Verify real-API
browser flows, concurrent/replayed writes, recovery, review revocation, visibility-safe exports,
phone accessibility and large-manuscript typing/focus. No later schema is added merely to reserve it.

## Consequences

RFC 0042 W-G's manuscript portion is replaced by this shared model and dedicated app; sheets from
templates remain separate. The existing Scene-appearance kind is Session-bound and is not reused
for manuscript tellings. The current copy-once prose update rule gains an explicit manuscript-only
extension. Draft storage and reviewer access are new scoped capabilities, not implied by the cache
or library membership. A PDF renderer and revision retention policy are settled in their slice ADRs.
