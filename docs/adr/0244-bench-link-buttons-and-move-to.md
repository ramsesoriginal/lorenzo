# 0244 - Bench: link buttons and "Move to…"

Status: accepted

## Context

Two small things left over from W-C and W-D of [RFC 0042](../rfcs/0042-bench-workbench-interface.md): inserting a link without knowing to type `[[`, and moving an entry under another without the parents editor. Dragging in the tree is not part of this.

## Decision

- **Two buttons over every text** (a description, a note, a new note): "Link to an entry" and "Show a picture". Each writes `[[` or `![[` at the caret, in front of what was selected, and leaves the caret after it, so the entry picker of [ADR 0235](0235-bench-the-entry-picker.md) opens straight away and searches for what was selected. They reuse the picker; they do not write a link of their own. Pressing a button does not take the focus from the text.
- **"Move to…" in the explorer**, for the selected entry (not one that changes its parent in its own way, an inventory item). It makes the chosen entry the entry's **only parent**, or with "Top level (no parent)" none, as one `entry.set-parents` command: sent in order with the rest, undone with Undo. The entries offered leave out the entry itself and everything under it, since a parent under its own child would be a loop, and the entry's present only parent.
- With more than one parent, "Move to…" replaces all of them. Removing or adding one of several stays in the parents editor on the entry.

## Not in scope

Dragging an entry in the tree, which also needs a place to drop and a choice of which parent a drag leaves.

## Consequences

- No new API use; a move is the parents write that already exists.
