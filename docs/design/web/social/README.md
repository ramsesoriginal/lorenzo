# Social: design

A fresh design of Lorenzo Social, a new app, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, Calendars with Sessions, Maps, Beings and Inventory are decided. This page holds the brief, the questions and the decision log for this app.

Status: the prototype is built and ready for review (decisions SO1 to SO8 are logged here).

The app comes from [RFC 0049](../../rfcs/0049-lorenzo-social-relationships-and-social-webs.md) and ADRs 0399 to 0408, written in parallel on the open pull request [#1010](https://github.com/ramsesoriginal/lorenzo/pull/1010). Its section "For the interface design" is the brief this page builds on. Where they differ, the RFC wins until it is changed.

## What the app is for

Social says who is connected to whom and how, which groups hold whom, and how much one being stands with another, in any setting. It draws that as a graph and edits it as a matrix.

- **A Relationship is an entry of its own kind,** between two ends that are entries of any kind (a being, a group, a place, an Event). It is not a Maps connection: a road and a friendship never meet. It has a **type**, which is a prototype entry the library writes (parent of, ally of, patron of), and any number of **standings**, which are stats on the relationship (reputation, honor, faith, familiarity).
- **Direction belongs to the type.** A directed standing is two one-way relationships with a value each; a symmetric one is one two-way relationship, shown in both cells of the matrix.
- **A Social web is a saved view as an entry:** a chosen set of entries, drawn as a graph or read as a matrix. It shows exactly the entries chosen, never a rule.
- **Groups stay membership.** A relationship to a group says a role or a standing and grants nothing.
- **Time is optional.** A relationship may start and end at an Event. A reading *as of* an Event says `holds`, `not yet`, `ended` or `unknown`, from the reader's own recorded order.
- **Nothing is inferred and nothing is added up on the server:** no kinship deduced from a parent, no trust along a chain, no total standing. A chain a relationship is stated to hold *through* is written by an author.

Sources: the RFC and [ADR 0399](../../adr/0399-relationships-the-kind-and-its-two-ends.md), 0400 to 0408 on its branch, and [identity §18](../../brand/identity.md#18-information-visualization-grammar), the grammar for edges.

**What this design does not draw.** How a graph is laid out (the engines, the Scene) and the contract for painting it belong to a package, `packages/graph-renderer` ([ADR 0407](../../adr/0407-the-graph-renderer.md)), written like Maps' renderer. This design draws the stand-in that a prototype needs and everything around it: the pages, the lists, the panels, the matrix, the forms and the words. Bench's Relations view is not redesigned here, and its per-type line styles are not adopted.

## The jobs

| Who | The job | Needs from the data |
| --- | --- | --- |
| A GM preparing | Build a court, a family, a pantheon, a faction web; set how much each stands with each; keep some bonds secret; draw a web to show players | types, standings, audiences, webs |
| A GM during play | Ask "what does Mara think of the Guild, and who is her patron?"; add a tie in the moment; change a standing after a scene | an entry's social page, quick edits |
| A player | Read the webs and relationships they may see | the readable part, with both ends |
| An author of a setting | Define the types, standings and scales once; publish them in a repository | the types screen, scales |
| Staff checking a story | Read a web as of an Event, or as one being may read it | the date lens, "as read by" |
| Anyone | Find a relationship by name, type, end, group or standing | the list |

Roles in play: Author, GM, full-visibility Owner or Organizer (they write relationships in the first slices), the player of a being (reads; writing their own is a later slice), and everyone else (they read what is visible).

## Words

Relationship; type (of a relationship); standing; social web; since and until (Events); "unknown" for a state that is not recorded; "what X may read", never "what X believes"; "in this library". A relationship reads as a sentence: "Mara is the parent of Wren". No type ("friend", "enemy") is built in: the types are the library's data.

## What stays true, whatever it looks like

- **A hidden thing is absent** (D24). No placeholder, no "N more", no gap in a chain, and no difference between an empty matrix cell and a cell whose relationship the reader may not see. A relationship is read only with both its ends.
- **Nothing is inferred and nothing is totalled by the server.** Any sum is worked out in the page from what the reader sees, and is worded "from what you can see".
- **Time is never assumed.** No "now", no default Event. A relationship with no start and no end behaves as if time did not exist. An as-of answer the order cannot decide is `unknown`, drawn dotted, worded "unknown as of this Event".
- **No genre, unit or vocabulary is built in.** No type name, no scale, no standing is a default.
- **The edge grammar is identity §18:** solid is direct, dashed is derived, inherited or indirect, dotted is unknown. An arrowhead means direction. The type of a relationship is told by its label and an icon, never by a line style of its own. Selection is a fill and never changes a shape. Colour never carries meaning alone.
- **Visibility is a neutral badge with an icon and a word** (`icon-private` for restricted), never a colour.
- **A refusal is shown as the API gave it,** next to the cell or field, and the draft is kept. A stale edit (412) keeps the draft and offers a reload. Nothing says "saved" that is not.
- **Everything is reachable without a pointer.** The graph is one tab stop that opens into its nodes; a list of one sentence per relationship is the primary non-visual form and is always available; nothing is hover-only.

## Already decided

- **The shell** (D12 to D29): the header, the app's own Home, the status bar, the palette, overlays, loading, empty and error states, and Undo for what can be reversed.
- **Templates:** list and detail (D21), full width for a graph and a wide table, settings and forms with a save bar for structure, edit in place where it can be seamless.
- **From Maps:** a full-width workspace with panels over it, region switches for what a view shows, the shared time filter for a date lens (CS2, CS7), and the tool-registry idea for a canvas.
- **From Writing, Maps and Beings:** a menu twin for every drag, the shell's Undo toast, "as seen by" wording.
- **Phone, from the RFC:** one breakpoint at 720px; lists, an outline, forms and a read-only graph (pan, pinch, tap to select); the matrix is for a tablet and wider, and a per-being list of standings takes its place on a phone.

## What changes in the shell

This app joins the shell, so these change when its place is decided (Question 1):

- the app list and its groups (D17) and the app grid in the "Apps and about" drawer;
- the go-to chord (G then a letter) and its entry in the shortcuts list and the palette;
- the app's tabs and its Home (D16);
- the illustration list, which gains `empty-social-types`, `empty-relationships` and `empty-social-web` (added with this brief);
- `apps/brand` is not changed: two kind icons are chosen below and listed as a follow-up for the atlas.

## Questions

**1. Where does Social sit in the shell, and what are its tabs?**

*Group and name.* Working name "Social", as the app is "Lorenzo Social".

- **A. World, beside Calendars, Maps and Writing.** It is about the setting: who is tied to whom.
- **B. Play, beside Sessions, Beings and Inventory.** It is used at the table: what does Mara think of the Guild.
- **C. Its own group.**

My recommendation: A. It describes the world, and Beings and Maps already link to it through entries. Go-to chord: **G then O** (relatiOnships is the least bad free letter, since S, B, M, W, R, I, C, H and A are taken); G then N is the alternative.

*Tabs.* The app has its own Home (D16).

- **A. Webs, Relationships, Types and standings (authors), Problems (staff).** Home is the list of webs, with Continue. A web has three views: Graph, Matrix, List.
- **B. Relationships first,** webs a tab; Home is the list of relationships.
- **C. Entry first:** Home is a search for an entry, which opens its social page; webs and the rest are tabs.

My recommendation: A. A web is what a GM shows and returns to, and the types and problems tabs are only for the people who write and check.

**2. How is one web arranged: graph, matrix and list?**

- **A. One page, three views of one web** in a switch (Graph, Matrix, List). The members, the toolbar and the side panel are shared; the page keeps the same selection across views. The graph is full width with the panel over it, as a map is.
- **B. Graph and list side by side,** the matrix a separate page for the same members.
- **C. A graph page only,** with the list and the matrix as panels.

My recommendation: A. The three are different readings of the same members, a person switches between them often, and the list must always be a click away for a screen reader. On a phone the switch has Graph (read-only) and List.

**3. How is a standing shown, in the matrix and on a relationship?**

- **A. A number only,** and its scale in the column header.
- **B. A number and a quiet bar or tint** in the cell, scaled to the standing's minimum and maximum where there is one and to the visible range where there is not (and the page says which). The number is always there, so colour is never the only carrier.
- **C. A number, a tint and a mark** for each state: inherited, derived, unknown, in conflict.

My recommendation: C, in a quiet form. The states matter (RFC: inherited dashed with a word, a conflict that lists both) and each needs a mark that survives greyscale; the tint is the optional layer.

**4. Where do the date lens and "as read by" live, and how loud is "unknown"?**

- **A. Region switches in the web's toolbar,** like Maps' layers: a date lens (an Event, from the shared time filter listing Events in story order) and "as read by" (any being for staff, the player's own for a player), each with a visible chip when on, saying "Looking as of The Wedding" or "As read by Mara".
- **B. A lens panel** opened from one button.
- **C. In the address only,** set from an Event or a being's page.

My recommendation: A, with an always-visible line while a lens is on, because a lens changes what the whole page means. An unknown relationship is drawn dotted in the graph and marked "unknown as of this Event" in the list and matrix.

**5. Which icons stand for Relationship, Social web and the app?**

Candidates are drawn on the atlas grid in [`icon-candidates.html`](icon-candidates.html) and [the images](screens/icon-candidates-light.png): for a **Relationship**, R1 two nodes and a line (in the atlas now as `icon-connection`), R2 two nodes and an arrow (new), R3 two overlapping rings (new); for a **Social web** and the app, W1 a hub and three nodes (in the atlas now as `icon-social`), W2 three linked nodes (`icon-relations`), W3 a mesh of five (new), W4 a ring with a centre (new).

My recommendation: **R3 for a Relationship** (it shows "shared, between" with no direction, which suits a type that may be symmetric or directed, and it does not look like a Maps connection) and **W1 for a Social web and the app**, because it is already in the atlas, so the follow-up is two new names and one new drawing. The new ones are listed for the atlas as a follow-up and are not added by this work. R2's arrow is wrong for a symmetric type; W3 and W4 are too busy at 18px.

Say which, and say if you want other candidates. No answer means "as recommended".

## Decision log

### SO1. Social is in World, with chord G then O, and four tabs

Social sits in the World group beside Calendars, Maps and Writing, with the go-to chord **G then O** (D30). Its tabs are **Webs** (the app's Home: the list of webs, with Continue), **Relationships**, **Types and standings** (authors) and **Problems** (staff). A person who may not write sees Webs and Relationships.

### SO2. One web is one page with three views

A web is one page with a switch between **Graph**, **Matrix** and **List**. The members, the toolbar, the lens and the side panel are shared, and the selection carries from one view to the next. The graph is full width. At phone width the switch has Graph (read-only) and List.

### SO3. A standing shows a number, a quiet tint and a mark per state

In the matrix and on a relationship a standing shows its number always, a quiet tint or bar scaled to the stat's minimum and maximum (or to the visible range where there is none, and the page says which), and a mark for each state: inherited, derived, unknown and in conflict. Each mark survives greyscale and has a word in the legend.

### SO4. The date lens and "as read by" are region switches with a line

Both are switches in the web's toolbar, like Maps' layers. While one is on, a line says so ("Looking as of The Wedding", "As read by Mara") and can be cleared, because a lens changes what the whole page means. The date lens uses the shared time filter, listing Events in story order. An unknown relationship is dotted in the graph and marked "unknown as of this Event" in the list and the matrix.

### SO5. The icons are R3 and W1

A **Relationship** is two overlapping rings (new). A **Social web**, and the app, is a hub with three nodes (the atlas's `icon-social`). The two new kind icons are listed for the atlas as a follow-up and are not added by this work.


### SO6. The web page floats its controls over the graph, with a Members control

Direction A. The graph fills the page and the view switch, the region switches, the legend and the zoom float over it, with the panel sliding in from the right. From direction C comes the **Members** control: a dialog to add entries by name, add a group's members, add everyone within some steps of the selected entry, and remove members. It writes explicit rows and never a rule.

### SO7. The controls on the right are a vertical bar, and the graph has a Focus

The region switches (Labels, Groups, Types, Steps, Focus, As of an Event, As read by) are a vertical bar at the top right, each a chip with an icon and its word. The panel slides in to the left of the bar and the bottom-right controls move left of the panel. On a tablet the chips are icons with their words as names; on a phone the bar is a wrapped row again. **Focus** dims everything but the selected entry and its neighbours, or the selected relationship and its two ends, so a large web can be read around one thing. It says so if nothing is selected.

### SO8. The matrix edits where the cell is

A first click selects a cell, a second click or a double click edits it where it is, and typing on a selected cell starts the edit too. Clicking away saves the edit as a draft, Enter saves and moves down, Tab saves and moves right, Escape cancels, Delete clears. The save bar, the refusals and Undo are as before.

## The directions (drawn; A with C's members control chosen)

In `directions/`: the web page in three layouts, each with its Graph, Matrix and List views, on the shell with made-up data (a harbour town, nine entries, ten relationships). The graph is an SVG stand-in for the renderer package's drawing. The matrix and the list are the same in all three; what differs is where the controls and the panel sit. Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/social/directions/index.html
```

The controls bar switches the layout, the view, the two lenses and the panel. Screens are in `directions/screens/` (9 images, at 1440).

| | A. Float over | B. Toolbar and panel | C. Members outline |
| --- | --- | --- | --- |
| Shape | The graph fills the page; the view switch, the region switches and the legend float over it; the panel slides over from the right | A toolbar above with the switch, the layout and the region switches; the graph beside a docked panel | An outline of the members on the left, the graph, and a panel when something is selected |
| Same as Maps | Yes: a full-width workspace with floating controls | No: closer to a document editor | No: closer to a file tree |
| Members | Added from a control; not on the page | Added from a control | Always on the page: add by name, add a group's members, add within some steps, and the list of entries |
| The lens line | A line below the title, over the graph | A line under the toolbar | A line under the toolbar |
| Cost | The panel hides part of the graph; nothing is docked | A permanent panel takes 22 rem even when nothing is selected | Two side panes take 36 rem; the graph is narrower |
| Best for | Reading and showing a web | Editing standings and relationships all day | Building a web: choosing who is in it |

What is the same in all three: a graph edge is solid (direct), dashed (derived or through) or dotted (unknown), with an arrowhead for direction and a label for the type; a group is a soft hull; a selected edge is a fill and a heavier line, never a new shape. The matrix shows a number, a quiet bar, and a mark and a word for derived, inherited, unknown and two-fill-one-cell (SO3); the legend says what each is. The list is one sentence a relationship, with its standing and "since" or "through" or "unknown as of The Wedding".

What is not drawn yet: the phone, dark mode, the Webs home, the Relationships list and a relationship page as a page, an entry's social page, the Types and standings screen, Problems, the connect mode, the empty states and the dialogs. None of it has been through the checks.

## The prototype

In `prototype/`, on the shell, with made-up data (a harbour town). Run it from `prototype/index.html`; `prototype/build-review-copy.mjs OUT_DIR` writes a single page that runs without the repository. "You are" switches between a GM and a player. The Social controls bar shows the empty states.

### Webs (SO1)

The Webs home lists the webs with a Continue block, makes a new web (empty, with the `empty-social-web` slot), renames and deletes one with Undo, and shows the empty state when there is none.

### One web (SO2, SO3, SO4, SO6)

- **Graph, Matrix, List** are three views of one page; the selection carries from one to the next. At phone width the switch is Graph (read-only), Standings and List.
- **The graph:** entries and relationships, drawn solid, dashed (through others) or dotted (unknown) with an arrowhead for direction, labelled with the type and the standing. Groups are soft outlines. Several relationships between one pair curve apart. Layouts: Circle, Radial from the selected entry, Force, and Placed by hand (drag, or Alt with the arrow keys, or fields for X and Y). Pan, zoom, fit; keys for zoom and pan. The graph is one tab stop that opens into its nodes, and the arrow keys move along edges.
- **The switches** (a vertical bar, SO7): Labels, Groups, the types shown, steps from the selected entry (All, 1, 2) and Focus. The panel shows a relationship (ends, type, one row per standing with its scale and where it comes from, since and until, the chain it holds through, notes) or an entry (its relationships, and its members apart from them).
- **The date lens and "as read by"** (SO4): a line says what is on and clears it. As of an Event, a relationship holds, has not started, has ended, or is unknown (an Event with no recorded order, or one the reader cannot see); those that have not started or have ended are not drawn, with a count of how many, and a switch shows them faded. As read by a being shows what that being may read.
- **Members** and **Connect:** pick one entry, pick another, then the type and a standing; the same entry twice is refused in words; a value outside the scale is refused in the form.
- **Edit in the panel:** a standing is a number that saves and says what it refused; since and until are Events and refuse an end before a start; each change has Undo.

### The matrix (SO3)

An ARIA grid with one tab stop: arrows, Home, End and the page keys move. A click selects, a second click or a double click edits in place, and so do Enter, F2 and typing; clicking away or Tab or Enter saves the draft and Enter or Tab move on; Escape cancels, Delete clears (asked once), Ctrl Z and Ctrl Y undo and redo drafts. Cells show a number, a quiet bar, and a mark and a word for derived, inherited, unknown and two-fill-one-cell; a legend says what they are. Edits are drafts in a save bar; a value outside the scale is refused at the cell; one cell is refused on save as changed meanwhile (412) with the draft kept, and the rest are saved with Undo. An empty cell creates a restricted relationship of the type chosen in "New cells are". Presence mode shows a type as present or not, and says whether it is one-way. A conflict cell asks which relationship to edit. A cell the reader may not read is empty.

### Relationships, a relationship, an entry, Types and standings, Problems

The list searches by name and filters by type (and what inherits from it), by an end and by reputation. A relationship has its own page with who may read it (changed as a whole), the webs that name it, and delete with Undo. An entry's social page groups its relationships by type with *to* and *from*, shows a group's members apart, and edits its standings in place. Types and standings (for authors) shows the tree with how each type reads, the scales, and the library's three type stats; a scale that existing values would break is refused with how many; a type cannot be inside itself; with no types the empty state offers the ready-made ones. Problems (for staff) lists doubled relationships, chains whose ends do not meet and groups that disagree.

### A player

A player does not see a hidden entry or any relationship with a hidden end, and nothing counts them. There are no writing controls, no Types and no Problems tab, and the pages for them say one thing. The matrix is read-only.

### What it fakes

The data is made up and kept in the page. The graph and its layouts are stand-ins for the renderer package: the engines are not deterministic across browsers as the real ones are required to be. The matrix shows the members of a web and is not windowed. Writes are checked in the page, not by an API; the 412 is staged for one cell. Who may read a relationship is one of two audiences plus named people. The starter types are in the data from the start. Notes are plain text.

### What was checked

108 scripted checks pass (Playwright, 1440 and 430 wide): the webs and their empty states; the graph, its encodings and its layouts; selection, the panels, in-place edits, refusals and Undo; the date lens, the unknown state and "as read by"; types, steps, members and connect; zoom and the keys; placing by hand with a drag, the keys and the fields; focus and the vertical bar; the matrix's keys, in-place edits with the pointer, drafts, refusals, the stale cell, the conflict cell and the presence mode; the relationships list, a relationship, an entry, types and problems; a player's absent entries and relationships; a phone's views, no horizontal scroll and 44 px targets. axe-core finds no violations on 19 to 21 states at 1440 and 430, light and dark (80 runs; the landmark-region rule is off for overlays). There are no console errors.

### What was not checked

A screen reader, a real phone or touch device, pinch zoom, colour-blindness simulation, Safari and Firefox. The matrix has not been tried with hundreds of members, and the graph not with 500 nodes. The non-visual reading of the graph (the list is the primary form) has been checked by script only.

### Findings

- A graph edge's label text made its button's name fail axe, so labels are drawn apart from the edges and hidden from assistive technology; the list and the edge's own name carry the words.
- A matrix cell's name could not match its visible text, so the cells take their name from their content and the row and column headers, and a refusal is attached with `aria-describedby`.
- Re-drawing the page reset the matrix's scroll, so a second click landed on a different cell; the scroll is kept.
- Focusing a cell that was off-screen scrolled the shell's frame; the frame is kept in place.
- On a phone the slide-over panel fell below the page, so selecting an edge or an entry opens its page instead, with the same content.
- With the panel open on a large screen it covered the zoom controls, which now move left of it.

### Screens

In `screens/` (27 images): the Webs home and its empty state; the graph, with a relationship's panel, the date lens, "as read by", Members and Connect; the matrix, with a refused save; the list; the relationships list, a relationship, an entry's page, Types and standings and its empty state, and Problems; a player's graph; dark; and the phone's graph, standings and list.

## Open questions

None are open.
