# 0380 - Chapter numbering

Status: accepted implementation of RFC 0047 W7a under ADR 0327.

## Decision

Numbering is optional presentation, never an entity title, identity or manuscript payload.
An Edition supplies the policy for its Chapter tree. An unassigned Chapter supplies its own
policy and is level one itself. Attached Chapter policies remain stored but inactive; moving
a Chapter changes its numbering context without rewriting its text or settings. Carriers
retain the numbering of referenced writing, rather than creating another ownership tree.

Policies default off. Each configured level selects decimal, upper/lower Roman or upper/lower
alphabetic numbering, a positive start, restart under each parent or continuous traversal, and
whether to include numbered ancestors separated by dots. Deeper levels reuse the final rule;
there is no new Chapter nesting limit. Alphabetic numbers continue A..Z, AA..; Roman values
above 3999 display as decimal to keep labels bounded. Values and starts are 1..999999.

A Chapter can be unnumbered (no counter consumed), override its next number, restart its level
at the configured start, or end that level's sequence after itself. After an end, siblings at
that level remain unnumbered until an explicit restart or numeric override; a parent restart
starts a fresh sequence. An override also starts a stopped sequence. Unnumbered ancestors are
omitted from compound labels. Children still use their own level rules. Only Chapters consume
numbers; prose, pictures, tellings and joined redirects do not. Traversal is composition order,
including following-payload anchors, rather than creation order or title sorting.

Compute labels from the reader's authorized tree only, pruning inaccessible branches. Hidden
siblings consume no numbers and expose neither gaps nor configuration; no invisible ancestor
identifier is returned. Reviewer reads use their existing Book scope and revocation gates.
The highest accessible Edition/Chapter ancestor supplies context for an individual Chapter.

One tenant-owned numbering settings row per Edition/Chapter stores its policy and Chapter
options as validated JSON. FORCE RLS, repository read policy, same-tenant FK and copy registry
are required. Author-only conditional replacement uses a settings ETag under the structural
lock; identical retries succeed, stale different writes fail. Reads are private/no-store.
Ordinary manuscript permissions and guarded-join rules apply. The new endpoints are additive.

Copy settings with independent Editions and repository content. Release format 30 carries them;
older readers default settings to absent/off. Structural extraction creates default Chapter
options, moves retain options, and joins retain the source settings only as inactive history.
Repository prose/structure update conflict semantics remain W9.

The existing Outline and Read views display labels separately from titles. A closed Numbering
control opens inline using existing brand classes, with level rules on the context root and
Chapter options on each Chapter. Book review headings display the same scoped numbering.
Contents, special-Chapter classification, counts, goals and exports are later W7/W8/W10 slices.

## Validation

Test formats, nested/restarted/continuous sequences, starts/overrides/ends, unnumbered parents,
reordering and anchor order, hidden branches, reviewer revocation, tenant isolation, conditional
writes, Edition duplication, repository copying and historical releases. Exercise real-API
numbering authoring and reading in desktop/phone browsers with accessibility checks. Regenerate
clients and require the full stacked CI gate before review.
