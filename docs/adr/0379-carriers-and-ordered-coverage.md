# 0379 - Carriers and ordered coverage

Status: accepted implementation of RFC 0047 W6a under ADR 0327.

## Decision

A Carrier is an entity-backed marker and may stand alone with its own manuscript. Forms and
artifacts use the existing multiple-prototype graph: neither is a separate taxonomy or seeded
kind. Authors can create Carrier forms, choose several Carrier parents and write directly on
an artifact. Prototype ancestry does not inherit coverage or concatenate manuscripts. Physical
inventory participation remains a later explicit capability, not a consequence of coverage.

Coverage is separate from Chapter composition, containment and inheritance. A Carrier has an
ordered list of references to whole Editions, Chapters, Scenes or tellings, or to individual
manuscript payloads. A Book is selected through its Edition. Each occurrence has its own stable
identity; several Carriers can reference the same writing, including across Books. References
follow stable payload identity when extraction moves it, rather than character offsets or a
stored owner. Whole-entry references read the entry's current composition. Joined Chapters
retain the existing guarded redirect, never silently include the whole destination manuscript.
Carriers are not coverage targets in this slice, so coverage cannot introduce recursive cycles.

References interleave with the Carrier's own manuscript using following-payload anchors, as in
ADR 0341. A null anchor follows its prose. Removing coverage does not delete its target. Deleting
a target removes that reference; deleting an anchor moves preceding references to the end.
The Carrier's outline is replaced conditionally under the library structural lock. Reference
identities are client-chosen, tenant scoped and collision checked. A successful identical retry
returns the current result; stale different replacements fail. Hidden references are neither
returned nor silently deleted: replacing an incomplete outline is refused.

Coverage supplies no permission. Each referenced entry and manuscript Information is independently
authorized, including the current owner of a selected payload and shared Scene sources. Hidden
names, identifiers, bytes and counts are omitted. Book reviewers receive no Carrier access or
expanded scope. Authors retain existing library/repository manuscript powers. Prototype writes
check accessible Carrier parents and use ordinary graph cycle protection.

The Carrier marker and coverage table have tenant_id, FORCE RLS, same-tenant foreign keys and
content copy registration. Copies and releases remap Carrier identities, target entries/payloads,
prototype parents and local anchors. Partial copies require those dependencies; deletion guards
protect references from unrelated repository updates. Release format 29 adds coverage, with older
formats reading it as empty. Ordinary manuscript update semantics remain W9.

Writing offers Carrier in Start with. Its editor stays primary; Outline provides quiet optional
coverage and prototype controls using existing classes. Authors find writing by title, choose
whole writing or a specific text/picture block, and reorder it with their direct prose. Read
assembles only accessible writing. No new editor, CSS framework, counting or export features.

## Validation

Test standalone writing, multiple parents and cycle rejection, cross-Book ordering, repeated
references, stable payload extraction, stale/replayed writes, tenant isolation, hidden targets
and reviewer boundaries. Verify copy/release remapping and historical format readers. Exercise
the real API from the browser, direct prose plus coverage, removal without deletion, desktop
and phone layouts and accessibility. Run generated-client and full stacked CI checks.
