# Lorenzo Maps

Lorenzo Maps keeps the places of your worlds, from a whole universe down to one room, and draws them on Maps. This guide is for game masters and players. Developers will find the implementation detail in [`apps/maps/README.md`](../../apps/maps/README.md), and the decisions in [RFC 0048](../rfcs/0048-locations-maps-connections-and-optional-dates.md) and its ADRs, from [0330](../adr/0330-locations-the-kind-and-the-part-of-tree.md) to [0377](../adr/0377-the-date-lens-on-locations-in-lorenzo-maps.md).

## Choose a Library

Log in and the **Libraries** page lists your Libraries. Choose one to reach its **Locations** and **Maps**. What you see in each depends on what you are allowed to see; an empty list can mean there is nothing or nothing for you. Maps is for a computer screen: there is no phone layout, and nothing is kept for offline use.

## Locations and the part-of tree

A **Location** is an entry kind: a universe, a continent, a village and one floor of a building are all Locations. Each Location sits in at most one other, so Locations form a tree, and the tree can skip levels. A floor is a Location in the building above it, and a building need not be in a street.

- The **Locations** page shows the tree. Open a Location to see what is **Inside** it and **Where things are**.
- The tree says only "in" or "within". It is not containment of things: it neither moves items nor decides who may reach what.
- If a level in between is hidden from you, a Location appears directly under the nearest one you can see, and nothing marks the gap.

Authors, GMs and Owners and Organizers who can see everything can **Add a Location**, **Add a Location inside** another, rename one (**Save name**), move one (**Move here**) and decide who sees it (**Visible to everyone in the library**, then **Save visibility**). Everyone else reads what is visible to them. A new Location starts restricted.

## Make a Map

A **Map** is an entry too. **Maps of the library** lists the Maps you may see, and **Find a Map** searches their names. Those who write Locations can **Make a Map**: give it a **Name**, choose what the sheet is, and tick **Everyone in the library may see it** if it should be open. The sheet is one of:

- **A plane, with its own units**, where a distance is in a unit its author names, such as miles.
- **An outline, with no measure**, for a diagram that has no scale.
- **A grid of squares, rectangles or hexes**, with a cell size and, for hexes, whether they are flat-topped or pointed-top.
- **A sphere, in longitude and latitude**, for a world.

A plane or an outline can also have a grid **drawn over it** (**Draw a grid over it**), for reference. Unless you tick the box, a new Map is restricted. The Location a Map shows is chosen later, in **Settings**.

## Read a Map

Open a Map and the drawing shows its places, people, roads and names. **Zoom in** and **Zoom out** work, and you can drag the drawing or use the arrow keys. Choose a mark, or its row under **Places on this map**, to open its panel; hover or focus one to see the entry's card. **Legend** says what each kind of mark is, and **Look** chooses between two ways of drawing. The switches **Places**, **People**, **Roads**, **Names** and, when it has any, **Pictures** hide what you do not want.

On a grid, the cell under the pointer is named in words, and **Zoom in to see the grid** says when it is too small to draw. On a sphere you choose how it is drawn, **Flat**, **Mercator** or **A globe**; a globe turns with **Turn north**, **Turn south**, **Turn east** and **Turn west**, and the pointer's longitude and latitude are written out.

A player sees the same Map with no tools and only the places they may see.

## Draw on a Map

Choose **Edit this map**. The **Tool** choices are:

| Tool | Draws |
| --- | --- |
| Select | Nothing: it picks and drags what is drawn. Every point also has number fields. |
| Pin | One place. |
| Circle | A centre and an edge. |
| Line | A road or boundary through two or more points. |
| Area | A region of three or more points. |
| Cells | A region made of whole cells, on a grid. |

Each drawing is a **placement** of an entry on this Map. Give it a **Role** and a drawing order (−100 to 100, higher on top). **Place the children** of a Location drawn as an area spreads what is inside it within the shape, and **Remove from this map** takes a drawing off without touching the entry. **Undo** and **Redo** step through your changes, and **Stop editing** ends the session. On a grid, **Snap to the grid** keeps points on the grid. On a sphere you draw by longitude and latitude.

**Settings** holds the Map's name, its sheet, the Location it shows, the theme's name and who sees it. Changes are saved with **Save settings**.

## Pictures under a Map

In **Settings**, the **Pictures** section holds images laid under the drawing. **Add a picture**, then place it by **Fit the sheet** (it fills the sheet) or by two points (**Set by two points**): each point says where it is in the picture and on the sheet. A picture already placed by three points is kept as it is. Pictures can be reordered (**Move up**, **Move down**), replaced and removed, and a reader can hide them with the **Pictures** switch. Only pictures and SVG that pass the app's checks are accepted.

## Connections

A **connection** joins two entries, usually two Locations: a road, a river, a portal. On a Location's page, **Connections** lists those it is an end of, and a writer can **Join to another place**, one place at a time, and **Remove** a connection. A connection can be **One way only**. On a Map, a placed entry's panel says where it **Leads to** and on which other Maps the far end appears. Lines drawn between placed entries are derived from connections; the app does not guess any that were not recorded.

## Distance

A Map can measure how far one place is from another: choose **Measure from** and **Measure to**, then **Measure**. It gives two answers:

- **Straight line**, on the Map, in its author's unit. On a square or rectangular grid it says how it counts a diagonal (**Diagonals count as**: Euclidean, the larger of the two, or both added).
- **By the connections**, over the connections you can see, measured in a number stat the Map's author chooses (**By the connections, measured in**).

An answer is known, partial ("at least 12 miles; 2 of 4 legs have no length"), unknown with the reason, or cut off when it is too large to work out. It is never written as zero when it is not known, and it is never converted into another unit.

## Through a date

When the Library has a calendar, **Tied to a date** lets you look at the Maps list through a date, chosen with the same period picker as in [Lorenzo Calendars](calendars.md). Each Map is then **Tied to this date**, **Not tied to a date** or **Tied to other dates**, according to the dates already associated with it; a checkbox leaves out the Maps tied only to other dates. **Clear the date** goes back to the plain list. The **Locations** page has the same control and, while a date is chosen, lists Locations by name rather than as a tree. Nothing is inferred: a Map or Location with no association says so.

## Who can write

Authors, GMs, and Owners and Organizers who can see everything can add, rename, move and open Locations, and make and draw Maps. Players and other readers see what is visible to them, with no tools. Each Location and Map has an audience of its own; what a reader cannot see is left out without a placeholder, so two readers of one Library can see different Maps and different trees. Details are in [entities, knowledge and visibility](../domain/entities-knowledge-and-visibility.md).

## What Maps does not do

- It has no phone layout and no offline mode.
- It does not turn the part-of tree into containment, and the tree never decides who can reach what.
- It does not work out distance from anything but the Map's own geometry and the connections you can see.
- It does not infer dates: a Map or Location is tied to a date only where someone recorded it.
- Frames and axes, a way to name which setting a place belongs to, are available to the API but have no screen in Maps yet.
