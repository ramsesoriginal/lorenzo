# 0331 - A Location may be any kind

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 1.

## Decision

An entry may be a Location and any other kind at once: item, item instance, being, character,
fact, event, calendar, calendar period, observance, clock, scene, session. A sentient castle, a
Bag of Holding with an interior, a ship, a calendar period that is also a place, a Scene that is
set in a Location-entry of its own: none is refused for being a Location. Every such pair is
allowed in both directions through the kind API, and a Location marker is valid beside every other
marker by construction (it carries no payload).

Today's refusals stay exactly as they are between the other kinds. Scene, Session, Scene appearance
and clock still do not combine with kinds other than Location. A Fact still is not a physical
container, and the physical-container guard (`require_physical_container`) still refuses the
calendar family and Facts as containers whether or not they are also Locations. A Location does not
change what the other kind may do: a period that is also a Location keeps its coordinates and
structural parents, which are never a position.

**Proof.** The publish gate ([ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md)) stays: a kind combination that is not proven cannot be
published. A generated, parametrised test over the Location pairs proves each one at the database
level: create, publish, copy and release round trip, with the Location and the other kind both
present. Each lifted refusal has a regression test that the same refusal between two other kinds is
unchanged. The generated matrix covers Location only; a declarative table of refused pairs for all
kinds is a separate refactor. `("location",)` and each `(kind, "location")` pair join
`PUBLISHABLE_KIND_COMBINATIONS`; a triple is not published until proven.

**Containment.** Adding the Location marker to a container, such as a bag, changes no existing read
except one string in `kinds`: what a bag holds stays "carried in", and a Location's own part-of
subtree is its interior. The two are independent facts, authored separately.

## Validation and delivery

Part of RFC 0048 slice 1. The kind-matrix tests, the release-document golden file and the
repository copy tests are extended in the same pull request as the marker.

## Excluded

Maps, connections and frames as kinds (their own slices decide their pairs); a refused-pairs data
table; combining Location with kinds that do not exist yet.
