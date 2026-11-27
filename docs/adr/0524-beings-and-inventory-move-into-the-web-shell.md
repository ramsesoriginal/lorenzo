# 0524 - Beings and Inventory move into the web shell

Status: accepted, 2026-11-20, with the maintainer's answers to the six questions (below). Slice UI-F of [RFC 0050](../rfcs/0050-the-web-interface.md) ([issue #1017](https://github.com/ramsesoriginal/lorenzo/issues/1017)) for Beings and Inventory. The designs are [docs/design/web/beings](../design/web/beings/README.md) (BN1 to BN10, decided in [ADR 0422](0422-beings-redesign.md)) and [docs/design/web/inventory-web](../design/web/inventory-web/README.md) (IN1 to IN12, decided in [ADR 0423](0423-inventory-redesign.md)). This ADR says how the two apps are moved to them, in what order, and where it differs from the design on purpose. It follows [ADR 0440](0440-calendars-moves-into-the-web-shell.md), [0441](0441-sessions-moves-into-the-web-shell.md), [0465](0465-maps-moves-into-the-web-shell.md) and [0494](0494-writing-moves-into-the-web-shell.md). The Inventory stack is built (see the table below); the pull requests are listed in the tracking issue.

## Context

Both apps are the oldest of the web apps and still draw their own header and footer (`SiteHeader`, `SiteFooter`) in a `Base` layout. The shell (`packages/app-shell`: `AppPage shell="web"`, the apps sheet, palette, status bar, templates, states, dialogs, toasts) is used by the account hub, Calendars, Sessions, Maps and Writing.

**Beings** (about 10,000 lines, 15 end-to-end specs): a list of beings; a being's page with three modes (Read, Play, Edit) and a sticky bar of pinned numbers; a datasheet layout; steppers and a client-side undo stack in Play; hand over and delete; notes, relationships, events and facts pages. The design replaces Edit as a mode with editing in place on each section, adds a rows / cards / side-by-side list (and a datasheet view of it), puts the mode switch, the pinned numbers and the active conditions in one band, adds a "Change by" adjuster and a History (thirty steps, with who made each), and remembers the last mode per being for the person who plays it.

**Inventory** (about 16,000 lines, 23 specs): the board (columns of cards, drag and drop, selection, give, split and merge, setting down, undo), the catalog, Unsorted, item pages, the GM's views. The design keeps the board ("a minimal redesign") and moves the pages around it: the board as Home with Catalog and Unsorted as tabs, a switcher for the board's name, columns that show their weight and room left, one column at a time on a phone with "Move to…", an item opened in a panel (a sheet on a tablet, the page on a phone), a drag ghost with refusals in words, and the catalog and item page edited in place with a save bar for what can break links.

The two apps carry near-identical copies of several components (`DescriptionEdit`, `DescriptionEditor`, `Facts`, `FactPage`, `InfoForm`, `LibraryList`, `SlugEditor`, `TagEditor`, `SiteHeader`, `SiteFooter`), which is a reason to look at what the move can share.

## Decision

- **The frame is the web shell** (`AppPage shell="web"`) in both apps, with the palette, the apps sheet and the status bar the shell's. The notification bell moves to the shell's account menu (ADR 0423). Each app's own `SiteHeader`, `SiteFooter` and button styles are retired as it moves (UI-H's work for these two apps).
- **Beings first, then Inventory**, as two independent stacks of pull requests (each PR on `main` or on the one before it in its own stack, tested and green).
- **The two apps keep their own copies of the components they share** (`DescriptionEdit`, `DescriptionEditor`, `Facts`, `FactPage`, `InfoForm`, `LibraryList`, `SlugEditor`, `TagEditor`) while they move, so that no pull request changes two apps at once. Once both have moved, a follow-up (its own ADR and PR) extracts what is still a copy into a package.
- **No Edit mode.** A Beings page is Read or Play; a section a person may change has its own edit control and saves as it goes (ADR 0422, confirmed by the maintainer).
- **The History says who made each step, from the start** (BN9). Today a stat-value write is not logged and a stat row only knows when it changed, not by whom (ADR 0084 leaves stat values out of the activity log on purpose, as high volume). So the Beings stack opens with an API slice, its own ADR, that records a bounded history of a being's stat changes (who, when, from and to), written when a number is set, and a read that only people who may see the being can use. It is an exception to ADR 0084 for the table's sake, kept small, and does not feed the admin activity log.
- **Facts pages are kept and made a first-class part of the app** (the maintainer: "quite important"). They move into the frame with the rest, and a Fact and a being each get a **"Where it appears" page**: the incoming links from LorenzoScript (the read of ADR 0110, which exists), and the Scenes and Sessions it takes part in (a read that may need a small API addition; settled in that slice, with its own ADR if so). This is new to the design and is added to it as BN11 in that slice.
- **Inventory keeps its debug page** (`/debug/me`, the raw account data) for debugging; it moves into the new frame as it is, and stays reachable from the account menu in a development library.
- **Side by side with forty beings** is built as the design draws it, with windowing added only if it is slow in a large library.

### The Beings stack

| PR | What |
| --- | --- |
| BA | The API: a bounded history of a being's stat changes, with who and when, and its read (its own ADR) |
| B0 | The frame: the shell, the list and the page inside it; the old header and footer go from this app |
| B1 | The list as rows and cards, one switch, remembered, with the search, filters and Mine (BN1) |
| B2 | The list side by side, with its own Read and Play, and the datasheet as a third view (BN4, BN8) |
| B3 | The page's band: Read and Play as modes, the pinned numbers, a line saying what each is for, the active conditions, the last mode per being (BN2, BN5, BN7, BN10) |
| B4 | Editing in place on each section, with its own save, and no Edit mode (BN2) |
| B5 | Steppers with "Change by", the shell's Undo toast, and the History from BA (BN3, BN9) |
| B6 | The datasheet as a layout switch of the page (BN4) |
| B7 | Hand over, Delete being and the add-note dialogs; the rule that a note a person may not read is absent (ADR 0422) |
| B8 | Facts pages in the frame, and "Where it appears" for a being and a Fact (BN11) |
| B9 | The audit against the design |

### The Inventory stack

| PR | What |
| --- | --- |
| I0 | The frame: the shell, the tabs (Board, Catalog, Unsorted for a GM), the account menu, the debug page kept; the old header and footer go from this app |
| I1 | The board as Home with its switcher and the last board remembered (IN1, IN7); columns that show weight and room left (IN8, IN11); the board fills the page (IN9) |
| I2 | A phone shows one column at a time, with "Move to…" (IN2) |
| I3 | An item opens in a panel: a sheet on a tablet, the page on a phone; actions on the card and in the panel with the shell's bulk bar and Undo toast (IN3, IN4) |
| I4 | The drag ghost, the column highlight and the refusals in words; the gold ring on Equipped and Not carried (IN10, IN12) |
| I5 | The catalog and the item page: descriptions and notes in place, the structure behind a save bar (IN5) |
| I6 | The GM and author features on the new frame: any board, a group's, the unowned; make an item; reassign, unassign, delete; Unsorted and unpacking (IN6); Facts pages and "Where it appears" for an item as for a being |
| I7 | The audit against the design |

- **What does not change:** the API's rules for who sees which being, item and note (apart from BA's new history); the board's drag-and-drop behaviour and the checks behind it (ADRs 0131 and 0134); the library's Settings that say which stats are pinned, adjustable or derived.
- **The usual process:** one tracking issue and one milestone for the ADR; each PR with its labels, assignee, milestone and links; an end-to-end scenario for each behaviour that changes; the axe, dark-mode and 44px checks on the new pages; the table below filled in as each slice lands, with every difference from the design written down on purpose.

## Answers (2026-11-20)

1. **Which first?** Beings first.
2. **No Edit mode?** Yes, as decided in ADR 0422.
3. **Shared components?** The copies stay copies while each app moves; extraction follows.
4. **The History's "who"?** Yes, built in one go: the API slice BA comes first.
5. **Side by side with forty beings?** Built as drawn, windowing only if slow.
6. **The old pages?** Keep the Facts pages (and add "Where it appears" with the incoming links, Scenes and Sessions); keep the debug page.

## Checked against the design

Filled in as each slice lands.

| Part | Slice | State |
| --- | --- | --- |
| The frame, the tabs | I0, B0 | Beings: built (B0, [#1347](https://github.com/ramsesoriginal/lorenzo/pull/1347)). Inventory: built (I0, [#1359](https://github.com/ramsesoriginal/lorenzo/pull/1359)): Board, Catalog and Unsorted (a game master's) are the shell's tabs; the bell shows the unread count and links to the hub's page. Differences: the product icon and the search words ("Search or go anywhere") are the shell's, shared by every app, not the design's house and "Find or go anywhere"; the old Libraries page is replaced by the shell's library switcher |
| The board's switcher and weights | I1 | Built ([#1360](https://github.com/ramsesoriginal/lorenzo/pull/1360)): the board's name is a menu (My characters, My groups, and for a game master the finder and the unowned things); columns say their weight and room left, with the carried weight and its meter; the board fills the width with equal-height columns that scroll inside themselves; "Add an item" is a dialog. Differences: "Add an item" no longer sits under the toolbar |
| One column on a phone | I2 | Built ([#1360](https://github.com/ramsesoriginal/lorenzo/pull/1360)): a row of column names, one column at a time; moving a card is its "…" menu's Move to… |
| The item panel and actions | I3 | Built ([#1361](https://github.com/ramsesoriginal/lorenzo/pull/1361), [#1368](https://github.com/ramsesoriginal/lorenzo/pull/1368)): a panel beside the board on a wide screen, a sheet from the bottom on a tablet, the item's page on a phone; each card has a "…" menu with icons, Add a note and a game master's Reassign…, Unassign and Delete…; Set down and Add a note join Move to… and Give… in the panel; the panel says what the item is made from in chips; Undo is the shell's toast. Select shows a blue bar (Move to…, Give…, Merge, Done) with a box on each card. Differences: the shell has no bulk bar of its own, so the board draws it |
| The drag ghost and the ring | I4 | Built ([#1362](https://github.com/ramsesoriginal/lorenzo/pull/1362)): the lit column, the dashed ghost saying what the move makes or that it joins a stack, the refusal in words (a player cannot drop there; a game master is asked), the dimmed card, a live region for a screen reader; the ring is thinner |
| The catalog and item page | I5 | Built ([#1363](https://github.com/ramsesoriginal/lorenzo/pull/1363), [#1368](https://github.com/ramsesoriginal/lorenzo/pull/1368)): rows across the page with what each is made from, a Public or game-master-only pill and "N made"; New item is a dialog; the item beside the list is, for a game master, written in place: the description saves as you type, the weight, value and tags as you change them, and the link name, what it is made from and the public flag wait for the shell's save bar (a taken name keeps the draft; leaving with something unsaved is refused in words). An item's page is a card with the way back above it. Differences: the item page keeps its own editors rather than the panel's |
| The GM and author features | I6 | Built ([#1364](https://github.com/ramsesoriginal/lorenzo/pull/1364), [#1368](https://github.com/ramsesoriginal/lorenzo/pull/1368)): Make from catalog on the board; Reassign…, Unassign and Delete… in the item's panel and on the card's menu. Any board, a group's, the unowned things, unpacking and the Facts pages were already in the frame. Unsorted is a list with the open group in a panel beside it, with the design's words. Add an item is a form in a dialog (From the list / Not in the list) |
| The list: rows, cards, side by side | B1, B2 | Built ([#1348](https://github.com/ramsesoriginal/lorenzo/pull/1348), then matched to the design in [#1356](https://github.com/ramsesoriginal/lorenzo/pull/1356)): rows are a table (avatar, kind, who plays it, the pinned numbers); cards have an avatar and the first number big; side by side has "Played by", folds a stat's limit into its number, and has Read and Play with steppers and Undo (BN8). Differences: All beings / Mine is a toolbar choice, not two tabs of the shell's header (the shell tells tabs apart by path only); the Campaign filter stays; the `empty-beings` illustration is not drawn |
| The band, Read and Play | B3 | Built ([#1349](https://github.com/ramsesoriginal/lorenzo/pull/1349), [#1357](https://github.com/ramsesoriginal/lorenzo/pull/1357)): the switch, the line saying what each mode is for (and, for someone who may not change the being, who may), the pinned numbers as large tiles (value with its limit, a bar, a pencil, `fx`, steppers in Play), the conditions that are on, the tint and stripe of Play, shrinking, and the mode last used on a being. Differences: About is not closed in Play; with nothing pinned the band is empty |
| Editing in place | B4 | Built ([#1349](https://github.com/ramsesoriginal/lorenzo/pull/1349), [#1357](https://github.com/ramsesoriginal/lorenzo/pull/1357)): no Edit mode; a pencil on each number, "Edit details" in the page's "⋯" menu for name, link name, picture and tags, notes' actions in Read. Differences: About keeps its form with Save rather than saving as you type; name, link name, picture and tags are one disclosure |
| Steppers, Change by and History | B5 | Built ([#1350](https://github.com/ramsesoriginal/lorenzo/pull/1350), with the API read of [#1346](https://github.com/ramsesoriginal/lorenzo/pull/1346), ADR 0525): the shell's Undo toast, "Change by" (`+3`, `-5`, a bare `12` sets), Undo (saying what it takes back) and History (with a count) on the band, with who and when. Differences: "undo back to before" writes the old values as new steps, so what it undid cannot be undone again |
| The datasheet | B6 | Unchanged: it was already a layout of the page, with steppers in Play; its switch is in the Stats header, and above the table in the datasheet layout |
| The dialogs | B7 | Delete being (from the "⋯" menu, the name is typed) and Hand over are dialogs ([#1350](https://github.com/ramsesoriginal/lorenzo/pull/1350), [#1357](https://github.com/ramsesoriginal/lorenzo/pull/1357)); New being is a dialog on the list. Not built: add a note as a dialog (it stays inline), undo of a hand over |
| Facts and Where it appears | B8 | Built ([#1351](https://github.com/ramsesoriginal/lorenzo/pull/1351)): the Facts pages are in the frame; a being and a Fact each have a "Where it appears" page (BN11, added to the design) from the existing backlinks read. The Sessions a being takes part in without being named in their text were built later ([ADR 0531](0531-the-sessions-a-being-takes-part-in.md), UI-H): a group "Sessions it takes part in" on the page. Not built: a "Where it appears" page for an Inventory item (ADR 0528 lists it) |
| The page head and rail (BN6) | B3 | Built ([#1357](https://github.com/ramsesoriginal/lorenzo/pull/1357)): an avatar, the name, "Character · played by Ana · campaign", the "⋯" menu, and a rail with who plays it, the campaign, Hand over, Where it appears and the Events. "Seen by" was built later, from an outer audience on a being ([ADR 0529](0529-an-outer-audience-on-a-being.md), UI-H): a select in the rail for those who may say who sees it, Everyone or the game masters only |
| The audits | I7, B9 | Beings: built ([#1352](https://github.com/ramsesoriginal/lorenzo/pull/1352)): axe, both themes, 390px and 44px on eight pages and states, run again after the design match. Inventory: built (I7, [#1365](https://github.com/ramsesoriginal/lorenzo/pull/1365)): axe on five pages and states, both themes, desktop and 390px; it found one problem in the shell's phone menu, fixed in app-shell. Not audited: the 44px target size |

## After first use

The first week of using the built Inventory found what the specs had not, all in [`apps/inventory-web`](../../apps/inventory-web), and it is fixed:

- Dragging a card redrew the page: every card and the page itself were view-transition groups. Now only the cards moved are named for the transition ([#1375](https://github.com/ramsesoriginal/lorenzo/pull/1375)).
- The board did not use the width of a large screen, and a long column grew the page instead of scrolling. The board is a page template of its own, and the page is exactly the window tall by layout alone (a flex chain with `min-height: 0`, no script that measures heights) ([#1375](https://github.com/ramsesoriginal/lorenzo/pull/1375)).
- Moving, adding, giving and merging fetched and drew the whole board again. A drop now says what it changed from what the board already knows (counts, weights, where a container is), and a fetch of the same board changes the page to match instead of drawing it anew, so nothing flashes, scrolls or loses focus; the select bar's Move to…, Give and Merge and the panel's Give and Merge put the cards in place with no fetch ([#1376](https://github.com/ramsesoriginal/lorenzo/pull/1376), [#1377](https://github.com/ramsesoriginal/lorenzo/pull/1377), [#1378](https://github.com/ramsesoriginal/lorenzo/pull/1378)). A hand over, giving what is inside, and anything that stacked into an identical item still fetch.
- A catalog item written in place listed every tag as a toggle, showed only weight and price, and hid the texts and pictures from what it is made from. It now lists the tags the item has (an inherited one marked as that), every stat with where it comes from (a value typed over an inherited one is the item's own), and the inherited texts and pictures beside the description ([#1379](https://github.com/ramsesoriginal/lorenzo/pull/1379)).

## Consequences

- When it is built, Beings and Inventory use the shell, and UI-H (retiring each app's own header, footer and button styles) is left only for Social.
- The Writing, Maps, Calendars and Sessions shapes are the pattern; no new shell component is planned. If the board or the band turns out to need one, it is proposed in its own ADR.
