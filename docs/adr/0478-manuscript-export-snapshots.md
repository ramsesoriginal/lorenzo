# 0478 - Manuscript export snapshots, source archives and basic PDF

Status: accepted. Implements RFC 0047 W10 and ADR 0327; implementation authorized by the
maintainer on 2026-11-17. Mechanism follows the existing Writing reading and review gates.

## Context

Writing can assemble a reading through several API requests. An export must instead contain
one saved, authorized version of its structure, text and pictures. Flattening the result to one
text file would lose the stable elements, reused tellings, Carrier coverage and local footnotes.

## Decision

An on-demand Export control opens an in-page preview of saved writing. It offers **Download
LorenzoScript** and **Print / Save as PDF**. The latter opens the browser's print dialog; the
interface explains choosing Save as PDF. It is basic browser pagination, not a server-generated
PDF download or a publishing/layout system. Use the shared LorenzoScript renderer, self-hosted
brand fonts and existing controls. Only the printable document needs isolated print styling.

The API assembles a read-only export snapshot in a dedicated REPEATABLE READ transaction,
using the restricted application role and the authenticated user and tenant RLS context from
its first read. It includes the chosen entry's authorized manuscript composition: ordered text,
pictures, child Chapters and tellings, repeated Carrier coverage and shared Scene manuscripts.
Books use an explicitly selected Edition (the existing first-Edition navigation remains the
initial choice). Direct drafts, empty writing and picture-only writing are valid exports.
The existing ordinary entry/Information gates apply independently. A separate Edition-review
route uses the existing review grant and its manuscript-only scope; it never admits unrelated
Scene identities, research, notes or other Editions. Revocation is checked again for each request.
Hidden content and identities leave neither placeholders nor counts. Export is a projection of
what this reader may read, not a tenant backup or a copy of access grants.

The versioned snapshot preserves stable entry and element identities, composition order,
permitted telling/coverage relations, source locale, exact text and original picture bytes,
numbering/contents settings and their authorized presentation. Repeated occurrences reuse
stored elements but remain repeated in the reading. A joined source keeps only its guarded
redirect reference; exporting it never silently expands the destination's entire manuscript.
Notes, descriptions outside the manuscript, history, review grants, personal goals and unsent
browser drafts are excluded. Existing unsent work is not silently saved or substituted; the
preview is explicitly labelled saved writing.

A source download is a ZIP identified by `lorenzo-writing/1` in `manifest.json`. UTF-8
`.lorenzoscript` files retain each text payload verbatim; picture files retain their bytes and
media types. The manifest names their stable IDs, paths and order and retains the selected
structure. Paths are generated from IDs, never authored names. Include a small README that
explains the format and the absence of an importer. Source export does not promise a restore
endpoint, new syntax, or an export of referenced world entries.

The preview and printable document use the snapshot only, including its embedded picture bytes.
No external images are fetched; unresolved world references retain their authored text, as in
the existing reader. LorenzoScript headings, tables and local footnotes use the shared renderer;
IDs and local links are scoped to each occurrence so repeated passages cannot collide. Structural
numbering and contents use the existing authorized projections and link only within the exported
reading. Footnotes remain local to their text block, not cross-document or relocated notes.

A content-derived ETag covers the complete snapshot (including picture fingerprints); generated
clock times are not part of it. Downloads and printing reauthorize and condition on the preview's
version. A changed snapshot asks the author to refresh, without silently printing different work.
Responses are private/no-store. Nothing is persisted as a new tenant table or server export job.
Bound assembly to 5,000 distinct entries, 20,000 reading occurrences and 50 MiB of text/picture
bytes; refuse oversized or cyclic exports clearly instead of truncating them. Iterative traversal
keeps the existing unbounded-depth domain model without imposing an artificial Chapter depth.

## Validation

Test exact source/asset preservation and manifest references; nested composition, repeated and
partial Carrier coverage, shared/independent tellings, empty/picture-only drafts and redirects;
consistent snapshots during concurrent edits; tenant isolation, both visibility gates, scoped
reviewers and revocation; stale preview rejection and bounded assembly. Real-API browser flows
cover preview, download, saved-versus-unsent work, keyboard/phone access and print readiness.
Render a representative multi-page PDF with the browser's PDF engine, inspect every page, and
check text, images, numbering, contents, repeated local footnotes and absence of application chrome.

## Consequences

Both outputs describe the same authorized saved reading. Source files retain manuscript
structure and assets; PDF uses the renderer and fonts authors already see. Browser print support
and page settings vary by platform, so the UI names the actual operation. Automatic PDF file
delivery, advanced layout, other formats, cross-document headings/footnotes and an importer remain
outside this slice, consistently with RFC 0047's deferred publishing features.
