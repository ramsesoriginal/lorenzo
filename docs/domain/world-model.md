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

Exactly how far this needs to be modeled — a shared "true" timeline vs. many independent local ones, and how causality gets tracked across them — is genuinely open. Flagged here rather than decided; it's the kind of thing that needs an RFC once it's actually being built, not an assumption baked into this doc.
