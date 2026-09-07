# Repositories

A **repository** is a reusable setting: a published campaign setting, a homebrew world, or an entire multiverse, packaged as something a game can draw on.

- A world can belong to **no repository, one, or many** at once. Faerûn, for instance, is part of the official D&D Forgotten Realms setting — but a given table's Faerûn might *also* be part of a homebrew repository layered on top that changes or adds things.
- A game, book, or campaign can draw on **one repository or several at once** — e.g. a D&D campaign set in Faerûn that also pulls in Marvel-multiverse content.
- Multiple games can relate to the same repository in different ways:
  - Several campaigns can **share one repository's live state** — what happens in one is visible/real in the others.
  - Several campaigns can each get their **own instance** of the same starting repository, diverging independently from there.
- Repositories aren't tied to one game system — content from one system's repository can end up referenced inside a game running a completely different system.

## Why this matters for the data model

This is why a world can't just "belong to" one campaign the way a typical single-tenant app would model it. The same location, item, or character might need to be visible from multiple campaigns (the shared-state case) or need to be copied-and-diverged (the instanced case), and a piece of content's *origin repository* is a different fact from *which campaign(s) currently use it*.
