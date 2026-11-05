# Social: design

A fresh design of Lorenzo Social, a new app, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, Calendars with Sessions, Maps, Beings and Inventory are decided. This page holds the brief, the questions and the decision log for this app.

Status: the brief and its questions. Nothing is decided yet.

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

Nothing is decided here yet.
