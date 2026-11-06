# 0414 - The palette and the keyboard model

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D25, and the keys in MP7.

## Context

There is one command surface in Bench and none in the other apps, and no shared keyboard model.

## Decision

- **One palette** for entries across apps, apps ("Go to") and actions, with Tab narrowing it (Everything, Entries, Apps, Actions). **Ctrl K** (Cmd K on a Mac) opens it. Centered with a preview of the selected entry on large and desktop screens, centered without a preview at the tablet step, a full screen on a phone. In a rich-text editor **Ctrl K** inserts a link to an entry and **Ctrl Shift K** opens the palette.
- **Shortcuts:** `?` lists them. Go to is **G then** H (home), S (Sessions), B (Beings), I (Inventory), C (Calendars), M (Maps), W (Writing), O (Social), R (Bench), A (Account), L (library switcher), T (theme). In a list, J and K move, Enter opens, X selects, Shift J selects a range, N is new, E is edit and `/` filters.
- **A switch turns off single-key shortcuts** (WCAG 2.1.4); shortcuts with Ctrl always work. The keys may be remapped by a person; Maps' tool keys are remappable from the start, a key in use is refused with the reason and the chord key G is refused for other tools.
- **Ctrl L and Ctrl Shift T are reserved by browsers** and are not used.

## Consequences

- The palette needs a search across apps; the prototypes match on names only.
- A tool registry in an app (Maps) is the contract for its keys, so a new tool adds one entry and no screen.
