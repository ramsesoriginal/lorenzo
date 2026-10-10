# 0235 - Bench: the entry picker

Status: accepted, decided with the maintainer on 2026-10-09. The picker part of slice W-C of [RFC 0042](../rfcs/0042-bench-workbench-interface.md), after [ADR 0233](0233-bench-links-to-entries-in-text.md) (links to entries in text).

## Context

An author writes a link to an entry by typing `[[Name]]` and knowing the name. With the links of ADR 0233 shown as links or as plain text, the missing part was finding the name: which entries are there, and how exactly is this one spelled.

## Decision

- **Typing `[[` in a description, a note or a new note offers the entries**, in a list under the field, filtered by what is typed after the brackets: those whose name starts with it first, then those that contain it, each by name, at most eight. Nothing typed offers the first eight by name.
- **It is driven from the keyboard without leaving the text**: the arrows move, Enter or Tab choose, Escape closes it and leaves what was typed. A click chooses too, without taking the focus from the text.
- **Choosing writes the whole link**, `[[Name]]` with the entry's name as it is, replaces what was typed after the `[[` (and a `]]` already there), and puts the caret after it; the preview then shows whether the link works (ADR 0233).
- **The list is the one the explorer has** (`bench.listing()`), so entries made here and not yet sent are offered; the link they make stays text until they are sent and looked up (ADR 0233 says so). What the picker writes for an entry follows its link name, as [ADR 0236](0236-bench-link-names.md) describes.
- **Entries that cannot be linked by name are not offered**: a name with brackets in it, and one with no letter or digit to make a link name from (the link name is the slug of the name, [ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md)).
- The list sits under the field, not at the caret: a textarea does not say where its caret is on the screen.

## Not here

- **(Done in [ADR 0236](0236-bench-link-names.md).) A link name that is not the slug of the entry's name** (an entry given its own link name, [ADR 0107](0107-entity-slugs-and-batch-resolve.md)): the list does not know link names, so what it writes is `[[Name]]`, and the preview says when that does not reach the entry. Writing `[text](slug)` from the entry's real link name waits for the list to carry it.
- Toolbar buttons that insert links, and the picker for pictures.

## Consequences

- Links are written by choosing, not by remembering; a name that is spelled wrongly is no longer a way to lose a link.
