# Repositories

A **repository** is a reusable setting: a published campaign setting, a homebrew world, or an entire multiverse, packaged as something a game can draw on.

- A world can belong to **no repository, one, or many** at once. Faerûn, for instance, is part of the official D&D Forgotten Realms setting — but a given table's Faerûn might _also_ be part of a homebrew repository layered on top that changes or adds things.
- A game, book, or campaign can draw on **one repository or several at once** — e.g. a D&D campaign set in Faerûn that also pulls in Marvel-multiverse content.
- Multiple games can relate to the same repository in different ways:
  - Several campaigns can **read the same repository live** — if the repository's own content is updated (new lore, a correction, an added NPC), every campaign still referencing it sees the update next time it's read.
  - Several campaigns can each get their **own instance** of the same starting repository, diverging independently from there — a copy that no longer sees later updates to the source repository.
- Repositories are read-only from a campaign's (or tenant's) point of view: **no campaign or game ever writes into a repository**. Updating a repository's own content is a separate authorship process, not something that happens as a side effect of play — not designed yet, a future problem.
- Repositories aren't tied to one game system — content from one system's repository can end up referenced inside a game running a completely different system.

## Why this matters for the data model

This is why a world can't just "belong to" one campaign the way a typical single-tenant app would model it. The same location, item, or character might need to be _read_ live from multiple campaigns (the live-read case) or be _copied_ and diverge (the instanced case) — but a campaign never mutates a repository directly, only its own copy or its own tenant-scoped data. A piece of content's _origin repository_ is a different fact from _which campaign(s) currently read or copied from it_.
