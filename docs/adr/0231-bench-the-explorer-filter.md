# 0231 - Bench: the explorer filter

Status: accepted, decided with the maintainer on 2026-10-09. A follow-up to [ADR 0230](0230-bench-the-explorer-tree-and-kinds.md) (the explorer as a tree), slice W-D of [RFC 0042](../rfcs/0042-bench-workbench-interface.md); the "Filter entries" field of the prototype.

## Context

The tree of ADR 0230 is drawn from the whole list, so in a repository of a few hundred entries finding one means folding and scrolling.

## Decision

- **A "Filter entries" field** at the top of the explorer. What is typed lists the entries whose name contains it, **flat and by name**, whatever the order is set to: when looking for an entry, where it sits matters less than finding it, and a tree of matches would have to show their parents to make sense. Clearing the field (or Escape in it) brings the order back.
- **The match is a substring of the name**, ignoring case and accents, on this device, over the list the explorer already has. It does not read descriptions, and it does not call the API: `GET .../entities?q=` exists (ADR 0215) but the list is already here, and a local match answers as each letter is typed, including for entries made and not yet sent.
- **The count says it**: "3 of 11 entries". With no match the pane says "No entry matches that filter."
- **The filter is not remembered**, nor kept when another repository is opened: it is a search, not a setting. The order is, as before.
- **Typing is not interrupted** by the redraws the pane makes when something else changes: the field keeps its focus and its text.

## Not here

- Matching descriptions, kinds or parents (a filter by kind, "under X"). The kind order and the tree already answer those; a richer filter waits for the bulk export of RFC 0039 (W3), which brings the bodies to the device.
