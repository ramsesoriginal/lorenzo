# 0334 - Whereabouts: where something is, for one character

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 2.

## Decision

`GET /tenants/{tenant_id}/entities/{entity_id}/whereabouts?relative_to={character_id}` answers where an
entry is, as one character would say it, in four words and at most one name. It is a read for
anyone who may see the entry; it asks nothing of axes, depth or coordinates and shows none.

```json
{"state": "with_you"}
{"state": "stashed"}
{"state": "stashed", "place": {"id": "...", "name": "Blackstaff Tower", "slug": "blackstaff"}}
{"state": "elsewhere", "place": {"id": "...", "name": "Ceres Dock 4", "slug": null}}
{"state": "unknown"}
```

**Who can ask.** A participant of the library. The entry must be visible to them and `relative_to` a
Character they reach (the reach `controlled-by` uses); otherwise the same 404 as a missing entry.

**The rules.** Containment first, the way the inventory reads it:

- `with_you`: the character is among the entry's surroundings (a container above it, or the owner of
  a thing in no container, ADR 0123), or the entry is the character. No place is named for what the
  character carries.
- Otherwise the entry has a place when the top of its chain is placed (`entity_location`, ADR 0333)
  or is itself a Location. If it has none, or the reader cannot see that Location, the state is
  `unknown`, whatever may be recorded.
- The character has a place the same way. Two places are on one branch when they are the same
  Location, or one is a part of the other, seen as the reader sees the tree, hidden levels skipped
  (ADR 0330). The entry is `stashed` when its place is on one branch with the character's, or the
  character has no place; `elsewhere` when both are known and are on different branches.
  `elsewhere` is refined by frames when they exist, and by nothing else.
- A place is named only when it differs from the character's own, and only by what the reader may
  read of it: its name and link name.

**Nothing leaks.** The answer is a function of the rows the reader can see: a hidden Location is
`unknown`, never an ancestor in its stead, and the answer for a hidden level in between is
byte-identical to the answer when the level is absent. There is no depth, path or ordinal in it,
and an entry that is not visible, a character that is not reached and a missing id answer alike.

**Built for more than one entry.** The resolver takes a list of entries, one statement for the
chains and one for the places, and the route calls it with one. The inventory headings of the
bot and the GM's address read (slice 3) reuse it; a batched route is added when one needs it.

## Validation and delivery

Tests: each state; carried through a container and by ownership; a place on a contained entry
ignored; places on one branch and on two, with a hidden level in between; a hidden place; the 404s;
and parity of a hidden place with no place at all. It is one API pull request with ADR 0333.

## Excluded

The GM's `address` read, axes and frames, a `where` block on the owned-by groups and the bot's
`/inventory` headings (they call this resolver in their own slices), and any way to ask for
another point in time.
