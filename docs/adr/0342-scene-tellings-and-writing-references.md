# 0342 - Scene tellings and writing references

Status: accepted implementation of RFC 0047 W3 and ADR 0327.

## Decision

A Scene telling is an entry with a required reference to an existing reusable Scene,
an optional viewpoint Being, and an explicit shared or independent manuscript mode.
It is distinct from a Session appearance and never asserts Event occurrence or participation.
The generic entity-kind response gains `scene_telling`; generated clients and the exact
accepted OpenAPI findings are updated together.

An Edition or Chapter may place a telling among its prose and Chapters. A telling has
at most one parent; repeated uses of a Scene create distinct telling entries. Removing
a placement preserves the telling and its notes. The existing placement relation is
generalized to child entries, with API validation of the allowed kinds. Tellings cannot
contain Chapters or other tellings. All structural writes retain the library lock,
conditional composition version, tenant-scoped foreign keys and cycle guards.

Shared mode reads the Scene's designated manuscript, with separate authorization of
both the telling and the source bundle. It never silently writes through to the Scene.
The editor offers an explicit link to edit the shared Scene and an action to make this
telling independent. That action conditionally copies the current permitted prose and
pictures into a fresh private bundle, then switches mode atomically; retries return the
already-independent telling. Subsequent edits cannot change another telling's prose.
A new independent telling may start empty. Notes always belong to their own entry.

Viewpoints and Scene references are selected from accessible entries, never inferred
from prose. Existing Scene Fact/Event/Being/period references remain the canonical
world links, with their existing explicit sharing and both-end visibility rules.
Writing offers these references in an optional in-page Details view. A simple biography
creation action creates a private Being with an internal writing-biography marker and
its own manuscript. Library Authors may edit these marked biographies, not arbitrary
campaign Beings; repository author rules remain unchanged. No Character, ownership,
roster, knowledge or inventory capability is granted by biography creation.

Edition duplication creates fresh telling entries. Independent telling bundles are
copied privately; shared tellings retain their Scene reference and shared mode. Viewpoint
references remain references, without widening access. Deleting a referenced Scene or
viewpoint is refused until references are removed. Repository copies and releases carry
telling mode, remapped Scene/viewpoint references, biography markers and generalized
placements; missing dependencies are reported. Revision history and audience grants are
not duplicated. Older release documents upgrade with empty new fields.

## Validation

Exercise two tellings of one Scene, explicit independence and retries, viewpoints,
hidden sources and protected pictures, unchanged Event/Session state, author scope for
biographies, placement/removal and Edition copying. Prove tenant isolation, composite
foreign keys, registry coverage and repository copy/release/purge behavior. Real-API
browser coverage must demonstrate reuse, independent editing and optional Details with
the shared controls and no new CSS. Reviewers, split/join, Carriers and later slices
remain deferred.
