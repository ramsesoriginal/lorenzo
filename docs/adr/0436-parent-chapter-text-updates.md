# 0436 - Repository text updates for Chapters with subchapters

RFC 0047 W9e extends ADRs 0430/0435 without applying structural changes.

## Decision

A copied Chapter within an Edition may accept updates to its own manuscript text even when it
contains Chapters. New copies retain its direct child edges as well as its ancestor path. Each
child edge records the source Chapter identity, following own-payload anchor and position; sorted
stable identities make this independent of query ordering. No child prose enters the parent's
text baseline or is overwritten by accepting the parent's text.

Base, local and upstream must agree on both ancestor path and direct child edges. Additions,
removals, reorderings, reanchoring and kind changes require structural review. Child tellings,
coverage or redirects remain unsupported. Ancestor dependency refusals continue. The complete
current context enters the review version, and the existing tenant structural lock serializes
acceptance with composition changes. Existing payload shape, history, audience and draft/session
protections remain unchanged.

Leaf context formats remain compatible. No child baseline is inferred for older parent copies.
Only Chapters rooted in an Edition are added here; unassigned parent trees, Edition/Book direct
text, shared tellings, assets and structural update application remain later W9 work.

Continuous reading preserves the exact interleaving of parent prose and child entries. A parent
update never accepts a child's separate repository changes. A child may be reviewed separately.

## Validation

Test parent updates with children before/between/after own text, source/local child-edge changes,
legacy context refusal, unchanged child prose/placements and remapped anchors. Preserve leaf and
nested regressions. Verify parent acceptance and continuous Edition reading in the browser with
unsaved-draft, reload, session-credit and phone-accessibility checks.
