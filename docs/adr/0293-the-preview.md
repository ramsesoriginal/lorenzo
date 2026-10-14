# 0293 - The preview

Status: accepted, decided with the maintainer on 2026-10-14. Slice D4 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), tracked in #726. Builds on [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing and the storefront), [ADR 0287](0287-who-may-read-a-public-repository.md) (who may read a public repository) and [ADR 0286](0286-the-read-switch-for-public-repositories.md) (what is read: the current release). It amends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)'s "structure, not text", narrowly and under the Owner's switch, as RFC 0038 §5 asks.

## Context

Looking inside a repository before copying it is what makes it worth copying, and ADR 0118 forbade it: a browse showed names, kinds and parents, never text. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §5 lets an Owner decide how much a reader may look at (`preview`: `off`, `showcase` or `public`, `showcase` unless they choose, [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md)) and which entries to feature, and promises that GM-only text never comes out. D2 built library-less reads of a public repository that showed every entry's name to anyone signed in; with a default of `showcase` that was too much.

## Decision

### Who sees what

A **holder** is a library that holds access to the repository, invited or from a copy. A **visitor** is anyone else signed in: a user with no library, or a library with no access. "Text" is Everyone's.

| Reader | `off` | `showcase` | `public` |
| --- | --- | --- | --- |
| Visitor | no entries | the featured entries, with their text | every entry, with its text, and the stat groups |
| Holder | every entry's name, kinds and parents, and the stat groups | and the featured entries' text | every entry's text |

`repository_preview.rules_for` is that table. The browse routes of D2 apply it: a visitor's `GET .../entities` is empty at `off`, the featured entries at `showcase` and all of them at `public`, and `GET .../stat-groups` is empty for a visitor below `public`; a holder's browse is as it was. A private repository is reached only by holders, so only the holder column applies to it. This tightens D2's library-less browse, which showed every name: nothing is public yet, and what a visitor sees by default is now the entries the Owner chose.

### What is looked at

- **Everyone's text only.** The information rows of an entry that are `is_public`, with their descriptions (every locale) and their pictures, and the stat values the entry holds itself (not inherited, not computed: the open question of RFC 0038 is decided as "own values"). Documents and numbers on a row are not offered. Nothing reads who knows a row, `knowledge`, or any row that is not `is_public`: the code that picks the rows skips a row that is not Everyone's before it looks at anything of it. A test runs every reader against every entry and every level and asserts that the text, the title and the picture of a GM-only row are in none of the answers, and that its picture is `404` under every entry.
- **The release, not the rows.** For a public repository what is looked at is its current release's document ([ADR 0286](0286-the-read-switch-for-public-repositories.md)): edits since are not seen. A private repository, read by its holders, is read live.
- **A cache.** A release's document is immutable, and decoding one costs 0.3 s at 5,000 entries and 1.4 s at 20,000 and holds about 100 MB (the scale spike of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md)), which a storefront with twelve featured entries and a browse would each pay again. The decoded content is kept by release id in a process-local cache bounded by the entries it holds (`release_cache_entries`, 10,000, `0` off); a release larger than the bound is not kept. The preview and the browse read it; the copy and update engines do not (they may change what they are given) and still read the document themselves.

### The routes

Each in two forms, as everything since [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md): `/repositories/{id}/...` for a signed-in user (always a visitor) and `/tenants/{tenant_id}/repositories/{id}/...` for a library (a holder if it holds access, else a visitor):

- **`GET .../preview`**: `{preview, entries}`: the Owner's switch and the featured entries with their text, in the order chosen, as far as this reader may look (none when the reader may see no text).
- **`GET .../entities/{entity_id}`**: one entry: `{id, name, kinds, parents, featured, text_visible, information, stats}`. For a reader who may not see this entry at all, `404`, the same as for one that does not exist. For a holder who may see its name and not its text, `text_visible: false` and nothing of the text.
- **`GET .../entities/{entity_id}/pictures/{payload_id}`**: a picture on a row of Everyone's text of an entry whose text the reader may read; `404` for any other row, entry or reader.

Looking needs a signed-in user, like every read of a repository.

### The showcase

`repository_showcase(tenant_id, entity_id, position)`: the entries an Owner features, in their order, a same-tenant key to the repository's own entry and gone with it. A tenant table of the repository with `tenant_isolation` and `FORCE ROW LEVEL SECURITY`, **and `repository_read`**: RFC 0038 calls it "not content", meaning a copy never carries it; the registry's meaning of content is whether the libraries and visitors that look read it through the gated read, which they do, as they do the profile, so it is registered like the profile (`copy: none`).

- **`GET /tenants/{id}/showcase`** (any member) and **`PUT /tenants/{id}/showcase`** (Owner) with `{entity_ids}`: replaces the list. **At most 12** entries (the cap RFC 0038 asks for; any entry may be featured, whether or not it is in the public catalog), each an entry of the repository, none twice: `422 showcase-invalid`, and nothing of a refused request is kept. Logged as `repository.showcase_changed`.
- **An entry added after the last release** is featured from the release that has it: the preview says nothing of one the release does not hold.

### The lock on a note

Every note on an entry of a repository, wherever it is edited, shows a lock when it is Everyone's, "visible to libraries that copy this", with "make GM only" in one click: an edit of content that needs no new route (the information `PATCH` of [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md) sets `is_public`), so it is the editors' to show, which the hub section below lists: the ones that have it and the ones with no such surface.

### The hub: the preview, the showcase and the lock

The account hub's words are those of [ADR 0194](0194-user-facing-terminology.md): library, repository, release, Owner, entry, copy; never "tenant", "grant" or "subscription". One drawing, `components/Preview`, serves a repository's page in Discover and in Shelf; it renders what the API answered with and decides nothing of what a reader may see. A `PreviewSource` (`lib/previewApi.ts`) is the one thing that differs: a visitor's (`/repositories/{id}/...`) or a library's (`/tenants/{id}/repositories/{id}/...`). The reads of the preview do not go through the hub's cache of other reads: the Owner's switch can change at any moment and the text was chosen to be shown, so a read is never answered from what an earlier one held. A picture is fetched with the token and shown from a blob, as the cover is.

- **The storefront's "Look inside"**, under "Built on", from the Owner's switch as the preview route answers it. At `off`: "The Owner has not opened this repository for a look inside." At `showcase` with nothing featured: "The Owner has not chosen entries to show yet." Otherwise the featured entries as cards, in the Owner's order: the name, a "Featured" pill, its kinds ("Item"), "Inherits from" its parents, each row of Everyone's text under its title (rendered as LorenzoScript, in the reader's language where there is one), its pictures, and its own stat values under the stat's group. At `public` the featured ones come first, then "All entries": a "Find an entry" search (sent after a pause in typing), "20 of 134 entries", "Show more", "No entry matches.", and a "Look" button on each, which opens the entry in a dialog from `GET .../entities/{id}`. An entry that is not open to look at is said so in the dialog, as it is a `404` to the API; a failed read says so and leaves the page. The preview is read at the same time as the releases and what the repository is built on, and each fails on its own.
- **Shelf's repository page** has the same section for a library that holds the repository, through the library's routes, headed "Look inside", between "What is inside" and "Built on". A holder sees every name in its list of entries as before, and a "Look" button on each wherever the Owner opened anything to look at (not at `off`). An entry whose text the switch does not show opens with its name, kinds and parents and "The Owner has not opened the text of this entry for a look." At `off` the section says "The Owner has not opened the text of this repository for a look. You can see the names of its entries." The caption under "What is inside" says that only names show until the library copies the repository, and that what its Owner has opened for a look is under "Look inside".
- **Studio's "What people can look at"**, on the Overview, an Owner's, for any repository (the holders of a private one look inside too): the three choices of the "Make public" dialog as plain radios, in the same words, saved when chosen with `PATCH /tenants/{id}/profile`; and "Featured entries": the list in order with Up, Down and Remove on each (named "Move up: Owlbear"), "3 of 12 entries featured. You can feature up to 12 entries.", an "Add an entry" search of the repository's own entries (what is featured is not offered again, and the search is closed at twelve), and "Visitors read the latest release, so an entry you add is shown from the next release." Each change is saved as it is made with `PUT /tenants/{id}/showcase` and says "Saved."; a refusal changes nothing, is said, and the card reads what the API holds again. An Organizer and an Author do not see the card and nothing is asked of the API for them.
- **The lock on a note** is in the editors that open a repository's entries and write notes:
  - **Bench**, which is only ever about a repository. A note's audience is part of what the command layer reads (`TextDoc.isPublic`), and making it GM only is a command like the others, `note.set-public`: shown at once, sent through `PATCH /tenants/{id}/information/{id}` with `is_public`, kept waiting while there is no connection, compared with what the server has when it is sent (a note that someone else made GM only first is sent as nothing) and undone with Undo. Under each note: "GM only", or, for one that is Everyone's, a lock with "Visible to libraries that copy this" and "Make GM only". A note written in Bench is GM only already.
  - **Lorenzo Beings**, which lists every library and repository a person is a member of and opens a repository's beings: a note of a being whose library is a repository shows the same lock and words, and "Make GM only" for whoever may write notes there, as one edit of the row. In a play library nothing is shown.
  - **inventory-web has no such surface.** It does open a repository's items, but shows its writing sections only to a GM of a campaign of that library, and a repository has no campaign; its Notes are the notes of an item instance, which belongs to play. Its Information section is never shown for a repository's entry, and nothing was added there. The hub has no editor of notes. The loot bot's `/note` and the command line's inventory notes write in play libraries (the command line's are GM only), and what the command line's importer writes into a repository is descriptions, not notes.

## What the tests pin

- The table: a visitor with no library and a library with no access see nothing at `off`, the featured entries in their order at `showcase` and everything at `public`, with their text, kinds, parents and own stat values; a holder always sees every name and the text the switch says.
- A row that is not Everyone's, its title, its text and its picture, comes out of no route, for any reader, at any level; a picture is read only where its text may be and only under its own entry.
- What is looked at is the release and not what was edited after it; an entry added after the release is skipped until a release has it.
- A private repository is looked at by its holders and by nobody else.
- The showcase: kept in order, at most twelve, no repeats, none that is not an entry of the repository, nothing kept of a refused request; the Owner's alone.
- A release read for the preview is decoded once, again for the next release, and not kept when the setting is `0`.
- In the hub, against the real API: a visitor sees exactly the featured entries in the Owner's order with their text, picture and stat value, no entry that is not featured and no list; at `public` the list, its search and an entry's dialog; at `off` the quiet line; at `showcase` with nothing featured its line; the preview follows the switch when the Owner changes it; a library that holds the repository sees every name and the text the switch says, and no text at `off`; the Owner's choice and list are kept and ordered in Studio, twelve is the most, an Organizer does not see the card, and what Studio features is what a visitor reads. At 375 pixels nothing overflows and everything pressed is at least 44 pixels high. On every one of these pages, and in every answer of the API they were given, the text and the title of a GM only row and the address of its picture appear nowhere. In unit tests: the line of each level, the words, an entry's lines, the pick of a description by language, the moves on the list.
- In Bench: the command (shown at once, sent as one change, undone, waiting while offline, nothing sent when it is already so, refused where the note is gone), the transport and the page. In Beings: the lock in a repository and none in a library.

## Not in scope

- **Inherited and computed stat values** in the preview: own values only, until it is shown they cost nothing.
- **A SQL path for browsing a large public repository** (R2): the cache removes the repeated decode, not the first.
- **The publisher, the gates before launch and deprecating**: D6 and D8.

## Consequences

- An Owner decides, and a visitor sees by default only what the Owner chose to show: the featured entries.
- GM-only text cannot come out of a preview: the rows are chosen by `is_public` before anything else is read.
- One migration: the showcase table, its policies and its index.
