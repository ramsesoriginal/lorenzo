# 0346 - Safe paragraph splits

Status: accepted implementation of RFC 0047 W5c under ADR 0327.

## Decision

Split a saved manuscript text payload into two adjacent text payloads at a safe paragraph
boundary. Keep the original identity for the first part and create a client-named identity for
the second. Both stay in the same Information bundle with the same locale and audience.
Concatenating their source strings reproduces the original exactly, including whitespace and
Unicode. Existing child placements retain their relative position. Either part can then be
extracted using W5b; these are two explicit operations, each atomic. Joins and guarded redirects
remain later W5 work.

Use a conservative server-side boundary check, not a second LorenzoScript parser or a new
runtime. This slice supports ordinary paragraphs and inline markup. A complete simple footnote
can remain with its references on either side; reject a boundary when a normalized footnote
label occurs on both sides. Reject compound-block texts (lists, quotes, code, tables, display
math and class blocks), abbreviations, headings/fragment anchors and contents directives rather
than changing their meaning. More general syntax-aware splitting remains later W5 work; these
restrictions are shown in the interface, and whole-element extraction remains available.

The API offers safe split points from the saved text with readable following-paragraph snippets
and an outline version. The write rechecks that version and the chosen boundary under the
library structural lock and manuscript bundle lock. Do not accept replacement prose from the
client. Validate ids and permissions, stage order changes to checkpoint the original manuscript,
then split the content and insert the second payload in one transaction. No audience or notes
change, and this is structural work rather than new writing.

A tenant-scoped operational receipt records actor, request fingerprint, entry and both payload
identities. Exact retries acknowledge the original split after later edits, without splitting
again; current entry and manuscript editing access is still required. Changed requests and
other actors cannot reuse the operation id. FORCE RLS and same-tenant foreign keys apply;
receipts are excluded from copies/releases. Content uses existing payload copy/release contracts.

The outline offers Split text beside a text block, only when requested. Choose a following
paragraph by its words and confirm; no character offsets or codes are shown. Keep the original
version and operation id for retries. The shared editor and styles remain unchanged. On a stale
version, explain that the author must reopen the outline rather than silently selecting a new
boundary in changed text.

## Validation

Shared source fixtures exercise the Python boundary guard and the canonical TypeScript parser.
For accepted boundaries, the two parses must retain the original blocks and footnotes, and their
source concatenation is exact. Cover inline links/emphasis, Unicode, CRLF, footnote dependencies
and rejected compound constructs. API tests cover order/identity/locale, saved revisions,
permissions, stale and concurrent writes, safe retries, id collisions with rollback, RLS and
repository copies. Browser tests split, extract, read and edit the resulting Chapter, with
phone accessibility and unchanged text.
