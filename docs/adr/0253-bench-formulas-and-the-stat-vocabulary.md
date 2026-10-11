# 0253 - Bench: formulas and the stat vocabulary

Status: accepted

## Context

A stat can be worked out rather than typed ([ADR 0104](0104-computed-stats.md)): a formula, held by an entry, reaches everything that inherits from it. Bench had no way to see or write one, nor to make a stat (the prototype's Formula editor and Vocabulary panes). The API has everything but a rename of a stat (K6), a bulk read of formulas (K7), and a duplicate (K4).

## Decision

- **Two panes.** *Formulas* lists the stats of the selected entry that are worked out (own, or inherited with "from Parent" that goes there) and edits one. *Vocabulary* lists the repository's stats and makes or deletes them. The Stats pane marks a worked-out stat with ƒ.
- **Four kinds, in a person's words:** *Add up* (`sum`), *Scale* (`linear`), *Contents* (`contents`), *Compare* (`comparison`). Numbers are kept as typed text (a comma is read as a point) and sent as text, so a decimal reaches the API exactly. A draft that cannot be saved says why (`problems`), in plain sentences; Save stays off until it can be, and while the formula is unchanged.
- **The result is tried before it is saved** through `POST .../preview`, with the inputs the formula read.
- **Writes are direct and online, not commands.** A formula is a separate resource with its own `If-Match`, and its effect (the value of a stat on every entry below) cannot be shown from the mirror. Save, Remove and the vocabulary calls go to the API at once; offline they say so. A stale `If-Match` reloads the entry's formulas and says it changed. These join the outbox with the offline work (B4).
- **Changing an inherited formula** starts a draft on the selected entry; saving gives that entry a formula of its own.
- **The vocabulary:** a stat is made with a name, a kind of value (whole, decimal, text, tag, one of a list), and a group (an existing one, or a new one made in the same step). A stat is deleted after asking twice, and only when no formula reads it (`.../dependents`). It **cannot be renamed** (K6): the form says so.
- **The store** (`core/formulaStore.ts`) reads the formulas of an entry and of its ancestors once and finds the one that applies, own first, then parents in order.

## Consequences

- Formulas read on the server are not shown inside the stat values of the mirror until the entry is read again.
- No bulk view of "every formula in the repository" until K7 exists.
