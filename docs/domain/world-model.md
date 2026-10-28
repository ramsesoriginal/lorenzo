# World model

A single "thing" in Lorenzo (a building, a person, an army) can be located along several independent axes at once. None of these are optional add-ons — they're all first-class, and something can be positioned on all of them simultaneously:

- **Physical location.** The familiar containment hierarchy: building, in a city, in a province, in a kingdom, on a continent, on a planet.
- **Position in space.** The planet itself sits in a solar system, in a cluster, in a sector, in a galaxy, in a galaxy cluster.
- **Sphere.** A parallel grouping of planets — it might line up with a solar system, or it might not. Spheres are their own axis, not a rename of "position in space."
- **Plane.** Some planes mirror each other closely (D&D's Ethereal Plane mirrors the Material Plane); others are nothing alike. A location's plane is independent of where it sits physically or in space.
- **Parallel reality (timeline).** The classic "one decision split history into two branches" — the same place can exist differently across timelines that diverged at some point.
- **Multiverse.** Parallel worlds that differ in some more fundamental way than a single diverging decision — think Marvel's multiverse of Earths.

## Why this isn't one hierarchy

It's tempting to want one tree that contains all of this ("planet → sphere → plane → ..."), but that's not how any of these actually nest in the fiction they're modeled on. A plane doesn't sit "inside" a sphere the way a city sits inside a province. These are closer to independent coordinate axes: something's full "address" is a combination of where it sits on each axis, not one path down a single tree.

## Time and causality

Every one of these axes can keep time differently, and not just "different calendar, same clock speed" — a plane can sit outside time entirely, a ship traveling near light speed experiences time differently than the world it left, and parallel timelines aren't necessarily synchronized at all.

How far this needs to be modeled — a shared "true" timeline versus many independent local ones, and how causality is tracked across them — is still partly open, and [RFC 0028](../rfcs/0028-time-causality-and-calendars.md) is only partly accepted. What is built is deliberately narrow:

- **Authored calendars.** A calendar is an entry with its own months, festivals, weeks and moons. Dates are positions in that calendar, calculated by the API, and never a clock reading or a "today" ([ADR 0308](../adr/0308-authored-calendars-and-calculation.md) to [0311](../adr/0311-calendar-documents-import-and-app.md)).
- **Explicit Event order.** Events relate by explicit "happened before" and "causes" assertions in one graph that cannot loop. A date, a Scene or a Session never creates an assertion ([ADR 0312](../adr/0312-explicit-event-order-and-causality.md), [0315](../adr/0315-reader-scoped-event-order-and-sharing.md)).
- **Participation and learning.** Who took part in an Event, and optionally when someone learned of it, are separate records ([ADR 0313](../adr/0313-event-participation-browsing-and-calendar-addresses.md), [0314](../adr/0314-optional-event-learning-records.md)).
- **Personal lived order.** What one being experienced before what, below.

Clocks that run at different rates, branching or looping timelines, and the state of the world as of a date are not built. The non-containment address axes are likewise proposed in [RFC 0026](../rfcs/0026-world-model-axes-and-address.md).

## Locations

A Location is an entry of its own kind, from a whole universe down to one floor of a building, in any
setting. Locations form their own tree: each is a part of at most one other, a level may be skipped,
and siblings can be stacked in an order. That tree is not physical containment: a bag still holds what
it carries, and a Location that is also a bag has its contents and its interior as two separate things.
Who can see a Location is the entry's own audience. A reader sees every visible Location under the
nearest Location above it that they can see, so a hidden place between them leaves no trace. A Location
may be any other kind as well.

An entry of any kind can be *at* a Location. Something in a container is where the container is, so
it takes a place only at the top of what holds it, and putting something into a container clears
its own place while taking it out gives it the container's. A player can ask where something is, as
one of their characters would say it: with you, stashed (here or near, with the name of where when
it is not the character's own place), elsewhere, or unknown, using only what that player can see
([ADR 0333](../adr/0333-placement-an-entry-is-at-a-location.md),
[ADR 0334](../adr/0334-whereabouts-the-players-read.md)). Those who write Locations also get the whole address of an entry (what holds it, its owner,
where it is and every Location above that, and what a Location is itself within) and a list of
probable mistakes in the library's places, such as a place the players cannot see
([ADR 0335](../adr/0335-the-gms-address-and-the-location-lint.md)).

A Map is an entry too, of the `map` kind, and may be any other kind as well. It says what its
positions mean (a flat plane in the Map's own units, or an outline with no measure) and holds
*placements*: where one entry is drawn on it, as a point, a circle, a line, a curve or a simple area
(one that never crosses itself, with holes), with a role such as water, relief, route, territory or
presence, a line style and a drawing order. A placement is a drawing, never where the entry is: an
entry can be drawn on many Maps, or none, and where it *is* stays what its place says. A Map may name
the Location it shows. A reader sees a Map only if they may see the Map entry, and a placement only if
they may see the entry it draws, so a hidden entry leaves no mark, gap or count on a page. Those who
write Locations draw and redraw; everyone reads what they may see
([ADR 0336](../adr/0336-maps-the-kind-its-system-and-its-placements.md),
[ADR 0337](../adr/0337-geometry-roles-and-the-validator.md), [ADR 0338](../adr/0338-reading-and-writing-maps.md)).
A repository carries its Maps and their placements through copy and update like any other entry.
A Map can be drawn by those who write Locations: a pin, a circle, a line or an area for an entry, or
for a new Location made on the spot; its role, line and drawing order changed, its points moved by
dragging or typed as numbers, and the places inside a Location placed as pins in one action that
writes explicit rows (nothing on the server expands a Location into its children). A drawing can be
undone and done again while the page is open. A Map may name a theme: how it looks is the viewer's
choice, then the Map's, then the default, and a legend shows what each role on the Map looks like
([ADR 0351](../adr/0351-writing-placements-in-bulk.md), [ADR 0352](../adr/0352-the-look-of-a-map.md),
[ADR 0353](../adr/0353-authoring-a-map-in-lorenzo-maps.md)).
A Map may be a grid instead of a free plane: squares, rectangles or hexes (flat-topped or
pointed-top, always chosen), each cell given a size on the sheet and optionally what it is in the world
(six miles a hex), and optionally divided for the eye. A cell is named by a column and a row, and the
convention for hexes and for a point on a shared edge is written once
([ADR 0354](../adr/0354-grid-systems-square-rectangular-and-hex.md)). Any Map, a plane or an outline
included, can also have a grid drawn over it that measures nothing. Places stay where they are drawn,
in drawing units, and may lie anywhere on the sheet; the editor can snap to the grid and can draw a
region as a set of whole cells ([ADR 0355](../adr/0355-the-cell-functions-and-drawing-a-grid.md),
[ADR 0356](../adr/0356-authoring-on-a-grid.md)). Turning a Map into a hex Map, out of one, or turning its
hexes, once places are drawn, is refused, since it would move all of them.
A Map may also be a sphere, a world whose places are given by longitude and latitude. It has
no edges to wrap round: what crosses the antimeridian is two parts, and a line between two places is the
straight line between them in longitude and latitude, never a great circle. How it is drawn (flat, as
Mercator, or as a globe facing a chosen point) is only a look; the globe can be turned by a reader, and its far
side draws nothing. A sphere holds points, lines and areas, no circles or curves; it can be given a radius in
the author's own unit, and a Map with places cannot become a sphere or stop being one
([ADR 0357](../adr/0357-the-sphere-system.md), [ADR 0358](../adr/0358-projections-and-drawing-a-sphere.md),
[ADR 0359](../adr/0359-authoring-on-a-sphere.md)).
A Map may also be drawn over pictures, up to eight, kept under it in an order. A picture is a picture of
the Map's own notes, so it is seen by whoever may see that note, and nobody else is told it is there. It lies
on the sheet either fitted whole or by saying where two points of the picture are on the sheet. Places
are always stored in the sheet's own units, so replacing a picture never moves one; but a replaced
picture is flagged for a writer to look at against the places, and to mark reviewed. A sphere is
drawn without pictures. SVG pictures are accepted when they hold nothing that could run or fetch
([ADR 0360](../adr/0360-pictures-a-stored-fingerprint-svg-and-when-to-leave-postgres.md),
[ADR 0361](../adr/0361-map-layers.md), [ADR 0362](../adr/0362-drawing-and-setting-up-pictures-in-lorenzo-maps.md)).
A connection joins two entries (a road, a portal, stairs, a mirror) and is an entry itself: it is named, it has a
kind of its own as a prototype, it can carry a length as an ordinary stat, and it can be drawn on a Map as a road. It goes
both ways or one way, and a stair shaft joining twelve floors is a Location with a connection to each floor, written
in one request. A reader sees a connection only when they can see it and both its ends; a hidden end leaves no trace.
A Map says where a place leads from the connections at the entries drawn on it, and on which other Maps the far end
is drawn, without ever saying where anything is
([ADR 0363](../adr/0363-connections-the-kind-and-its-two-ends.md),
[ADR 0364](../adr/0364-links-derived-from-connections.md), [ADR 0365](../adr/0365-connections-in-lorenzo-maps.md)).
Distances and optionally tying a map to a calendar period
are proposed in [RFC 0048](../rfcs/0048-locations-maps-connections-and-optional-dates.md) and come in
later slices.

## Sessions, Scenes and personal lived order

A Scene is a reusable entry that brings together Facts, Events, participating beings and an
optional calendar period. A Session belongs to one campaign, has a real-world date and optional
in-world start, and can cover several calendar periods. Its GMs, players and selected Characters
form an explicit roster. Each Scene appearance in a Session has its own notes, so another group
can use the same Scene without receiving those notes. Session and Scene references have their
own sharing controls and never grant knowledge of their targets.

Preparation order, recorded play order and personal lived order are distinct. Played Event
presentations can repeat and can include flashbacks. They do not establish Event order. An
explicit lived-before assertion instead names two existing participations of one being and is
order evidence in the shared Event graph. Its source and audience remain explicit; it does not
assert causation or learning. Unknown and unplaced history stays unknown or unplaced. See
[ADR 0317](../adr/0317-sessions-scenes-and-collaborative-planning.md),
[ADR 0318](../adr/0318-explicit-session-and-play-order.md) and
[ADR 0319](../adr/0319-personal-lived-order-as-event-evidence.md).
