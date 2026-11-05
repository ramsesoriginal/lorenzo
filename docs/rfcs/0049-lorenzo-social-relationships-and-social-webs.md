# 0049 - Lorenzo Social: relationships, standings and social webs

Status: accepted, decided with the maintainer on 2026-11-05 for the structural choices below; the numbers
marked *proposed default* are the author's and are settled in the ADR of the slice that needs them.
Decisions: one ADR per choice, [0399](../adr/0399-relationships-the-kind-and-its-two-ends.md) to
[0408](../adr/0408-lorenzo-social-the-app.md). This builds on [RFC 0048](0048-locations-maps-connections-and-optional-dates.md)
without changing it, and uses [RFC 0028](0028-time-causality-and-calendars.md) only through the Event order that
is already built. It accepts nothing of [RFC 0029](0029-epistemic-status-of-information.md).

## Purpose

Say who is connected to whom and how, which groups hold whom, and how much one being stands with another
(reputation, honor, Concordance, faith, familiarity, ...), in any setting: fantasy, science fiction, modern,
realistic, or no game at all. Show it as a graph and as an editable matrix, and let a connection be limited
in time by Events. Everything is an entry, as everywhere in Lorenzo: a relationship is an entry, its type is an
entry, a saved view is an entry, a standing is a stat.

## Decided inputs

Decided with the maintainer on 2026-11-05 (the number is the question it answered).

1. **A second kind, Relationship** (1c). `connection` stays what Maps made it: a way between places.
2. **Membership stays `group_member`** (2). A relationship to a group adds a role or a standing and never
   implies membership.
3. **A standing is a stat on the relationship entry** (3a). **Direction is the type's**: a directed standing is
   two one-way relationships, a symmetric one is one two-way relationship (3b).
4. **A saved view is an entry of its own kind, SocialWeb** (4). The unsaved state lives in the address.
5. **Optional start and end Events** on a relationship. A reading *as of* an Event uses the reader's authorized
   order and is `holds`, `not yet`, `ended` or `unknown`. *As seen by* is an audience lens and nothing more (5).
6. **Restricted by default, with named recipients.** Those who write Locations and Maps write relationships in
   the first slices; players writing their own is a later slice (6a).
7. **Words**: reputation, honor, Concordance, faith and familiarity are standings; romantic and sexual are
   relationship types; family, summoner and patron, diplomat and realm relations are types (7).
8. **An opt-in starter repository** holds that vocabulary as ordinary content. Nothing is seeded (8).
9. **An optional minimum and maximum on a stat definition**, as a slice of its own (9).
10. **The layout engines are written by us**, with no external library (10).
11. **One app, `apps/social`, and one package, `packages/graph-renderer`** (11).
12. **Phone**: lists and an outline, a read-only graph, a per-being list of standings in place of the matrix (12).
13. **Pairwise only**: a marriage of three is three relationships (13).
14. **`relationship_through`**: an ordered chain of relationships that a relationship is stated to hold through
    (the maintainer's addition to 13).
15. **Review answers, 2026-11-05.** The three type stats are named by a library-wide setting, not found by name.
    A start or end Event the reader cannot see makes an as-of answer `unknown`. Deleting an Event that bounds a
    relationship clears the reference and leaves a note. "As read by a being" is also for the players of that being.
    A group's hull is drawn from `group_member` alone.

## Hard invariants

Every slice holds these, and each is pinned by a test.

- **S1.** Nothing is seeded. Absence means "not modeled". An unused feature costs zero rows, form fields and
  response keys.
- **S2.** Time is optional and never inferred. A relationship with no start and no end behaves as if time did not
  exist. No "now", no default Event, no date creates an order (ADR 0312).
- **S3.** No relationship, `relationship_through` row or SocialWeb feeds ADR 0046 reach, a knowledge grant,
  `group_member` or any access decision. Maps never reads a relationship: a pin test names the new tables.
- **S4.** A hidden thing is absent, not a placeholder: in every list, count, page, graph layout, matrix cell,
  as-of answer and error. The predicate is applied in SQL before pagination and traversal.
- **S5.** Nothing is inferred and nothing is aggregated on the server: no kinship deduced from a parent, no trust
  computed along a chain, no total standing over a being's relationships.
- **S6.** No genre, unit or vocabulary default in the schema, the API strings, the renderer or the interface.
- **S7.** Everything travels through repository copy, update and release: a registry line in
  `copyable_tables.py`, the `repository_read` policy, a planner step, a release-format bump with its reader and
  a kind-matrix row.
- **S8.** Every tenant table has `tenant_id`, `ENABLE` and `FORCE ROW LEVEL SECURITY` and same-tenant foreign keys
  ([ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)).

## What this relies on and leaves alone

- [ADR 0363](../adr/0363-connections-the-kind-and-its-two-ends.md) to
  [0367](../adr/0367-the-distance-read.md): `connection`, its links and its router are unchanged. A friendship
  built on `connection` would be an edge of the router and a link on a Map (a connection with no length makes a
  route partial), which is why a second kind exists.
- [ADR 0037](../adr/0037-effective-stat-resolution.md), [0104](../adr/0104-computed-stats.md),
  [0278](../adr/0278-stat-definition-display-fields-order-and-patch.md),
  [0387](../adr/0387-the-bulk-effective-stat-read.md): a standing inherits through prototypes by hop distance, a
  sum formula reads the stats the reading entry resolves, a stat definition has no range today, and the bulk
  read takes at most 50 stats and 100 entries a page.
- [ADR 0028](../adr/0028-knowledge-and-group-membership.md) and
  [0316](../adr/0316-collaborative-events-facts-and-participant-audiences.md): a group is a bare entry and
  `group_member` is direct and flat, with beings as members.
- [ADR 0305](../adr/0305-facts-and-entry-audiences.md): an entry's outer audience gates its existence and its name,
  and information keeps its own audience. A stat value is as visible as its entry.
- [ADR 0312](../adr/0312-explicit-event-order-and-causality.md) and
  [0315](../adr/0315-reader-scoped-event-order-and-sharing.md): Event order is explicit and acyclic, a reader
  derives it from visible Events and shared assertions, and a `linearized` comparison is a display order, never
  evidence of chronology.
- [ADR 0339](../adr/0339-the-map-renderer.md): layout to a plain Scene, paint with `createElementNS`, hit test and
  interaction apart, themes as code modules, no runtime dependency.
- [Identity §18](../brand/identity.md#18-information-visualization-grammar): solid is direct, dashed is derived,
  inherited or indirect, dotted is unknown or uncertain, an arrowhead means direction matters, and the
  vocabulary stays small. [ADR 0195](../adr/0195-brand-phone-base.md) and
  [0259](../adr/0259-bench-the-quiet-interface.md): the phone base and the quiet interface.

## Design

### The Relationship kind (ADR 0399)

```sql
relationship(entity_id PK, tenant_id NOT NULL, end_a NOT NULL, end_b NOT NULL,
  one_way boolean NULL CHECK (one_way IS NOT FALSE), CHECK (end_a <> end_b))
```

Same shape as `connection`: a marker that gives an entry the kind, two ends that are entries of any kind
(a being, a group, a Location, an Event, an item that stands for the bond, another relationship), `one_way` null
for a way both ways and true from `end_a` to `end_b`, same-tenant foreign keys, `ON DELETE CASCADE` on the ends
(the entry stays, a plain entry). A relationship **combines with no other kind**. Its user-facing word is
**relationship**; in prose its prototype is its **type** (parent of, ally of), and "kind" is kept for what an
entry is.

- **Visible only with both ends.** A relationship is read only by a reader who can see it and both ends, in every
  read: its own routes and the generic entry routes alike (the list, the bulk stat read, previews, search). The
  end predicate joins the shared entry-visibility clause for this kind, so no read has to remember it (S4).
- **No uniqueness on a pair or a type.** A uniqueness refusal would tell a writer that a hidden relationship
  exists. Two relationships of one type between the same pair are legal and the matrix has a state for it.
- **Limits** (*proposed default*): 20,000 relationships a library, counted apart from connections; a repository's
  30,000-entry quota is shared, so a dense web spends it. A bulk write takes at most 100 operations.
- **Reads**: `GET /tenants/{t}/relationships` by name then id in the standard page shape, with `end`, `end_a_in`
  and `end_b_in` (at most 100 ids each), `type` (a prototype and what inherits from it), `q`, repeatable
  `stat_definition_id` (the effective values come with the row, as in ADR 0387) and the as-of parameters below;
  `GET .../relationships/{id}` with an ETag.
- **Writes**: `POST` one, `PUT` the ends and `one_way` under `If-Match`, and the bulk write (ADR 0400).

### Types, standings and direction (ADR 0400)

- A **type** is a prototype entry; types form a tree (Family, then Parent of and Sibling of), and a relationship
  names its type through `prototypes` on create. Nothing is seeded.
- A **standing** is a stat on the relationship entry. The value inherits from the relationship's prototypes, so a
  relationship from a character to a group can be the prototype of a more specific one from that character to one
  member; the nearest value wins, and an adjustment is a sum formula over an inherited base and an own part.
  Nothing checks that the member belongs to the group.
- **Direction is the type's.** Three optional stats on a type say how it reads: *directed*, *reads as* and *reads
  as, from the other end*. The library says which stat definitions they are in a library-wide setting (three
  nullable columns on the tenant, as the being stat group of [ADR 0296](../adr/0296-being-stat-group.md) is
  set; a library setting, not repository content). A directed standing is two one-way relationships, one each way, each with its own value
  and its own audience; a symmetric one is one two-way relationship, shown in both cells of the matrix and edited
  from either. Without those stats a relationship still works: it reads with its type's name and its own
  `one_way`.
- **Pairwise only.** A relationship has two ends. A marriage of three is three relationships; "the marriage" as one
  thing with dates and stats is an entry (a group or any entry) that each partner relates to. A relationship with
  a set of members is parked and is not designed here.
- **The words.** Reputation, honor, Concordance, faith and familiarity are standings. Romantic and sexual are types.
  Family (parent, child, sibling, co-parent, married, partner), summoner and summoned, patron and patroned,
  diplomat for and diplomat in, at war with and in alliance with are types. All of it lives in an opt-in
  **starter repository** that a library copies like any repository; it is content, not code.

### Groups (ADR 0401)

`group_member` stays membership and access: beings only, direct, flat. The app reads it and writes it through the
existing group API. A relationship to a group says a role or a standing (rank in an order, Concordance with a
pantheon) and grants nothing. A pantheon is a group of beings, or any entry; Concordance is a standing on a
relationship from a being to it. Nesting (a pantheon inside a pantheon, a nation in an empire) is a relationship
between group entries.

### Through (ADR 0402)

```sql
relationship_through(relationship_entity_id, step smallint, via_entity_id, tenant_id NOT NULL,
  PRIMARY KEY (relationship_entity_id, step), UNIQUE (relationship_entity_id, via_entity_id),
  CHECK (relationship_entity_id <> via_entity_id), both ids -> relationship)
```

A relationship is stated to hold **through** an ordered chain of other relationships: grandfather through father
and father, trust through a chain of trusted relationships, co-spouse through the partner both share. It is an
authored statement, not a computation (S5): nothing derives a value or checks the chain, and a lint lists a chain
whose ends do not meet. Through is acyclic across the library (checked on write under an advisory lock, with a depth
cap), at most 12 steps (*proposed default*). A hidden step leaves no gap: the reader sees the steps they may see.
A relationship with steps is drawn dashed (indirect, §18).

### Standing scales (ADR 0403)

A number stat definition gets an optional `min_value` and `max_value`. The API checks a write against them (422),
refuses a bound that existing values would break (409 with the count), and repositories carry them. The matrix uses
them to bound input and draw honestly; with none it shows the value and colors by the visible range and says so.
This is a slice of the stat vocabulary, independent of the rest.

### Visibility and writers (ADR 0404)

- A new relationship is restricted unless `is_public` (as a connection is). Its audience takes named recipients
  (a character, a group, a player) by extending the entry audience of
  [ADR 0305](../adr/0305-facts-and-entry-audiences.md) to the kind, with the atomic, versioned `GET` and `PUT` that
  facts have.
- A stat has no audience of its own, so what must stay secret is a relationship of its own: a public friendship
  and a restricted romance between one pair are two entries. A difference between readers is two entries, never a
  redaction (authored truths, ADR 0028).
- Notes on a relationship are information with their own audiences.
- Standing to write in the first slices is that of those who write Locations and Maps (Authors, GMs, full-visibility
  Owners and Organizers). A player writing a relationship with a being they control, with a default audience of that
  being and the GMs, is a later slice with its own ADR.
- The starter repository includes no default audience: the default is restricted for every type.

### Optional time and reading as of an Event (ADR 0405)

`relationship` gains two nullable Event references, `starts_at` and `ends_at` (the columns arrive in the slice that
reads them). They name Events, never dates, and set no order. This narrows RFC 0048's "time never reaches a
connection row", which stays true of `connection`.

- Deleting an Event that a relationship references clears the reference and, in the same transaction, leaves a staff-only
  note on each relationship it bounded, so the relationship does not silently become unbounded.
- **As of Event E**, over the reader's authorized graph only (visible Events and shared assertions, ADR 0315):
  `holds` when the start is E or recorded before E and the end is none or not recorded at or before E;
  `not yet` when the start is recorded after E; `ended` when the end is recorded at or before E; otherwise
  `unknown`. "Recorded" means a path of `causal` or `ruled` assertions; a `linearized` comparison never decides
  anything. `unknown` is drawn dotted. A start or end Event the reader cannot see makes the answer `unknown`, which
  tells that a limit exists and never which.
- The read takes `as_of=<event id>` on the list and adds the state to each row; `state=` filters before
  pagination. The reachability sets are bounded in code (*proposed default*: 2,000 Events) and an answer past the
  bound is `limit_reached`.
- **As seen by X** is for staff, and for a player when X is a being they control: the relationships X may read (X's own
  grants and X's groups). For a player the answer is also limited to what that player may read, so it never shows more
  than they could see. It is worded "what X may read", never "what X believes"; belief, rumour and confidence wait for
  RFC 0029.

### SocialWeb (ADR 0406)

A SocialWeb is an entry of kind `social_web`: a chosen set of entries drawn as a graph or read as a matrix.

```sql
social_web(entity_id PK, tenant_id NOT NULL, layout text NOT NULL, layout_seed integer NOT NULL,
  theme_hint text NULL, view jsonb NULL, standing_stat_id NULL, as_of_event NULL)
social_web_entry(web_entity_id, entry_entity_id, x numeric NULL, y numeric NULL,
  PRIMARY KEY (tenant_id, web_entity_id, entry_entity_id))      -- x and y both set or both null
social_web_type(web_entity_id, type_entity_id, PRIMARY KEY (tenant_id, web_entity_id, type_entity_id))
```

- **A web shows exactly the entries that have a row.** There is no rule the server expands: "add this group's
  members" and "add everyone within two steps of her" are editor actions that write explicit rows (as ADR 0351
  does for Maps). The same ad hoc selections are the unsaved form of a view, kept in the address.
- Edges are the visible relationships whose two ends are members, limited to the web's types when it names any.
  No entry id sits inside the JSON, so a copy never rewrites it.
- `layout` is a name from a closed list in code (`circle`, `radial`, `stress`, `forceatlas2`, `manual`); `x` and `y`
  are hand placement and are used by `manual` and as pins by the others.
- **A reader's layout is computed over what that reader sees**, so a hidden member cannot move anyone. Two readers can
  see different drawings of one web, and a test pins that a hidden member changes no byte of another's Scene.
- At most 500 members and 50 types a web (*proposed default*). A web is an ordinary entry: audience, name, notes.

### The drawing contract (ADR 0407)

`packages/graph-renderer`, framework-free TypeScript, no runtime dependency, shipping source and a stylesheet.

1. `layout(model, view, theme) -> Scene`: pure, plain data, the same input the same bytes, numbers rounded, NaN and
   Infinity rejected. The model is nodes (id, name, icon key, flags), edges (id, ends, direction, label, status
   `direct | derived | uncertain`, an optional value), groups to draw as hulls, hand positions and the view.
2. `paintSvg(scene, svg)`: `createElementNS` and `textContent` only, never `innerHTML`.
3. `hitTest(scene, point)` and the interaction module (pan, zoom, select, centre on, move a node in `manual`), which
   emit events and never fetch or write.

- **Layout engines**, written by us, each `(graph, params, seed) -> positions`, in a closed list in code that grows
  by ADR: `circle`, `radial` (polar rings by steps from a focus), `stress` (stress majorization),
  `forceatlas2`, `manual`. A **layered** engine (for family trees and lineage) is its own later slice.
- **Determinism**: integer seeded generator, fixed iteration counts, stable ordering by id, and only +, −, ×, ÷ and
  square root, with our own sine and cosine for the circle. `Math.sin`, `Math.cos` and `Math.exp` are
  implementation-approximated and an iterative layout amplifies the difference, so they are not used. A golden
  test runs the same input in two engines.
- **Themes** are code modules naming brand tokens. The default theme now; later themes (family tree, an
  underground map, a git log) are new modules and, where they need one, a new engine, through the same contract
  and without changing the data. A theme cannot add a field or a request.
- **Grammar** (§18): three edge styles (solid direct, dashed derived or indirect, dotted uncertain), an arrowhead for
  direction, selection as a fill and never a change of shape, nothing told by color alone. The type of a
  relationship is told by its label and an icon, never by a line style of its own; the Bench prototype's per-type
  line styles are not adopted.
- **Limits** (*proposed default*): 500 nodes and 2,000 edges a Scene; above that the app asks for a smaller
  selection.
- **Reading it without sight**: a list in the document is the primary non-visual form, one sentence a relationship
  ("Mara is the parent of Wren, since The Wedding"), kept in step with the selection; every node is focusable
  with a name; the arrow keys move along edges. Nothing is hover-only.

### The matrix (ADR 0408)

An editable grid in `apps/social`, one cell per ordered pair of the web's members for a chosen standing (a *value*
mode) or a chosen type (a *presence* mode, for kinship and the like).

- **Reads**: a window of at most 100 rows by 100 columns through `end_a_in` and `end_b_in`, prefetched through the
  read cache. A relationship the reader may not see is an empty cell, indistinguishable from none.
- **Cells**: a one-way relationship fills its own cell; a two-way one fills both cells of its pair; a value
  inherited from a prototype is marked as inherited (dashed, with a word); two visible relationships for one cell
  are a conflict state that lists both and asks which to edit.
- **Editing an empty cell creates** a relationship of the chosen type, restricted, named `<A> - <type> - <B>`,
  one-way A to B for a directed type and two-way for a symmetric one, with the value set. Clearing a value removes
  the stat, not the relationship.
- **Scale**: hundreds of members, virtualised (only the visible cells are in the document), an ARIA grid with one
  tab stop and arrow, Home, End and page keys, Enter or F2 to edit, Escape to cancel, typing to replace, Delete to
  clear (asking once), undo and redo while the page is open.
- **Saving**: edits collect and go in batches of at most 100 operations, each in one transaction; a refused cell
  stays marked with the API's reason and nothing else is lost. A stale ETag is a 412 that keeps the draft.
- Row and column order: by name, by group or by a chosen standing; any total of a row is worked out on the client
  from the relationships the reader can see and is worded so.

### The app (ADR 0408)

`apps/social`, "Lorenzo Social", a static Astro app in the shape of Maps (ADR 0332): the shared page frame, the brand
base, the typed client, the read cache and the app-link registry, Authgear as its own client, a Cloudflare Pages
project `lorenzo-social`. Phone is built to ADR 0195 for lists, the outline, the relationship forms and a read-only
graph; the matrix is for tablet and desktop, and a per-being list of standings (the same bulk save) takes its place
on a phone.

## For the interface design

This section is for the team designing the web interface. It says what the app does and which data each screen
needs. How it looks is the brand's (identity, ADR 0195, ADR 0259) and yours.

### Who uses it and for what

- **A game master preparing**: builds a court, a family, a pantheon, a faction web; sets how much each stands with
  each; keeps some bonds secret; draws a web to show players.
- **A game master during play**: asks "what does Mara think of the Guild, and who is her patron?", adds a tie in the
  moment, changes a standing after a scene.
- **A player**: reads the webs and relationships they may see. Writing their own is a later slice.
- **An author of a setting**: defines the relationship types, standings and scales once, publishes them in a
  repository.
- **Staff checking a story**: reads the web as of an Event, or as one being may read it.

### Words (use these)

Relationship; type (of a relationship); standing; social web; since and until (Events); "unknown" for a state that
is not recorded; "what X may read", never "what X believes". Say "in this library". A relationship reads as a
sentence: "Mara is the parent of Wren". Do not use "friend", "enemy" or any type as if it were built in: types are the
library's data.

### Screens and the data each needs

1. **Relationships** (list): search by name; filter by type, by an end, by a group and by a standing; a row is a
   sentence plus the standing value and its scale; paging, never a total of what is hidden. Data: the list read.
2. **A relationship**: the two ends (each a link with a card), the type and what it inherits from, one row per
   standing with its value, its scale and where an inherited value comes from, since and until (an Event each, with
   its place in the order), the *through* chain, notes, who may read it, and the entries that name it. Edit and
   delete for writers. Data: the relationship, its effective stats, its prototypes, its steps, its audience.
3. **An entry's social page** (a being, a group, any entry): its relationships grouped by type, each in its direction
   in words (*to* and *from*); for a group, its members from `group_member` shown apart from relationships; a list of
   all standings of this entry with inline editing. Data: the list read with `end`.
4. **Social webs** (list) and **one web**: the canvas and a panel.
   - A toolbar: layout (circle, radial, stress, force, placed by hand), labels on or off, groups as hulls on or off,
     the types shown, steps from the selected entry (all, 1, 2), a date lens (an Event, from a picker listing Events
     in story order), and "as read by" a being (any for staff, the player's own beings for a player).
   - A legend of the three line styles and the arrowhead (not of types).
   - A panel for the selection: the relationship or the entry, with the same fields as screens 2 and 3.
   - A mode to connect two entries: pick one, pick the other, choose the type, set a standing.
   - A members control: add by name, add a group's members, add everyone within some steps.
   - The list form of the same web, always available and primary for a screen reader.
5. **Matrix**: described above. The toolbar chooses the standing or type, the row and column order and the members.
6. **Types and standings** (for authors): the tree of types with their reading and direction, the standings with
   their scale, and the starter repository's offer.
7. **Problems** (staff): relationships doubled for one cell, chains whose ends do not meet, groups and relationships
   that disagree. A list with a link to each.

### States every screen has

- **Empty**: no types in the library (offer the starter repository), no relationships, no members, no standing chosen.
- **Loading**: a skeleton for a list; the Scene keeps its last drawing while a new one is computed.
- **Partial**: a Scene over its cap asks for a smaller selection and says so; a list is paged; the matrix reads in
  windows and marks a window still loading.
- **Hidden**: absent. No placeholder, no "N more", no gap in a chain, no difference between an empty cell and a cell
  whose relationship the reader may not see.
- **Unknown**: a date lens where the order does not decide. Drawn dotted, worded "unknown as of this Event".
- **Conflicting**: two relationships fill one cell; a stale edit (412) keeps the draft and offers a reload.
- **Refused**: a write the API refuses is shown as it gave it, next to the cell or field, and keeps the draft.
- **Offline**: no offline grant in the first slices. Reads come from the session cache, writes are refused honestly with
  the reason, and nothing says "saved" that is not.

### Keyboard and touch

- Everything reachable by pointer is reachable by keyboard. The graph is one tab stop that opens into its nodes;
  arrow keys move along edges, Enter opens, Escape closes; pan and zoom by keys; dragging a node in manual layout has a
  keyboard way to nudge it and a field for its position.
- The matrix is one ARIA grid with the keys above and no hover-only control.
- Touch: targets of at least 44px, one breakpoint at 720px, the page in one column, a tab row that wraps, no hover-only
  control, type that does not shrink. At phone width the graph is read-only (pan, pinch, tap to select) and the
  matrix is replaced by the list of one entry's standings.

### Fixed by the brand

Tokens and no literal colors; the quiet interface of ADR 0259; Gold only for canonical; visibility is a neutral
badge with an icon and a word, never a color (`icon-private` for restricted); selection is `--surface-selected` with
`--focus-ring`, and never changes a node's shape; color never carries meaning alone; the line grammar of §18;
the icon atlas (ADR 0391) with two kind icons to choose for Relationship and Social web, added to the atlas by the
scaffolding slice; reduced motion honored; the shared page frame and the app-link registry for moving between apps.

## Delivery

One ADR per slice, written before its implementation, and one tested vertical pull request. The docs pull request
for this RFC and its ADRs comes first. A slice never lands a table without its repository line, because the
repository tests fail otherwise; no schema or interface for a later slice is built early to reserve space. The
slices below are proposed and each is scoped with the maintainer before it starts.

| # | Slice | ADR | Depends on | First step |
| --- | --- | --- | --- | --- |
| 1 | Relationship kind: table, routes, reads with the both-ends rule in the shared entry visibility, own limit, registry line, release format, kind matrix, `kinds` widening through the breaking-change process | 0399 | none | a failing test that a relationship with a hidden end is absent from every generic read |
| 2 | Audiences with named recipients for the kind | 0404 | 1 | the atomic `GET` and `PUT` of ADR 0305 on the kind |
| 3 | Stat scales | 0403 | none | the two columns and the write check |
| 4 | Bulk write of relationships and stat values, and the library's three type-stat settings | 0400 | 1 | one transaction over at most 100 operations, each resolved under the writer's visibility |
| 5 | Through | 0402 | 1 | the table and the acyclic check under the advisory lock |
| 6 | Optional time and the as-of read | 0405 | 1 | the two columns and the bounded reachability over the reader's graph |
| 7 | `packages/graph-renderer`: Scene, paint, hit test, interaction, default theme, `circle` and `radial` | 0407 | none | the Scene type and the golden corpus, from fixtures |
| 8 | SocialWeb kind and its rows | 0406 | 1 | the three tables and the reader-scoped read |
| 9 | `apps/social` scaffold: sign-in, library, relationship list and page, create | 0408 | 1 | the scaffold and the steps for the maintainer below |
| 10 | The graph view, with `stress` and `forceatlas2` | 0407, 0408 | 7, 8, 9 | the web page over the list form |
| 11 | The matrix | 0408 | 3, 4, 8, 9 | the read window and the grid without editing |
| 12 | The date lens and "as read by" in the app | 0405 | 6, 10 | the Event picker and the three states |
| 13 | Types and standings screen and the starter repository | 0400 | 9 | the starter as content, reviewed with the maintainer |
| 14 | Players write their own relationships | new | 2, 9 | the standing rule and the default audience |
| 15 | A layered engine and further themes | new | 7 | the engine, on family-tree fixtures |
| 16 | Bench's Relations view and the Beings relationships slot take the package | new | 7, 9 | the consumer, per ADR 0098's second-consumer rule |

The scaffolding slice lists, for the maintainer, the steps nobody else can do: the Authgear client with its callback
addresses, the Cloudflare Pages project `lorenzo-social`, the `app:social` and `pkg:graph-renderer` labels, and the
entry in the app-link registry. A package normally waits for its second consumer; `graph-renderer` is created at its
first, as `map-renderer` was, because the Bench Relations view and the Beings relationships slot are its named second
consumers.

## Not in scope

A relationship with more than two ends; inferred kinship and any transitive value; a server total of standings;
belief, rumour and confidence (RFC 0029); a place that differs between timelines; travel or routing over
relationships; a map drawing of relationships; layered, octilinear and lane layouts and their themes until their own
slices; an external layout or graph library; time on `connection`; mobile apps of the app; offline use; players
writing before slice 14; per-viewer server storage of views.

## Open questions

Each is settled in the ADR of the slice that needs it.

1. The numbers marked *proposed default*, after measurement.
2. Which two icons stand for Relationship and Social web.
3. Whether connections get the same both-ends rule in the shared entry visibility. The generic reads appear not to
   apply it to `connection` today (`readable()` is called only by the connection and distance routes); that is a
   separate defect to be proved by a test and fixed on its own.

## Consequences

Easier: roads and friendships never meet; a standing is an ordinary stat, so formulas, inheritance, repositories and
the stat editors apply; a view is an entry and travels like one; a different look is a different theme over the same
data; a library with no social data has no social rows.

Harder, and accepted:

- A relationship entry exists for each filled cell, so a dense matrix spends the library limit and the repository
  quota before anything else.
- A hidden relationship is absent from a standing's picture, so no total is the same for every reader; the app does
  its sums on the client and says "from what you can see".
- A hidden step in a chain leaves no trace; a hidden Event that bounds a relationship makes an as-of answer `unknown`,
  which tells a reader that a limit exists.
- Deleting an Event changes the relationships it bounded, and the note it leaves is the only record.
- Two readers can see different drawings of one web, since layout runs over what each may see.
- Each slice carries a release-format bump, a registry line, a planner step and a kind-matrix row, and the `kinds`
  widening is an API break that goes through the breaking-change process.
- Closed lists (layout engines, themes, the type stats) are shared by the API and the renderer and drift unless
  one source and a golden test hold them.
