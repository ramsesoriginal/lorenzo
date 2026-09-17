# 0046 - GM reachability widens to the party's surroundings, not just their inventory

Status: accepted

## Context

The brief that started this round of API additions claimed campaign GMs can only see GM-private `Information` if they also hold the tenant-wide `ORGA` role. Grounding that claim against the current code found it's narrower than stated: `information_visibility.py`'s `gm_reachable_entity_ids` bypass ([ADR 0035](0035-campaign-scoped-gm-visibility.md)) already lets a campaign's GM see GM-private info about anything their own players' characters own or carry, with no `ORGA` needed - `resolve_information_visibility` roots `entity_access.reachable_entity_ids` at the campaign's own `CharacterPlayer` roster and walks ownership + containment downward from there.

The real, narrower gap: that walk only ever goes *down* from a PC (what it owns, what's inside what it owns). It never goes *up* - a GM-private secret about the room a party is standing in, an NPC also standing there, or a locked chest in the corner isn't reachable at all unless some PC happens to already own it. Asked directly, the user chose to close this by widening the reachability walk itself (not by adding a new visibility flag) - see [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)'s Context section for the parallel discussion this same grounding pass surfaced about item-instance write authorization.

This is possible without inventing a new domain concept: `Containment` already accepts *any* entity as its child, characters included - RFC 0001 states this directly ("a character in a room" is one of `containment`'s three worked examples), and `apps/api/tests/test_api_characters.py` already places a character inside a `Tavern` entity via `Containment` in an existing test, confirming this is a real, already-supported pattern, not a hypothetical one.

## Decision

New `entity_access.containing_ancestors_ids(session, *, entity_ids, tenant_id)`: walks `Containment` **upward** (child → parent, repeatedly) from a set of entities to every entity that transitively contains any of them - the exact mirror of `recursive_descendants_cte`'s existing downward walk, same cycle-safe path-array guard technique, just the join direction inverted. Returns ancestors only, not `entity_ids` themselves - matching `reachable_entity_ids`' own convention of taking the "plus itself" step at the call site, not baking it into the traversal helper.

`information_visibility.resolve_information_visibility`'s GM branch: the root set fed into `reachable_entity_ids` changes from `gm_character_ids` alone to `gm_character_ids | containing_ancestors_ids(gm_character_ids)` - every container a campaign's PC currently sits inside (a room, a building, nested up to the world root, *if and only if* a character entity actually has a `Containment` row placing it there). `reachable_entity_ids`'s existing downward walk from those extra roots then naturally pulls in the room itself, everything else in the room, and everything nested inside those - no change needed to `reachable_entity_ids` itself, only to what roots it's given.

## Not in scope

GM-private info about an entity that isn't structurally near where any of the campaign's PCs currently are (an NPC three rooms away nobody has approached yet) - still not covered, deliberately. Closing that would require a real campaign-to-entity link the domain doesn't have (the heavier option the user declined in favor of this one) - named here as an honest, residual scope limit rather than solved partway.

## Consequences

- `entity_access.py`: new `containing_ancestors_ids` (and its own private `_containing_ancestors_cte` helper, mirroring `recursive_descendants_cte`'s shape).
- `information_visibility.py`: `resolve_information_visibility`'s GM branch widens its root set as described. No change to `reachable_entity_ids`, `can_self_manage_entity`, or RFC 0005's self-or-managed write authorization - this ADR only touches the GM-visibility read path.
- A campaign's GM can now see GM-private secrets about the scene their players are actually in - the room, its other contents, an NPC standing there - without needing a separate tenant-wide `ORGA` role, closing the concrete gap the brief named (even though the brief's own framing of *why* it happens was broader than the actual cause).
