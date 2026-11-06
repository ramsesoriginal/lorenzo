# 0408 - Lorenzo Social: the app, the matrix and the phone

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slices 9 to 13. In the shape of Lorenzo Maps ([ADR 0332](0332-lorenzo-maps-the-app.md)).

## Decision

**The app.** `apps/social`, "Lorenzo Social", is a static Astro app (`output: 'static'`, plain TypeScript, no component
framework) using the shared page frame (`packages/app-shell`), the brand base, the typed client, the read cache and the
app-link registry ([ADR 0273](0273-app-links-registry.md)). It signs in with Authgear as its own public single-page-app
client and holds no durable private cache. Hosting is a Cloudflare Pages project `lorenzo-social`; CI declares it as a
node that depends on the API client and `packages/graph-renderer`, with a real-API end-to-end suite on ports of its own.
The scaffolding slice creates the `app:social` and `pkg:graph-renderer` labels and lists, for the maintainer, the steps
nobody else can do: the Authgear client and its callback addresses, the Pages project and its build watch paths, the
production origin in the API's `CORS_ALLOWED_ORIGINS`, and the `social` entries of the app-link registry.

**Screens.** The relationship list and page, an entry's social page, the SocialWeb list and page (graph and list form,
with the date lens and "as read by" of [ADR 0405](0405-optional-time-on-a-relationship-and-reading-as-of-an-event.md)),
the matrix, the types and standings screen for authors (which also sets the library's three type stats, ADR 0400), and a
problems list for staff (RFC 0049, "For the interface
design"). Hierarchy and direction are said in words ("Mara is the parent of Wren").

**The matrix.** One ordered pair of a web's members a cell, for a chosen standing (value mode) or type (presence mode).

- *Reads*: windows of at most 100 rows by 100 columns through `end_a_in` and `end_b_in` of ADR 0399, with the values of the standing from the bulk stat read of ADR 0387 (`kind=relationship`), prefetched with the
  read cache. A relationship the reader may not see is an empty cell, indistinguishable from none.
- *Cells*: a one-way relationship fills its cell, a two-way one both cells of its pair, an inherited value is marked as
  inherited (dashed, with a word), and two visible relationships for one cell are a conflict that lists both.
- *Editing an empty cell* creates a relationship of the chosen type: restricted, named `<A> - <type> - <B>`, one-way for
  a directed type and two-way otherwise, with the value set. Clearing a value removes the stat and keeps the relationship.
- *Scale*: hundreds of members, virtualised (only the visible cells are in the document), an ARIA grid with one tab stop;
  arrows, Home, End, page keys, Enter or F2, Escape, typing to replace, Delete (asking once), undo and redo while the page
  is open. Input is bounded by the stat's scale ([ADR 0403](0403-stat-scales.md)).
- *Saving*: edits collect and go in batches of at most 100 operations through the bulk write of
  [ADR 0400](0400-relationship-kinds-standings-and-direction.md); a refused cell keeps the API's reason and nothing else is
  lost; a 412 keeps the draft.
- Any total of a row is worked out on the client from what the reader sees and is worded so. Row and column order is by
  name, by group or by a chosen standing.

**The phone** (ADR 0195). One breakpoint at 720px, targets of at least 44px, a single column, wrapping tabs, no hover-only
control, type that does not shrink. At that width the app ships the lists, the outline, the relationship forms and a
read-only graph (pan, pinch, tap to select). The matrix is for tablet and desktop; on a phone a list of one entry's
standings, with the same bulk save, takes its place.

**The interface** follows identity, [ADR 0259](0259-bench-the-quiet-interface.md) and
[ADR 0322](0322-calendars-and-sessions-share-a-header-and-the-brand-base.md): tokens only, the quiet interface, visibility
as a neutral badge, selection as a fill. Two icons for Relationship and Social web are chosen with the maintainer and added
to the atlas ([ADR 0391](0391-the-icon-atlas-grows-to-every-ui.md)) by the scaffolding slice. A mock-up from the other
design team is adopted later without a change to the data or the contract.

**Docs.** The app is listed in `AGENTS.md`, `apps/README.md`, the README and the domain documents in the scaffolding pull
request, and `docs/operations/social-setup.md` records the hosting.

## Validation and delivery

Browser tests against the real API: sign-in, an empty library with the starter offer, a writer making and restricting a
relationship, a player seeing only what they may, a hidden end leaving no cell, a conflict cell, an edit batch with a
refused cell, the keyboard path through the matrix, and the phone width; axe in light and dark on each screen.

## Excluded

Offline use, an installable shell, a native app, a matrix on a phone, and Bench's and Beings' adoption (slice 16).

## Addendum: as built (2026-11-06)

- The matrix edits whole-number (`int`) standings; a decimal standing is read, not written, because the JSON a browser
  sends cannot tell 3.0 from 3 and the API does not coerce a number between types.
- Row totals are shown for the focused row only, worded as what the reader sees.
- Two icons for Relationship and Social web are still to be chosen with the maintainer; until then the atlas's own
  `social` icon and the kind icons stand in.
- A player writes relationships with a being they control (ADR 0425): the relationship form is offered to every
  participant, without the choice of opening it up.
- The Beings relationships section and Bench's Relations pane (slice 16) read only and take the renderer's `radial`
  layout.
