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

Exactly how far this needs to be modeled — a shared "true" timeline vs. many independent local ones, and how causality gets tracked across them — is genuinely open. Flagged here rather than decided; the proposed [RFC 0028](../rfcs/0028-time-causality-and-calendars.md) explores time and causality without making them implemented behavior. The non-containment address axes are likewise proposed in [RFC 0026](../rfcs/0026-world-model-axes-and-address.md).

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
