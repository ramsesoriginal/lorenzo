# RFC 0042: Bench's interface: a docked workbench, and the order to build it in

- **Status:** proposed, from a prototype agreed with the maintainer (2026-10-09). To be accepted, with ADRs, once the maintainer has read it.
- **Builds on:** [RFC 0039](0039-bench-authoring-offline-and-extensibility.md) (what Bench is, offline, commands), [RFC 0041](0041-entity-kinds-and-author-freedom.md) (kinds, parents, K-slices), [RFC 0026](0026-world-model-axes-and-address.md), [RFC 0028](0028-time-causality-and-calendars.md), [RFC 0027](0027-lorenzoscript.md).
- **Picture:** [docs/design/bench](../design/bench/README.md) and its clickable prototype.

## Summary

RFC 0039 decided what Bench is underneath. It did not say what it looks like. This RFC records the interface worked out on a prototype, and maps each part onto slices so it can be built piece by piece. The phone layout is out of scope here and deferred.

## 1. Decisions

1. **A docked workbench** is the shell: panes of tabs that dock, split and float; an explorer; a palette. Views are tabs; the same entry can be open in more than one.
2. **One workspace model**, a tree of groups, splits and floats, kept as plain data with pure functions (normalise, lay out, hit test) so it is unit-tested without a DOM. It is saved per user and repository on the device.
3. **Every view edits through the command layer** of RFC 0039. No view writes to the server or the store directly.
4. **Views are over entries.** Map, relations, timeline, calendar, sheets and manuscript hold no data of their own; they read and write entries (frames, places and connections per RFC 0026, events per RFC 0028, templates and books as entries).
5. **Own small TypeScript, no framework**, as RFC 0039. Rendering of the workbench is plain DOM; the SVG views (map, graph) use `foreignObject` for labels only if needed.
6. **The prototype is a reference, not a starting point.** Its logic is ported where it was written as pure functions, and re-tested; its markup and styles are not copied.
7. **Brand and appearance** use `packages/brand` tokens; light and dark follow the system, as other apps.

## 2. From the prototype to slices

RFC 0039's B-slices stay as they are. This RFC adds the interface slices, which depend on them.

| Id | What | Depends on |
| --- | --- | --- |
| W-A | Workbench shell on stub data: workspace model and its tests, docking, split, float, palette, explorer, appearance, persistence of the layout. No API. | B1 |
| W-B | Wire the shell to B2/B3: real repository picker, item editor tab, stats pane, LIVE banner, status | B2, B3, W-A |
| W-C | LorenzoScript text with links, hover previews, images, picker | W-B, `packages/lorenzoscript(-editor)` |
| W-D | Several parents, kinds menu, bare entries | W-B, RFC 0041 K2 |
| W-E | Map and relations views | W-B, RFC 0026 slices |
| W-F | Timeline, calendar, what led to what | W-B, RFC 0028 slices |
| W-G | Sheets from templates, manuscript | W-B, a decision on templates (see questions) |
| W-H | First run, start screen, sign-out dialog | B4 for the honest parts; the dialogs can come earlier |

B5 to B10 of RFC 0039 are the conflict review, compare grid, formulas, pictures, packs and ancestry graph; the prototype shows how they sit in the workbench, and nothing here changes their scope.

**First step: W-A.** It needs nothing from the maintainer (no Authgear client, no Pages project) and it is the part most worth getting right early, since every later view lives in it. It is stub-data and not deployed.

## 3. Not in scope

The phone layout; real-time collaboration; anything the prototype fakes (see its brief); the API slices themselves.

## 4. Open questions

- **Templates.** The prototype treats a template as an entry and a sheet as a view through it. RFC 0018 was closed as superseded by parents (RFC 0041); does a template need anything beyond a parent and a layout, and where is the layout stored?
- **Manuscript.** Books and chapters as entries is simple; ordering chapters needs an order field or a sequence kind. Which?
- **Does the map need tiles or images** for frames, or only the vector schematic of the prototype? Pictures (K8) decide.
- **Layout persistence.** Per user and repository on the device only, or synced as a setting? Device only is assumed.
- **Accessibility of docking.** Drag is the prototype's only way to move a tab; keyboard moves are needed before it ships.
