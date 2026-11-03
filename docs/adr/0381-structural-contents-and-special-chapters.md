# 0381 - Structural contents and special Chapters

Status: accepted implementation of RFC 0047 W7b under ADR 0327.

## Decision

An Edition or unassigned Chapter tree can show an optional structural contents list before its
prose. The root supplies depth (one to one hundred Chapter levels) and a constrained text label
template. The default is `{number} {title}`; `{title}` is required once and `{number}` is optional
at most once. Other braces are rejected, and all literal text is displayed as text, never HTML.
This is a link list, not a page-number layout or a combination of LorenzoScript headings.

Each Chapter has an optional presentation role: ordinary Chapter, Contents, Index or Glossary.
These are not new entity kinds and do not change manuscript storage, audiences or ownership.
Index and Glossary remain authored LorenzoScript, including pictures. A Contents Chapter keeps
its authored prose and displays the root's generated list before it, even when the root's own
list is off. The Contents Chapter omits itself from its own list. Role changes never rewrite
prose, numbering or inclusion; the author controls those separately.

Every Chapter has an include-in-contents choice, default true. Excluding a Chapter hides its row,
not its included descendants; nesting is drawn under the nearest included ancestor. The depth
limit follows structural Chapter depth, not displayed row count. Contents follow the same mixed
composition/anchor order and reader-scoped numbering as ADR 0380. Scenes, tellings and payloads
have no generated rows. Invisible branches and joined redirects contribute no rows, names, IDs,
counts or depth clues. Directly opening an accessible Chapter uses its highest accessible
Edition/Chapter ancestor, never an inaccessible ancestor's settings.

A tenant-owned manuscript_contents row stores validated presentation settings for an Edition or
Chapter. Author-only conditional replacement uses a settings ETag and the structural lock,
accepts identical retries, rejects stale different edits, and refuses joined sources. Reads
are private/no-store. Reviewer contents use the existing Book review scope and revocation gates;
links stay within that review rather than granting library or unrelated entry access.

Independent Edition duplication and repository copies retain settings with remapped entry IDs.
Release format 31 adds them; previous formats read absent settings as defaults. Moves retain
Chapter inclusion/role; attached Chapter root policies are dormant until unassigned again.
Extraction creates ordinary default Chapters. Joins leave source settings inactive. W9 still
owns the explicit repository manuscript-update and conflict-review semantics.

The Outline has one closed Contents control, built with existing classes. Authors choose the
root list/depth/template and each Chapter's role/inclusion. Read and Book review render semantic
nested links, and Contents Chapters place generated navigation before their authored prose.
Carrier reads retain the source contents and use authorized source-reading links; payload-only
coverage does not pull in a generated list. No new CSS, editor, automatic index/glossary markup,
word counts, page layout or export is introduced.

## Validation

Test ordering, inclusion with included descendants, depth, safe templates, standalone Chapters,
numbered links, hidden branches, review revocation, stale/replayed/concurrent writes, forced RLS,
Edition and repository copies and historical release readers. Verify author controls, generated
navigation and preserved authored special-Chapter text in real-API desktop/phone browser tests;
run the full stacked CI gate before review.
