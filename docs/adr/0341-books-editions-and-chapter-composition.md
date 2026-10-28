# 0341 - Books, Editions and Chapter composition

Status: accepted implementation of RFC 0047 W2 and ADR 0327.

## Decision

Book, Edition and Chapter have entity-backed marker tables. An Edition belongs to one Book;
a Book creation creates its first Edition in the same transaction. Chapter drafts can stand
alone or form a tree; a Chapter has at most one composition parent, which is an Edition or
Chapter. Its Edition and Book are derived by following that tree, never duplicated as mutable
ownership fields. Cycles are rejected. Removing a placement leaves the Chapter and its text.
Deleting an entry that still owns Editions or contains Chapters is refused until it is emptied.

A manuscript's existing payload UUIDs are its stable prose/picture elements. A Chapter placement
has the Chapter's stable identity and an optional following payload anchor in its parent's own
manuscript. Several Chapters before the same payload have explicit order; a null anchor means
after the parent's prose. This represents interleaving without duplicating the payload's text or
order. Deleting an anchor moves its preceding Chapters to the end, preserving them. All links
are tenant-scoped foreign keys. No physical containment, prototype or Event edges are introduced.

Composition reads return the current mixed sequence. Conditional replacement accepts a complete
permutation of current own payloads and the desired direct Chapters. It locks structural writes
per library, checks the parent's ETag and each referenced entry, rejects cycles or a Chapter
already placed elsewhere, and updates payload order and placements atomically. Removed Chapters
become unassigned subtrees. Changes advance the parent version. The UI initially offers explicit
up/down ordering and placing unassigned Chapters; split/join and cross-parent moves remain W5.

Creating another Edition independently copies the selected Edition, its Chapter tree and its
manuscript bundles with fresh entity, Information and payload identifiers. Names, prose, pictures
and internal composition survive; notes, revision history, knowledge and grants do not copy.
New entries and bundles start private. Creation uses client identifiers so a retry does not make
another Book or Edition. A retry returns the existing result only for the same authenticated
creator and matching creation identity, otherwise it conflicts.

Library/repository Authors can read and write these manuscript entries through the existing
entry and Information gates without gaining unrelated campaign powers. Continuous reading
resolves every entry and Information independently and omits inaccessible content and identity.
Book-specific reviewers remain W4. Repository copies/releases carry marker rows, Edition-to-Book
links and composition with remapped identifiers; partial copies require structural dependencies.
Only demonstrated standalone kind combinations are publishable. Generic kind addition cannot
combine these markers with existing kinds incidentally.

Writing keeps the first Edition implicit in the ordinary Book workflow. Authors can start a
Book or an unassigned Chapter, write with the existing editor, open an in-page outline, create
nested Chapters, arrange prose/pictures and Chapters, read continuously, and explicitly duplicate
an Edition. Existing standalone Scenes remain available; Scene tellings are W3. No new CSS or
editor framework is required.

## Validation

Real PostgreSQL tests cover tenant isolation, same-tenant links, cycle and duplicate-placement
rejection, stale writes, retries, independent copies, deletion guards and visibility. Repository
copy and release tests demonstrate remapped structure and payloads. Real-API browser tests cover
starting a Book, nesting and ordering Chapters, interleaving prose, continuous reading and editing
an independent Edition. Generated clients and downstream contract checks remain mandatory.

## History

Originally claimed as ADR 0336 on the Writing branch. On 2026-10-24 the open Maps
decisions also used 0336; Writing moved this document to 0341 to keep the combined
index unambiguous. Existing migration identifiers remain unchanged.
