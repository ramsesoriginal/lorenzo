# RFC 0047: Lorenzo Writing, manuscripts, editions and carriers

Status: accepted with the maintainer on 2026-10-23. Decision: [ADR 0327](../adr/0327-lorenzo-writing.md).
Implementation is authorized as tested vertical slices in stacked PRs; no PR is merged autonomously.

## Purpose

Let authors of stories, books and game lore start writing immediately, then introduce structure
as they need it. Lorenzo Writing is a separate static Astro app, apps/writing, using plain
TypeScript, the shared brand and app shell, Authgear, the typed API client, LorenzoScript and
the Information editor. No docked panes, floating windows, large menus or component framework.
Existing classes and tokens come first; additional layout CSS needs a concrete reason.

## Agreed domain

Carrier, Book, Edition, Chapter and Scene telling are entries. The existing reusable Scene is
used unchanged as a narrative identity, with optional Facts, Events, beings and period references.
These are authored composition relations, never physical containment, prototype inheritance,
Event order, participation or knowledge inferred from prose.

A Book represents a work and automatically gets its first Edition. Editions become visible in
the workflow when needed. Each has independent manuscript structure and wording; a new edition
starts as an independent copy. A Chapter may be an unassigned draft. Once assigned it belongs
wholly to one Edition and therefore one Book, as do its subchapters. Chapters can nest without
an artificial depth imposed by the interface; composition cannot cycle. Books/editions may use
Scenes directly, and Carriers may use Chapters or Scenes without requiring a Book.

Every writable entry can have its own prose and pictures. A designated manuscript Information
bundle is distinct from descriptions, research and notes; converting existing text is an explicit,
easy action. An ordered composition interleaves stable manuscript elements with Chapter and
Scene-telling references, so prose may precede, follow or sit between children. Title-only,
picture-only, bullet-only and empty drafts are valid. Unplaced writing is a view, not another
mandatory project entity. A continuous reading view assembles permitted content in authored order.

A Scene can be used repeatedly. A telling is independently addressable and annotatable, and
can use the shared Scene manuscript or carry its own text/pictures and optional viewpoint.
Changing one telling never changes another's prose. Existing Session-bound scene appearances
are not reused as manuscript tellings. A telling does not assert that an Event happened.

Carriers represent artifact forms and artifacts through ordinary multiple prototype inheritance:
a real codex can inherit from vellum, coptic, folio, hardcover and illuminated prototypes together.
No fixed setting taxonomy is seeded. Carrier coverage names whole editions or stable composition
elements, not character offsets. It has its own order, may interleave the Carrier's own writing,
and can span multiple Books or cover only part of one. Different wording is an edition of a Book.
Physical inventory participation is explicit and does not follow from manuscript coverage.

## Writing workflows

Start with an untitled draft, a contents outline, a collection of Scene ideas, pictures, existing
prose or an existing world's entries. Keep title, writing, save status and optional count visible;
Outline, Read and Details open only when requested, in the page rather than permanent panels.
The initial LorenzoScript editor uses a short toolbar and Write/Preview tabs. Focus mode reduces
chrome without hiding save failures. Keyboard, touch and assistive-technology workflows are required.

Authors can reorder, nest/promote, split, extract, join and reuse content. Each restructuring
operation is atomic, retry-safe and conditional on the versions it read. Preserve valid local
LorenzoScript constructs, footnotes and links when splitting. Moving existing prose is not new
writing. Removing a placement does not delete its source. After joining, source identities,
notes and permissions remain; their manuscript redirects to stable sections of the destination,
which must independently authorize the reader. Sources remain inspectable, not second editable
copies. Redirects cannot loop and never grant access.

## Access and safety of work

Authors have full manuscript reading and writing in repositories and libraries, without new
rights over unrelated campaign secrets or inventory. Creating simple Being biographies and
Scene references is scoped to writing needs rather than blanket campaign management.

An Author can invite named signed-in reviewers to a Book's selected editions without library
membership. A review grant reaches manuscript descendants and tellings only, not unrelated
research, biographies or other private notes. Reviewers read and append/edit their own notes;
those notes are visible to their author and the Book's authors, not other reviewers by default.
Removing a grant revokes the access it supplied. Entry and Information gates remain independent;
all routes, bytes, previews, resolution, counts, exports and cached reads enforce the same scope.

Autosave uses conditional writes and retains both versions on conflict, without silent text
merging. Unsent drafts survive browser reload/closure, separately per account. Server manuscript
revisions provide recoverable saved history, including checkpoints before restructuring and
incoming updates. Recovery is not a promise of offline browsing. Logout, account switching,
revocation, storage failure and image recovery must have explicit tested behavior before shipment.

## Numbering and special Chapters

Numbering is presentation, separate from titles and identities: per-level decimal/Roman/alphabetic
rules, continuous or parent-restarted sequences, starts, overrides, sequence boundaries and
unnumbered sections. Structural contents include/exclude choices, depth and a constrained template
produce links from composition. They do not yet combine headings inside separate LorenzoScript
texts. Index and glossary Chapters are authored text; automatic generation/markup is deferred.

## Counts and assistance

Count manuscript words rather than markup, notes or generated contents. Scope may be a selection,
Scene/telling, Chapter subtree, Book, Carrier coverage or selected pieces; assembled counts count
repeated text each time the reader encounters it. Specify language/footnote/caption rules with the
counting slice. Separate manuscript-length goals from net-new personal writing-session goals and
optional timers. These sessions are not campaign Sessions. Structural moves contribute zero.

Name/date matching offers suggestions only. Match accessible names and explicit dates, preserve
wording, expose ambiguity and require acceptance. No language-model service, automatic rewriting,
inferred Event participation, causal assertions, learning or knowledge grants.

## Repositories and output

Manuscript content and structure participate in copies and releases with remapped same-tenant
references. Review grants, personal writing sessions, local drafts and recovery history are not
published content. Extend repository updates for manuscript prose: compare base, local and upstream;
apply unchanged local content only through explicit updates, review conflicts, and apply dependent
structure/text atomically. Do not silently change sharing. Existing non-manuscript text behavior
is not broadened incidentally.

Initial export is lossless LorenzoScript and basic PDF only, assembled from an authorized,
consistent manuscript snapshot. PDF supports basic headings, numbering, contents, images and
local footnotes; advanced layout is later. Source export preserves structure and assets as needed
rather than flattening away identity. Other formats are deferred.

## Delivery

Each row is an independently tested API-and-app vertical slice, stacked on the previous PR.
The reusable documentation branch records further implementation decisions before their code.
Later slice schemas are not built speculatively. Every tenant table has tenant_id, FORCE RLS,
same-tenant composite foreign keys and an explicit copyable-table registry classification.

| Slice | Usable outcome |
| --- | --- |
| W1 | Writing app, standalone manuscript editing, images, safe autosave, local draft recovery and server revisions |
| W2 | Books, independent Editions, nested Chapters and ordered mixed composition, continuous reading |
| W3 | Reusable Scenes, independent tellings, viewpoint and permitted world references/biographies |
| W4 | Book-scoped reviewers, revocation and author/reviewer-only notes |
| W5 | Atomic extraction, split/join, nesting/moving and guarded source redirects |
| W6 | Carrier prototypes and ordered stable-element coverage, direct writing and standalone combinations |
| W7 | Chapter numbering, structural contents, authored special Chapters and aggregate counts |
| W8 | Separate goals/timers and reviewed name/date suggestions |
| W9 | Explicit manuscript prose/structure repository updates, conflict review and release compatibility |
| W10 | Lossless LorenzoScript source export and basic PDF export |

All slices carry repository-copy/release support for the content they introduce; W9 adds the
new update semantics, not a retroactive excuse to omit copy support. Tests cover isolation,
permissions, concurrent and replayed operations, real-API browser flows, phone accessibility,
long manuscripts, focus/selection preservation and ordinary flashbacks without time inference.
Authgear/Pages setup is documented separately and never represented as deployed until configured.

## Relationship to existing decisions

Builds on RFC 0001, RFC 0024, RFC 0027, RFC 0036-0041, RFC 0044 and RFC 0046. The manuscript
portion of RFC 0042 W-G is superseded by this program; its sheets/template question stays open.
Bench may later view these same entries, but a Bench manuscript UI is not a prerequisite or a
second implementation here. ADR 0327 records the agreed boundaries; slice ADRs settle mechanisms.

## Deferred

Replacement editor; cross-document LorenzoScript contents/headings and relocated footnotes;
advanced layout/publishing; simultaneous live collaboration; generated maps/timelines as Chapters;
index/glossary notation and generation; full offline browsing; HTML export, DOCX, ODT, portable
Markdown and LaTeX exports. No automatic sharing or automatic prose replacement.

## Research references

- [Scrivener restructuring](https://www.literatureandlatte.com/blog/merge-and-split-files-in-the-scrivener-binder)
- [Scrivener targets](https://www.literatureandlatte.com/blog/track-statistics-and-targets-in-your-scrivener-projects)
- [Plottr overview](https://docs.plottr.com/article/8-plottr-overview)
- [Reedsy Studio](https://reedsy.com/studio/)
- [iA Writer](https://ia.net/writer/support)
- [Hemingway writing mode](https://4.hemingwayapp.com/help/docs/quick-start-guide)
- [Vellum numbering](https://help.vellum.pub/elements/numbering/)
- [Vellum contents](https://help.vellum.pub/elements/toc/)

These informed interaction choices, not additional feature commitments.
