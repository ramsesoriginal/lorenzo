# 0236 - Bench: link names

Status: accepted, decided with the maintainer on 2026-10-10. Closes a gap in [ADR 0233](0233-bench-links-to-entries-in-text.md) and [ADR 0235](0235-bench-the-entry-picker.md); the "link name" of B3 in [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (section 6). Builds on [ADR 0107](0107-entity-slugs-and-batch-resolve.md) (an entry's one slug and resolving it).

## Context

A LorenzoScript link names an entry by its **slug**, its link name: `[[Old Sword]]` means the slug `old-sword`, `[text](blade)` means `blade`. An entry that has no link name cannot be linked to at all. The API gives an entry one only when the create or `PUT .../slug` carries it. Bench sent none on a create and had no way to set or see one, so every entry made in Bench was out of reach of links, and a link to it stayed text for good (ADRs 0233 and 0235 said "until it is sent", which was wrong for these). The picker also wrote `[[Name]]` for every entry, which is the wrong link for an entry whose link name is something else.

## Decision

- **A create carries the link name its name makes** (`slugify(name)`, the rule `[[Name]]` uses), so a link to the new entry works as soon as it is sent. A name that makes none (no letter or digit, as `日本`) is created without one.
- **A link name another entry has does not stop the create**: the API answers `409`, and Bench asks once more without it. An entry with no link name is better than one that was not made, and it can be given one afterwards. A `409` with no link name to drop (an id that is not available) is the answer, as before.
- **The entry carries its `slug`** (the detail has it, nullable), and **a "Link name" field** on the entry shows it and sets it: a command, `entry.set-slug`, compared three ways, undone and sent like the others, through `PUT .../slug`, and `DELETE .../slug` to take it away. Empty clears it. What the API would refuse is said at once (a letter or digit first, then letters, digits, `-` and `_`, at most 100) and not sent; another entry having it is Needs attention with the API's words. An entry with none is offered the one its name makes in one press.
- **The write has no version.** `PUT .../slug` moves nothing the entry's `ETag` follows and takes no `If-Match` (the audit of [ADR 0225](0225-stat-writes-that-can-be-checked-and-undone.md) found it); the command is compared against what was read just before, so a change elsewhere in between is only caught if it happened before that read.
- **The picker writes the link the entry's link name needs**: `[[Name]]` when its link name is the one its name makes, `[Name](link-name)` when it is another. It reads the entry quietly to know. An entry with none still gets `[[Name]]`, and the preview says nothing is called that.
- A rename does not change the link name, so links already written keep working.

## Not here

- Giving every entry that already exists without a link name one, in bulk. The field does it one at a time; a bulk action is a larger question (it can clash, and it writes to many entries).
- A button that follows a rename ("use the new name as the link name").
- Entries whose name makes no link name are not offered by the picker even when they have one (`[日本](nihon)`): the list does not carry link names.

## Consequences

- Entries made in Bench can be linked to, and the picker writes links that work.
- Entries made in Bench before this have no link name until someone gives them one.
