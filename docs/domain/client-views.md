# Client views

The backend is meant to hold the full complexity described in the rest of `docs/domain/`. Nothing that uses the API is meant to expose all of it at once — every client is a **narrower, audience-specific slice**.

## Worked example: an inventory manager

A concrete, small version of this: a Discord bot and a mobile app that, together, just manage inventory.

- **Players** see what they have and where they have it — stats and notes, but only the ones the GM chose to make visible to them (see [visibility](entities-knowledge-and-visibility.md)).
- The **Discord bot** helps with mechanical tasks like splitting loot among a party.
- The **GM** gets a web view across every player and their possessions, including secret notes/stats players never see.

## Why this matters for app boundaries

This is part of why [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md) allows many apps of the same "kind" rather than one do-everything web app: a GM-facing console and a player-facing companion app are legitimately different tools with different audiences, even though they're both "web frontends" for the same underlying data.

## Future direction (not being built yet)

The inventory-manager idea was described as a possible first step toward something bigger: connecting inventory to **events** (past, present, predicted future), and a **ledger of ownership** — tracking ownership provenance over time, not just current possession. This is deliberately not scoped yet; it's recorded here so it doesn't get lost, not as a commitment to build it next.
