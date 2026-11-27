# 0527 - Social moves into the web shell

Status: accepted and built, 2026-11-26, after the maintainer chose the scope (below). Slice UI-G of [RFC 0050](../rfcs/0050-the-web-interface.md) ([issue #1018](https://github.com/ramsesoriginal/lorenzo/issues/1018)). The design is [docs/design/web/social](../design/web/social/README.md) (SO1 to SO8, decided in [ADR 0424](0424-social-redesign.md)). This ADR says how the app is moved to it, in what order, and where it differs from the design on purpose. It follows [ADR 0440](0440-calendars-moves-into-the-web-shell.md), [0441](0441-sessions-moves-into-the-web-shell.md), [0465](0465-maps-moves-into-the-web-shell.md), [0494](0494-writing-moves-into-the-web-shell.md) and [0524](0524-beings-and-inventory-move-into-the-web-shell.md).

## Context

Social ([RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md), [ADR 0408](0408-lorenzo-social-the-app.md)) is built and tested end to end against the real API, but in the old interface. It is the last app on the old page frame (`AppPage` without `shell="web"`, with the header and footer of the first shell), which is what UI-H, the retiring of each app's own header, footer and button styles, waits for. The shell already lists it (World, beside Calendars and Maps, with its icon `icon-social`), and the atlas has both kind icons (`icon-kind-relationship` and `icon-kind-social-web`, [follow-ups](../design/web/follow-ups.md)).

What exists, about 6,000 lines in 49 files, the pages drawn imperatively by four large view files (`web-view`, `matrix-view`, `views`, `types-view`):

- **Libraries** as Home, then **Relationships** (a searchable list, and a form that makes one from two ends, a direction, an optional type and an audience) and one relationship's page (the sentence, what it holds, swap the ends, one way or both, who may see it, delete, and its notes).
- **Types and standings**: the tree, the scales, a starter set offered to an empty library.
- **Webs**: a list, and a web drawn as a graph with six layouts by `@lorenzo/graph-renderer`, with the date lens and "as read by" in the address, and members written as explicit rows.
- **The matrix** as a page of its own, with drafts, a save bar, a conflict cell and, on a phone, one entry's standings as a list.
- **Notes** on a relationship and on a web.

What the design has that it does not:

| In the design | In the app |
| --- | --- |
| Webs as Home, with Continue (SO1) | Libraries are Home; Webs is a tab |
| One page per web with Graph, Matrix and List sharing members, lens, panel and selection (SO2) | The graph page, the matrix page and the list are three pages |
| Controls floating over a full-width graph: a vertical bar of region switches, legend, zoom, a sliding panel (SO6, SO7) | A page of forms above the graph |
| Focus (SO7) | None |
| A Members control: by name, a group's members, everyone within some steps (SO6) | Add by name |
| Standing as a number, a quiet bar and a mark and word per state, with a legend (SO3) | A number |
| The lens as switches with a line that says what is on (SO4) | Fields in a form |
| Matrix editing where the cell is, with the keys of SO8 | Drafts and a save bar; the keys are partly there |
| Problems, for staff | None (the API has `GET /relationship-problems`) |
| An entry's own social page | None |
| The mascots `empty-social-types`, `empty-relationships`, `empty-social-web` | Plain empty text |

## Decision

- **The frame is the web shell** (`AppPage shell="web"`), as in the other apps: the header, the apps sheet, the palette, the status bar and Undo are the shell's. Home is Webs; the tabs are **Webs**, **Relationships**, **Types and standings** (writers) and **Problems** (staff); the old Libraries page is replaced by the shell's library switcher (SO1). A web is the `workspace` template, the lists and forms are `list-detail`.
- **Scope, chosen by the maintainer 2026-11-26: move what exists, then add Problems and the entry's page.** So the design is complete when this is built, and nothing that exists is lost on the way.
- **A stack of pull requests, each on the one before and each tested and green** (below). A PR draws only what the API already gives, and what it moves keeps its end-to-end scenarios (they are moved onto the new interface, never deleted).
- **The behaviour does not change.** What a person may see and write, the refusals, the 412s, the drafts, the audiences and the notes are as built. Old addresses keep working: `/matrix/` and `/webs/` redirect to the web page and Home with the same query; `?as_of=` and `?as_seen_by=` stay the address of the lenses.
- **One web, one page.** The view is `?view=graph|matrix|list`, kept in the address, with the same selection across views. The graph is full width with its controls floating over it, as a map's are.
- **The renderer is not changed.** `@lorenzo/graph-renderer` keeps its layouts, themes and Scene; the page changes around it. Where the design asks something of it (Focus dims all but the selection and its neighbours), that is a small addition to the renderer and its tests, in the slice that needs it.
- **App-specific CSS stays in one file** with brand tokens only and the existing guard test; where a class is the brand's, the app uses it (ADR 0526's lesson: the class-clash test in `apps/brand` is run on every app).
- **The date lens chooses its Event with the shared time filter and the Events list.** The strip of `@lorenzo/time-filter` (a calendar and its year; a range of its days keeps the Events dated in it, through `GET /events`'s period filter, [ADR 0442](0442-the-events-list-filters-by-period.md)), a search by name, and the Events as the API orders them: in story order unless asked for by name. The strip's ticks were not drawn at first (they needed every Event's dates read one by one); they are now, from one read of the year (`GET …/events/dated-days`, [ADR 0530](0530-a-calendars-current-date-and-where-events-are-dated.md)). What the strip and the list both need beyond drawing (the segments of a year, the period to ask for) is in the package, `stripOf` and `periodQuery`, and Calendars' Events list uses the same.
- **Shared parts.** Social imports no part from Beings or Inventory; a note's form is the information editor's, as now. If a second part turns out to be a copy, it follows ADR 0526's route and is extracted, not copied.

## The stack

| PR | What it does | Needs |
| --- | --- | --- |
| G0 | **The frame.** `AppPage shell="web"`, the tabs with their icons, the status bar, the legal links kept; the pages sit inside it unchanged (Libraries stays Home until G1). This ADR is accepted here and the tracking issue and milestone are made | nothing |
| G1 | **Webs.** Home as Continue, then the list of webs, and the Libraries page goes (the shell's library switcher replaces it); a new web (`empty-social-web`); rename, and delete behind a confirmation that says what goes and what stays (a web's delete cannot be taken back, so Undo is not offered); the shell's states | G0 |
| G2 | **Relationships.** The list (a sentence for each, the search and the filters it has), the form as a dialog, and a relationship's page (SO3's standing marks, who may read it, the webs that name it, delete with Undo) with its notes (`empty-relationships`) | G0 |
| G3 | **Types and standings.** The tree with how each type reads, the scales, the starter set (`empty-social-types`), the refusals for a scale existing values would break | G0 |
| G4 | **One web, the graph.** The `workspace` page with the Graph, Matrix and List switch, the floating controls (the vertical bar, the legend, zoom and layout), the sliding panel for an entry or a relationship, and the selection that carries across views; Focus | G1, G2 |
| G5 | **Members and Connect.** The Members control (by name, a group's members, everyone within some steps, removing) and connecting two entries from the page, with the refusals in words | G4 |
| G6 | **The lenses.** The date lens and "as read by" as switches with a line that says what is on and clears it; unknown dotted and worded; the count of what is not drawn, with its switch | G4 |
| G7 | **The matrix in the web.** The matrix as a view of the web (SO8's keys, SO3's number, bar and marks with the legend, the save bar, the conflict cell, the presence mode); on a phone one entry's standings as a list | G4 |
| G8 | **Problems.** Staff see the doubled relationships, the chains whose ends do not meet and the groups that disagree, from the API's `relationship-problems` read | G0 |
| G9 | **An entry's social page.** The entry's relationships grouped by type with to and from, a group's members apart, its standings edited in place; reached from a web, a relationship and the palette, and by an address other apps can link to | G2 |
| G10 | **The pass.** Phone and tablet (the graph read-only, a page in place of the panel), the 44px targets, axe in both themes on every page and state, the docs (`v1.0.md`, the apps README), UI-G closed and UI-H unblocked | G1 to G9 |

Each PR names the one below it. The pull requests are listed in the tracking issue.

## Questions

None are open: the design's questions were answered in [ADR 0424](0424-social-redesign.md), and the scope was chosen on 2026-11-26.

## Checked against the design

Filled in as each slice lands.

| Part | Slice | State |
| --- | --- | --- |
| The frame, the tabs (SO1) | G0 | Built: the shell's header with the tabs and their icons (Libraries, Relationships, Webs, Types and standings; Problems comes with G8), the status bar and the apps sheet; the pages are unchanged inside it. The shell's status bar is a labelled region, so the pages pass axe's landmark rule without the check being turned off |
| Webs as Home (SO1) | G1 | Built: Home opens the library's webs (the last library, or the only one), with Continue, a New web dialog (`empty-social-web`), rename in a dialog, delete behind a confirmation (no Undo: the API deletes for good) |
| Relationships and a relationship (SO3) | G2 | Built, but for the webs that name a relationship (the API has no read for it yet): the list, New relationship as a dialog, `empty-relationships`, standings with number, bar and word (SO3), delete behind the shell's confirmation |
| Types and standings | G3 | Built: the page already told how types read, the scales and the refusals; the empty library now shows the `empty-social-types` mascot with the starter set as its one step |
| One web: the graph, the switch, the panel, Focus (SO2, SO6, SO7) | G4 | Built: the `workspace` page with the drawing full width; a vertical bar of Labels, Focus, Drawing, Date and reader, Members and Notes; a sliding panel that opens on a selection and keeps its tab across redraws; a legend; zoom; Graph and List in the address (`?view=`). Focus is the renderer's existing `dim` on nodes, so the renderer is unchanged. The Matrix is still its own page until G7. The lens line (SO4) and the Members dialog (SO6) are in their first form here and are G5 and G6 |
| Members and Connect (SO6) | G5 | Built: Members is a dialog (by name, a group's members, everyone within one to three steps of the selected entry, and taking out), each write under the web's current version and never doubling a member; Connect makes a relationship from the page with an optional standing refused outside its scale, and adds its ends to the web. The old Members card of the panel is gone; the panel keeps Types |
| The lenses (SO4) | G6 | Built (the Event is chosen with the shared time filter and the story-ordered list, see the audit below): "As of an Event" and "As read by" are switches in the bar (on says so; a second press clears; off opens their controls), each with a line saying what is on and a Clear; what the date lens leaves out is counted with a "List them" switch that lists them and draws them faded; an unknown relationship is dotted in the graph and "Unknown as of the Event" in the list. |
| The matrix in the web (SO3, SO8) | G7 | Built: Matrix is a view of the web (`?view=matrix`), and `/matrix/` carries on to it; a standing shows its number, a quiet bar on the stat's scale (hatched below zero) and, when inherited, a word, with a legend; a first click selects and a second edits where the cell is, Tab saves the draft and moves right, Enter down, Escape cancels, typing starts an edit; drafts, the save bar, the conflict cell and the presence mode are as built; on a phone the view is called Standings and is one entry's standings as a list. Drafts are not kept if a lens or the members change and the web is drawn again (the save bar says how many there are). Delete still asks with the browser's own prompt: G10 |
| Problems | G8 | Built for what the API can say: staff see chains whose ends do not meet (the API's `relationship-problems`, the one kind it reports) and doubled relationships (worked out here from the relationships the reader may see: the same ends, either way round for a two-way one); a library with none says so with the `caught-up` mascot, and a player gets one sentence. "Groups that disagree" is not built: nothing says what it means yet, and the API does not report it |
| An entry's social page | G9 | Built at `/entry/?tenant=&id=`: its relationships grouped by type (one read a type), each with the other end, With, To or From, who may read it and its standing, written in place by those who manage relationships (inside the scale, refused in words); a group's members apart; reached from a relationship's page and from a selected entry's panel in a web. The palette finds any entry and opens its page. Not built: an entry in another app linking here (no app asks yet) |
| Phone, tablet, audits | G10 | Built: on a phone the web page flows (head, view, bar, drawing, panel one after another) instead of floating; the legend belongs to the drawing only; one audit spec visits every page on desktop, phone and tablet: axe in both themes (with the panel, Members and Connect open), nothing scrolling sideways, and every button, select and field at least 44px on a phone; the matrix's Delete asks in the shell and not in the browser |

## Audit against the design and the old app (2026-11-26)

After G10 the built app was checked item by item against [the design](../design/web/social/README.md) (SO1 to SO8 and the prototype's lists), against the old app on `main` and against [ADR 0408](0408-lorenzo-social-the-app.md). Every scenario of the old app's five specs is still there. What the audit found and what was done:

### Lost or wrong, now fixed

- **No way to switch library.** The Libraries page went and the shell's switcher was never fed. The shell now gets the person's libraries (and Home carries on to the last one used).
- **Swapping a relationship's ends, or changing its direction, cleared its since and until.** The API replaces them with the rest; the page sent neither. It now sends what the relationship had. (The old app did the same.)
- **Types and standings and Problems were tabs for everyone** (SO1 says a person who may not write sees Webs and Relationships). They now show for those who write.

### In the design, missing, now built

- The relationships list narrows by type (and what inherits from it) and by an end, which may be a group.
- The web's panel says what a relationship is: its type, who may read it, since and until, each standing with its scale and where it comes from (written in place, refused in words, with Undo), the chain it holds through; and for a group, its members apart. A row of the List view selects it in the panel and in the drawing.
- The bar has Groups (outlines) and Steps (All, 1, 2 from the selection); radial draws from the selected entry; a web can show a standing on its lines (their weight, and a label), chosen in Drawing and saved with it.
- A relationship's page sets and clears since and until, and shows, adds to and takes out of the chain it holds through.
- The matrix reads as of the date lens and as read by; a relationship not known as of the Event is dotted and worded; a stat with no scale is drawn against the values in view and the legend says so.

### Built after the first audit pass

- The date lens chooses an Event from the shared time filter and the Events in story order, as the design says, and Calendars and Social now share one reading of the strip.
- Edge labels name the type and the standing; a relationship that holds through a chain is dashed (read when the web is drawn, for webs of up to 100 entries and 60 relationships; a larger web is drawn without).
- The renderer gained a Fit, placing by hand with Alt and the arrow keys (Shift for a bigger step), a pinch on a phone and a faded edge (what the date lens leaves out is drawn faded when asked for, as well as listed); an entry in the hand-placed layout is also placed by X and Y fields in the panel.
- The selection carries into the matrix (its row is marked and its cell has the focus); the matrix orders by group.
- The relationships list finds by a standing and the numbers it lies between (worked out in the page: the list read has no such filter).
- The palette (Ctrl or Cmd K) and the go-to keys are fed: Webs, Relationships, Types and standings, Problems, New web, New relationship, and any being or group, which opens its page. The app had never called the shell's palette.
- A relationship's page lists the webs that name it: the webs list read gained `names=<relationship>` (webs with both ends as members; a relationship the reader may not see names none), and the API client was regenerated.

### Built after a second audit against the design's own screens

- A web on the Webs home is a card: a small drawing, its name, "N entries · M relationships", who may read it and a menu (Rename, Delete); Continue is the same card.
- Every standing the library has is read on a relationship, in its page and in the web's panel: its value as a number, a bar and a word, its scale (or that it has none and is shaded across the visible range), where an inherited value comes from, and for those who may write a field to set it where it is read, even when it has no value yet, refused outside the scale, with Undo (which clears a value that was new).
- A row of the relationships list says its type and its standing; the filters are one wrapped row (name, type, an end, a standing and the numbers it lies between).
- An entry's page has New relationship (this entry as the first end), "Back to the webs", and says what the entry is.
- The matrix marks a standing that holds through others as derived, as the design does.
- On a web, Members sits beside the view switch, and the layout and Connect with the zoom; the legend draws a sample of each line; the Types switch says how many types the web is limited to.

### In the design, still not built

- "Groups that disagree" in Problems: the design's example is a relationship that says an entry is a member of a group the group does not hold, which depends on what a library's types mean (no type is built in), so nothing defines it yet. Doubled relationships are worked out in the page, not reported by the API.
- Links to an entry's page from other apps: none asks for one yet.

## Consequences

- When it is built, every web app is on the shell, and UI-H (retiring each app's own header, footer and button styles) is what is left.
- `apps/social`'s four large view files are cut into the components of the pages they draw, as Calendars and Maps were; the end-to-end scenarios (24 in five specs) are the net under that work.
- The graph's pointer and keyboard behaviour is the renderer's and is not touched; what changes is where its controls are and what they are called.
- The slices are independent enough that a stop after any of them leaves a working app: G0 alone already puts it in the shell.
