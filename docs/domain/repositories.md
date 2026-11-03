# Repositories

A **repository** is a reusable setting: a published campaign setting, a homebrew world, or an entire multiverse, packaged as something a game can draw on.

- A world can belong to **no repository, one, or many** at once. Faerûn, for instance, is part of the official D&D Forgotten Realms setting — but a given table's Faerûn might _also_ be part of a homebrew repository layered on top that changes or adds things.
- A game, book, or campaign can draw on **one repository or several at once** — e.g. a D&D campaign set in Faerûn that also pulls in Marvel-multiverse content.
- Multiple games can relate to the same repository in different ways. The following describes the domain possibilities; the implemented play model is a copy with updates chosen by the library ([RFC 0024](../rfcs/0024-repositories.md)):
  - Several campaigns can **read the same repository live** — if the repository's own content is updated (new lore, a correction, an added NPC), every campaign still referencing it sees the update next time it's read.
  - Several campaigns can each get their **own instance** of the same starting repository, diverging independently from there — a copy that no longer sees later updates to the source repository.
- Repositories are read-only from a campaign's (or library's, what the API calls a tenant) point of view: **no campaign or game ever writes into a repository**. Updating a repository's own content is a separate authorship process, not something that happens as a side effect of play: its authors are the members of the repository itself, and campaigns that copied it take its changes one by one, when they choose to (see [RFC 0024](../rfcs/0024-repositories.md)). Private repository reads use the authors' live content; public repository reads use its current release document ([ADR 0286](../adr/0286-the-read-switch-for-public-repositories.md)). Public discovery and previews are built, but public repositories remain disabled by default until the remaining launch gates are implemented ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)).
- Repositories aren't tied to one game system — content from one system's repository can end up referenced inside a game running a completely different system.
- Who works on a repository: its Owner publishes and hands out access, and an **Author** edits its content only ([RFC 0040](../rfcs/0040-authors-and-invites.md), [ADR 0219](../adr/0219-the-author-role.md)). Libraries have Authors too.
- What a library copies: an Owner publishes a **release** of a repository, a library copies it and takes updates as it chooses, and one repository can be built on another ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), [RFC 0036](../rfcs/0036-repository-tooling.md)).
- A repository its Owner has made public can be found and copied from the Discover page, where the feature is switched on ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)).

## Why this matters for the data model

This is why a world can't just "belong to" one campaign the way a typical single-tenant app would model it. The same location, item, or character might need to be _read_ live from multiple campaigns (the live-read case) or be _copied_ and diverge (the instanced case) — but a campaign never mutates a repository directly, only its own copy or its own tenant-scoped data. A piece of content's _origin repository_ is a different fact from _which campaign(s) currently read or copied from it_.
