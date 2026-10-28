# 0365 - Connections in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 10. Extends
[ADR 0332](0332-lorenzo-maps-the-app.md) and
[ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) for the connections of
[ADR 0363](0363-connections-the-kind-and-its-two-ends.md) and the links of
[ADR 0364](0364-links-derived-from-connections.md). Desktop only.

## Decision

**A Location page lists its connections.** A *Connections* section names each connection the reader
may see that has this Location as an end: the connection's name and, in words, where it goes: *to X* for
a way both ways, *one way to X* when it leaves this Location and *one way from X* when it arrives. The
name of the other end is a link to its Location page when it is a Location, and plain text when it is
another kind of entry.

**Writers join a Location to another.** The section has *Join to another place*: a search for a
Location by name, the connection's name (by default `<this> - <that>`), *One way only* with its
direction (*from here* or *to here*), and *Everyone in the library may see it* (the Location's own
setting is the default). A refusal is shown as the API gave it and keeps the draft. Each connection
has *Remove*, which asks once more before it deletes the entry. The ends of a connection are not edited
in the page: remove it and join again.

**A Map page says where a place leads.** The Map page reads the links of ADR 0364 once. A selected
place that is an end of a connection lists it in the side panel: *Road to Dunmere*, *Portal, one way
from Hollowmere*, each with the Maps the other end is placed on as links (*also on the Eastern Map*).
Nothing about it is drawn on the sheet by this slice; a connection's own road is an ordinary placement,
made with the tools of ADR 0353 (the connection is found by name like any entry), and a *leads to*
mark on a pin is the only derived thing and it is words.

**What the interface does not say.** It never says *you are here*, a distance or a time, and it never
treats a connection as part-of, containment or a place. A hub is made with the API or the CLI (the hub
write of ADR 0363); the page has no form for it.

## Validation and delivery

Unit tests for the words of a direction. Browser tests against the real API: a writer joins two
Locations, one way and both ways, and the other end's page lists it from its side with the direction
reversed; a refusal (the same Location twice) keeps the draft; removing one asks twice; a portal between
two Maps is listed in the side panel of its pin with the other Map as a link; a player sees only the
connections whose two ends and the connection they may see and has no form; axe in light and dark with
the section and the panel.

## Excluded

A form for the hub write, editing the ends of a connection, a connection page of its own, drawing
a link, traveling it, and distance (slice 11).
