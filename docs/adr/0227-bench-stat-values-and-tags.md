# 0227 - Bench: stat values and tags

Status: accepted, decided with the maintainer on 2026-10-09. The second slice of B3 in [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (section 6), after [ADR 0224](0224-bench-description-and-notes.md). Builds on [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md) (the command layer) and [ADR 0225](0225-stat-writes-that-can-be-checked-and-undone.md) (the API side).

## Context

Bench edited an entry's name, parents, description and notes. Its Stats pane said "not editable yet". The API side of stat writes was made checkable in ADR 0225: a stat write moves the entry's version, an own value can be cleared, and the entry's `ETag` comes back with each write.

## Decision

- **One command, `stat.set`.** It sets the entry's **own** value for one stat, or with `null` removes it, so the entry inherits again. A tag is a bool stat, so it is the same command with `true` or `false`. The command carries the stat's id, name and type (`stat`), so it can be sent, shown and undone on its own.
- **What is compared is the entry's own value**, not the effective one: `base` is what the entry had of its own when the person wrote the change (`null` for none), `mine` is the new value, and the three-way compare of RFC 0039 section 5 is the one the other fields use. The same value arriving elsewhere is "already there"; a different one is a conflict, with Keep mine / Use theirs.
- **Undo is exact**: the inverse puts `base` back, which for a first value is `null`, and that is clearing it (`DELETE`). Bench reads the entry just before every write, so it does not need the response's `previous` to do this; `previous` is for callers that write without reading first.
- **Sending**: a number or text to `PUT .../stats/{id}`, a bool through `PUT` (true) or `PATCH` (false) of `.../tags/{id}`, a removal through `DELETE .../stats/{id}` (a bool's through `DELETE .../tags/{id}`). Each carries the entry's `If-Match`; a `412` reads the entry again once, as for the other fields. A write that sets a value sends `acquire_group`, so an entry given a stat from a group it does not have yet gets the group, as the tag routes already do ([ADR 0142](0142-acquiring-a-stat-group-on-the-generic-stat-put.md)). Clearing a value leaves the group, as the API does.
- **The stat vocabulary** is read with the entries (`GET /stat-definitions`) and cached by the transport, since an entry names its stats and a write needs their ids. An entry's stat whose definition is not in the list is not shown.
- **The Stats pane** lists the entry's stats: an own value as a field (a number, text, a choice among an enum's values, a checkbox for a tag), an inherited one in the same field, italic and marked "(inherited)". Changing an inherited value makes it the entry's own. A `×` removes an own value. "Add a stat…" lists the stats the entry does not have, and adds one with a starting value (0, empty text, the first enum value, `true`).
- **A float is not editable yet.** The API wants a float stat sent with a decimal point (no int/float coercion, ADR 0037); JSON written by the browser says `3` for `3.0`. It is shown, and left out of "Add a stat", until the transport can write a number the server reads as a float (a serializer that keeps the point, or a server that accepts it). Not worth guessing at here.
- A value cleared locally is shown as inherited with no number until the server answers, since the inherited value is not known on this side.

## Consequences

- Own stat values and tags are written, undone and checked like the rest of an entry, offline included.
- The sample server grew stats and inheritance, so the whole path is tested in a browser without an API. As with the other fields, the real transport is covered by unit tests against a faked fetch, and by hand against the deployed API.
- Formulas, the stat vocabulary itself (making stats, groups, enum values) and the link name are not here; they come with their own slices.
