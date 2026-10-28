# Kinds

An **entry** is one thing in a library or repository; its **kind** says what it is. An entry can have several kinds at once: a sentient sword is an item and a being. Which combinations a repository can hold is checked when it is published ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md), [ADR 0217](../adr/0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md)). The product words are in [identity §14.3](../brand/identity.md#143-terminology).

| Kind | What it is | Worked on in |
| --- | --- | --- |
| Item | An object, as a catalog item; an inventory item is one that exists in play | [Inventory](../../apps/inventory-web/README.md), [Bench](../../apps/bench/README.md) |
| Being | Anything that acts; a Character is a being tracked as an individual | [Beings](../../apps/beings/README.md) |
| Fact | A true statement about the world, with its own audience ([ADR 0305](../adr/0305-facts-and-entry-audiences.md)) | [Calendars](../../apps/calendars/README.md), [Beings](../../apps/beings/README.md) |
| Event | Something that happened, ordered by explicit assertions ([ADR 0312](../adr/0312-explicit-event-order-and-causality.md)) | [Calendars](../../apps/calendars/README.md) |
| Calendar | A world's months, festivals, weeks and moons ([ADR 0308](../adr/0308-authored-calendars-and-calculation.md)) | [Calendars](../../apps/calendars/README.md) |
| Clock | A ticking or timeless clock ([ADR 0320](../adr/0320-explicit-clocks-readings-and-reckonings.md)) | [Calendars](../../apps/calendars/README.md) |
| Location | A place, part of at most one other ([ADR 0330](../adr/0330-locations-the-kind-and-the-part-of-tree.md)) | [Maps](../../apps/maps/README.md) |
| Map | A drawing of entries on a sheet ([ADR 0336](../adr/0336-maps-the-kind-its-system-and-its-placements.md)) | [Maps](../../apps/maps/README.md) |
| Connection | A road, portal or stair joining two entries ([ADR 0363](../adr/0363-connections-the-kind-and-its-two-ends.md)) | [Maps](../../apps/maps/README.md) |
| Scene | A reusable piece of a story ([ADR 0317](../adr/0317-sessions-scenes-and-collaborative-planning.md)) | [Sessions](../../apps/sessions/README.md) |
| Session | One sitting of a campaign ([ADR 0317](../adr/0317-sessions-scenes-and-collaborative-planning.md)) | [Sessions](../../apps/sessions/README.md) |
| Book, Edition, Chapter, Scene telling | The parts of a manuscript, see [Writing](writing.md) | [Writing](../../apps/writing/README.md) |

Some kinds exist only as a part of another: a calendar period (a day, month or year of a calendar, [ADR 0309](../adr/0309-calendar-periods-events-and-date-associations.md)), a recurring observance ([ADR 0310](../adr/0310-recurring-calendar-observances.md)) and a Scene appearance (a Scene inside one Session).

A Location or a Map can be another kind as well, such as a Location that is also a being ([ADR 0331](../adr/0331-a-location-may-be-any-kind.md)); a Connection is always its own kind.
