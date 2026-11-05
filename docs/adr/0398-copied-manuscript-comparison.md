# 0398 - Comparing copied manuscript bundles

RFC 0047 W9a adds a read-only manuscript comparison before update application.

## Decision

A new repository copy records the designated manuscript bundle on its entity copy link in a
separate nullable JSON baseline. It records ordered stable payload identities, text/locale and
binary fingerprints, plus the copied bundle/payload identity mapping. It excludes audiences,
notes, personal goals, revisions and reviewer grants. The existing tenant-owned copy link and
its forced RLS cover this operational state; it is not repository content or a release field.
Ordinary entity updates neither replace nor advance this manuscript baseline.

An Author with current edit/history access to that exact local manuscript can explicitly
compare its saved direct bundle with the baseline and the repository version. Read upstream
through the existing gated read and public-release switch. Return plain source text and binary
fingerprints, never retained picture bytes or rendered upstream markup. Compare ordered payloads
as a bundle, distinguishing unchanged, local-only, upstream-only, matching edits and conflict.
Removal upstream is reported without deleting anything. No background reads or writes follow.

Older copies have no trustworthy prose baseline. Report that explicitly, never infer one from
today's upstream or local text. A removed or replaced local bundle does not expose its old
baseline. Grant revocation prevents further comparison. The response is private and no-store.

Writing offers this comparison in Details using the shared three-way review display. It states
that it compares saved direct writing; unsaved edits are not represented. It offers no update
choice yet. Composition/coverage, dependent graph changes, accepting updates, legacy baseline
establishment and atomic application are subsequent W9 slices, with decisions before code.

## Validation

Verify baseline capture and isolation, unchanged/local/upstream/conflict states, payload identity
and ordering, binary fingerprints, missing baselines, removed/replaced bundles, denied access,
release-backed upstream reads and ordinary update preservation. Exercise the comparison from
Writing against the real API, including plain-text rendering and phone accessibility.
