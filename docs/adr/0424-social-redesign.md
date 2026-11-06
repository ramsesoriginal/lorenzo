# 0424 - Lorenzo Social, designed

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/social](../design/web/social/README.md), SO1 to SO8, and D30. This is the interface design that [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md) asks for in "For the interface design"; it adopts [ADR 0408](0408-lorenzo-social-the-app.md)'s mock-up clause for the icons, and the two kind icons are added to the atlas by the scaffolding slice.

## Context

Lorenzo Social is a new app: relationships between entries, standings as stats, saved social webs, a graph, a matrix and a date lens. RFC 0049 gave the data and the rules and asked for an interface design.

## Decision

- **Social is in World with the chord G then O** (SO1, D30). Its tabs are Webs (Home: the list of webs with Continue), Relationships, Types and standings (authors) and Problems (staff); a person who may not write sees the first two.
- **One web is one page with three views** (SO2, SO6): Graph, Matrix and List, sharing the members, the toolbar, the lens and the panel, and the selection. The graph fills the page and the controls float over it, as a map does: a vertical bar of region switches (Labels, Groups, Types, Steps, Focus, As of an Event, As read by) at the right, the legend, zoom and layout, and a panel that slides in to the left of the bar (SO7). **Members** adds by name, a group's members, or everyone within some steps, and writes explicit rows; a web shows exactly the entries added. **Focus** dims everything but the selection and its neighbours.
- **A standing is a number, a quiet bar and a mark and a word per state** (SO3): inherited, derived, unknown and two-fill-one-cell, each with a legend; none relies on colour.
- **The date lens and "as read by" are switches with a line** (SO4) that says what is on and clears it; unknown is dotted in the graph and worded "unknown as of this Event" in the list and matrix; an unreadable thing is absent.
- **The matrix edits where the cell is** (SO8): a click selects, a second click or typing edits, clicking away or Tab or Enter saves a draft, the save bar batches, and a refused cell keeps its reason; an empty cell creates a restricted relationship of the chosen type.
- **A phone** has Graph (read-only), Standings (one entry's list in place of the matrix) and List, and opens a page for a selection.
- **Icons** (SO5): a Relationship is two overlapping rings (new); a Social web, and the app, is `icon-social`.
- **The graph's grammar** is identity §18 (solid direct, dashed derived or through, dotted unknown, an arrowhead for direction, selection as a fill and never a new shape); the type of a relationship is told by its label and never by a line style.

## Consequences

- The renderer package and its layout engines are RFC 0049's; the prototype's graph is a stand-in.
- A matrix of hundreds of members is windowed in the real app and not in the prototype.
- No total of standings is shown: the server adds nothing up, and a total would be worded "from what you can see" (not offered).
