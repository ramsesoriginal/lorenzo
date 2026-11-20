# 0524 - Beings and Inventory move into the web shell

Status: proposed, 2026-11-20. Slice UI-F of [RFC 0050](../rfcs/0050-the-web-interface.md) ([issue #1017](https://github.com/ramsesoriginal/lorenzo/issues/1017)) for Beings and Inventory. The designs are [docs/design/web/beings](../design/web/beings/README.md) (BN1 to BN10, decided in [ADR 0422](0422-beings-redesign.md)) and [docs/design/web/inventory-web](../design/web/inventory-web/README.md) (IN1 to IN12, decided in [ADR 0423](0423-inventory-redesign.md)). This ADR says how the two apps are moved to them, in what order, and what is to be settled first. It follows [ADR 0440](0440-calendars-moves-into-the-web-shell.md), [0441](0441-sessions-moves-into-the-web-shell.md), [0465](0465-maps-moves-into-the-web-shell.md) and [0494](0494-writing-moves-into-the-web-shell.md). Nothing here is built; the questions at the end are for the maintainer.

## Context

Both apps are the oldest of the web apps and still draw their own header and footer (`SiteHeader`, `SiteFooter`) in a `Base` layout. The shell (`packages/app-shell`: `AppPage shell="web"`, the apps sheet, palette, status bar, templates, states, dialogs, toasts) is used by the account hub, Calendars, Sessions, Maps and Writing.

**Beings** (about 10,000 lines, 15 end-to-end specs): a list of beings; a being's page with three modes (Read, Play, Edit) and a sticky bar of pinned numbers; a datasheet layout; steppers and a client-side undo stack in Play; hand over and delete; notes, relationships, events and facts pages. The design replaces Edit as a mode with editing in place on each section, adds a rows / cards / side-by-side list (and a datasheet view of it), puts the mode switch, the pinned numbers and the active conditions in one band, adds a "Change by" adjuster and a History (thirty steps, with who made each), and remembers the last mode per being for the person who plays it.

**Inventory** (about 16,000 lines, 23 specs): the board (columns of cards, drag and drop, selection, give, split and merge, setting down, undo), the catalog, Unsorted, item pages, the GM's views. The design keeps the board ("a minimal redesign") and moves the pages around it: the board as Home with Catalog and Unsorted as tabs, a switcher for the board's name, columns that show their weight and room left, one column at a time on a phone with "Move to…", an item opened in a panel (a sheet on a tablet, the page on a phone), a drag ghost with refusals in words, and the catalog and item page edited in place with a save bar for what can break links.

The two apps carry near-identical copies of several components (`DescriptionEdit`, `DescriptionEditor`, `Facts`, `FactPage`, `InfoForm`, `LibraryList`, `SlugEditor`, `TagEditor`, `SiteHeader`, `SiteFooter`), which is a reason to look at what the move can share.

## Decision (proposed)

- **The frame is the web shell** (`AppPage shell="web"`) in both apps, with the palette, the apps sheet and the status bar the shell's. Inventory's tabs are Board, Catalog and Unsorted (a GM's); Beings' are the list and a being's page, with Facts as the old apps have them. The notification bell moves to the shell's account menu (ADR 0423).
- **Two stacks of pull requests, independent of each other** (each on `main`, each PR on the one before it in its own stack, tested and green), so either can go first and they can overlap:

| PR | Inventory (ADR 0423, IN1 to IN12) | PR | Beings (ADR 0422, BN1 to BN10) |
| --- | --- | --- | --- |
| I0 | The frame: the shell, the tabs, the account menu; the old header and footer go from this app | B0 | The frame: the shell, the list and the page inside it; the old header and footer go from this app |
| I1 | The board as Home with its switcher and the last board remembered (IN1, IN7); columns that show weight and room left (IN8, IN11); the board fills the page (IN9) | B1 | The list as rows and cards, one switch, remembered, with the search, filters and Mine (BN1) |
| I2 | A phone shows one column at a time, with "Move to…" (IN2) | B2 | The list side by side, with its own Read and Play, and the datasheet as a third view (BN4, BN8) |
| I3 | An item opens in a panel: a sheet on a tablet, the page on a phone; actions on the card and in the panel with the shell's bulk bar and Undo toast (IN3, IN4) | B3 | The page's band: Read and Play as modes, the pinned numbers, a line saying what each is for, the active conditions, the last mode per being (BN2, BN5, BN7, BN10) |
| I4 | The drag ghost, the column highlight and the refusals in words; the gold ring on Equipped and Not carried (IN10, IN12) | B4 | Editing in place on each section, with its own save, and no page-level Edit mode (BN2) |
| I5 | The catalog and the item page: descriptions and notes in place, the structure behind a save bar (IN5) | B5 | Steppers with "Change by", the shell's Undo toast, and the History (BN3, BN9) |
| I6 | The GM and author features on the new frame: any board, a group's, the unowned; make an item; reassign, unassign, delete; Unsorted and unpacking (IN6) | B6 | The datasheet as a layout switch of the page (BN4) |
| I7 | The audit against the design | B7 | Hand over, Delete being and the add-note dialogs; the rule that a note a person may not read is absent (ADR 0422) |
| | | B8 | The audit against the design |

- **What does not change:** the API and its rules for who sees which being, item and note; the board's drag-and-drop behaviour and the checks behind it (ADRs 0131 and 0134); the library's Settings that say which stats are pinned, adjustable or derived.
- **What is retired as each app moves** (UI-H's work for these two apps, done inside each stack): the app's own `SiteHeader`, `SiteFooter` and button styles.
- **The usual process:** one tracking issue and one milestone for the ADR; each PR with its labels, assignee, milestone and links; an end-to-end scenario for each behaviour that changes; the axe, dark-mode and 44px checks on the new pages; the "Checked against the design" table below filled in as each slice lands, with every difference from the design written down on purpose.

## Questions for the maintainer

1. **Which first?** Recommended: **Inventory first.** It keeps its board, so the frame and the panels are the work and the risk is small; Beings changes how people play at a table and deserves a fresh head. The stacks do not depend on each other, so the other order, or both at once, are possible.
2. **Is "no Edit mode" still wanted?** ADR 0422 says so; it removes a mode that today's sheet and its tests are built around. Recommended: yes, as decided.
3. **Share the duplicated components first, or move the apps and share afterwards?** Recommended: **move first, extract afterwards**, so that no PR changes two apps' behaviour at once; the copies are noted in each stack's audit PR and a package follows if they are still copies then. The alternative is a package PR before B0 and I0.
4. **The History's "who made each step" (BN9).** Today's undo is a client-side stack of the person's own steps. "By Ana, 17:12" for steps made by others at the table needs a read of who changed a stat and when (the API has an audit log; whether a player may read it for a being they play is to be checked). Options: (a) the person's own steps only, "by you", with others' steps added when the API can give them; (b) an API slice first (a read of a being's recent stat changes, like the shared-with-me read of ADR 0494) so the History is complete from the start. Recommended: (a), with (b) as its own later slice.
5. **Side by side with forty beings** is untried (the design says so). Recommended: build it with the list as it is now, and add windowing only if it is slow in a large library, as RFC 0050 allows.
6. **Where do the old pages go?** Beings' fact pages and Inventory's debug page (`/debug/me`) predate the design. Recommended: Facts keep their pages in the new frame; the debug page is dropped from the app and the apps list. Say if you want it kept.

## Checked against the design

Filled in as each slice lands.

| Part | Slice | State |
| --- | --- | --- |
| The frame, the tabs | I0, B0 | Not built |
| The board's switcher and weights | I1 | Not built |
| One column on a phone | I2 | Not built |
| The item panel and actions | I3 | Not built |
| The drag ghost and the ring | I4 | Not built |
| The catalog and item page | I5 | Not built |
| The GM and author features | I6 | Not built |
| The list: rows, cards, side by side | B1, B2 | Not built |
| The band, Read and Play | B3 | Not built |
| Editing in place | B4 | Not built |
| Steppers, Change by and History | B5 | Not built |
| The datasheet | B6 | Not built |
| The dialogs | B7 | Not built |
| The audits | I7, B8 | Not built |

## Consequences

- When it is built, Beings and Inventory use the shell, and UI-H (retiring each app's own header, footer and button styles) is left only for Social.
- The Writing, Maps, Calendars and Sessions shapes are the pattern; no new shell component is planned. If the board or the band turns out to need one, it is proposed in its own ADR.
