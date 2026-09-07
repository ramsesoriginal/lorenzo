# Entities, knowledge, and visibility

## Everything is an entity, and everything has text

There's no tier of "important" things that get full treatment while everything else doesn't. A unique legendary artifact and a random unnamed goblin ("goblin #17") both get the same kind of record: identity, state, and text. So does a plane, a pantheon, an organization, a shop and its inventory, a disease, a wildlife population, a town.

**Beings can be items, and items can act like beings** — the model doesn't force a hard split between "creature" and "object." A sword can be sentient. A summoned creature can be tracked like inventory. Treating these as one overlapping concept rather than two exclusive categories is deliberate.

## State is game-system-specific

The same entity can carry different stats/state depending on which game system is looking at it — a character might have D&D stats in one campaign and Warhammer Wrath & Glory stats in another, if the same underlying repository gets used across systems (see [repositories](repositories.md)).

## Text is always split by audience

Every piece of text — lore, notes, stats, descriptions — is split into at least these tiers, not stored as one blob:

- **GM-only** — never shown to players.
- **Visible to everyone** in the game.
- **Visible to a subset** of players (e.g. only the character who discovered something).
- **Player-authored** — written by players themselves, not the GM.

This split is what lets one entity have a public description, a GM's secret notes, and a player's personal journal entry about it, all attached to the same underlying thing.

## Knowledge is tracked, not assumed

"Everyone in the room knows X" isn't good enough. Lorenzo needs to track **who knows what, and as of when** — including who has met whom, and what they learned about each other at that meeting. Knowledge is a fact about a specific character at a specific point in the story's timeline, not a global flag on the piece of lore itself.

This is genuinely unbuilt design space — exactly how "knowledge" gets represented (a simple visibility flag vs. a full event log of what was learned when) isn't decided yet.
