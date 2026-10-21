# Entities, knowledge, and visibility

## Everything is an entity, and everything has text

There's no tier of "important" things that get full treatment while everything else doesn't. A unique legendary artifact and a random unnamed goblin ("goblin #17") both get the same kind of record: identity, state, and text. So does a plane, a pantheon, an organization, a shop and its inventory, a disease, a wildlife population, a town.

**Beings can be items, and items can act like beings** — the model doesn't force a hard split between "creature" and "object." A sword can be sentient. A summoned creature can be tracked like inventory. Treating these as one overlapping concept rather than two exclusive categories is deliberate.

In the product an entity is an **entry**, and what it is (an item, a being, later a place or a clock) is its **kind**: a sentient sword is one entry of two kinds, not two things. See [identity §14.3](../brand/identity.md#143-terminology).

## State is game-system-specific

The same entity can carry different stats/state depending on which game system is looking at it — a character might have D&D stats in one campaign and Warhammer Wrath & Glory stats in another, if the same underlying repository gets used across systems (see [repositories](repositories.md)).

## Text is always split by audience

Information — lore, notes and descriptions — is split by audience, not stored as one blob:

- **GM-only** — never shown to players.
- **Visible to everyone** in the game.
- **Visible to a subset** of players (e.g. only the character who discovered something).
- **Player-authored** — written by players themselves, not the GM.

This split is what lets one entity have a public description, a GM's secret notes, and a player's personal journal entry about it, all attached to the same underlying thing. The current stat vocabulary and effective stat values are readable by participants; information's audience rules do not make an individual stat value secret.

## Knowledge is tracked, not assumed

"Everyone in the room knows X" isn't good enough. Lorenzo needs to track **who knows what, and as of when** — including who has met whom, and what they learned about each other at that meeting. Knowledge is a fact about a specific character at a specific point in the story's timeline, not a global flag on the piece of lore itself.

The current system records which characters, players or groups may read a piece of information, alongside public and GM-only audiences ([ADR 0028](../adr/0028-knowledge-and-group-membership.md), [ADR 0109](../adr/0109-player-knowers-knower-listing-and-information-list.md)). Optional learning records can associate a being with particular Information at an Event ([ADR 0314](../adr/0314-optional-event-learning-records.md)). These authored records do not grant access or reconstruct a historical access ledger. The broader temporal model remains proposed in [RFC 0028](../rfcs/0028-time-causality-and-calendars.md).

## Canonical facts are information anchors

A canonical fact is a true statement about the world, kept as an entry of its own rather than
belonging to one campaign. It can hold descriptions, notes and pictures, and LorenzoScript can
link to it and from it. Its optional **About** relations say explicitly which other entries it
concerns: a lich, a weapon, both, or none. Those subjects do not replace ordinary text links.

A fact can conceal its existence and name together. Its audience and each piece of information's
audience are set separately: a character must be allowed through both to read that part.
Sharing a note never silently reveals its containing fact. Current group membership can grant
access; it does not establish a permanent memory or a story-time learning event.

## Collaborative Events and Facts

Authors and GMs manage Events and Facts throughout a library; a GM grant in any campaign is
sufficient. Players can create Events and Facts, edit their own entries and add their own notes
to entries they can see. Entry creation does not grant editing of causal assertions or learning
records. A creator cannot read or change someone else's private Information through authorship
of the containing entry alone ([ADR 0316](../adr/0316-collaborative-events-facts-and-participant-audiences.md)).

An Event and each of its Information bundles can independently be shared with current
participants, reached through the beings a player controls. Participation changes affect that
present access, without creating learning or permanent memory. Facts have no participants.

Groups can contain any being, including untracked NPCs. Player control and roster seats still
require Characters. Group knowledge follows direct current membership; it does not propagate
through nested groups. GMs and Authors can create an ordinary group from an Event's current
participants. The preview makes clear that the group's member list is readable by library
participants. The group is a snapshot, not a live alias for the Event's participants, and creating
it does not open the Event or its notes. Removing Character tracking preserves group membership;
deleting the Being removes it.
