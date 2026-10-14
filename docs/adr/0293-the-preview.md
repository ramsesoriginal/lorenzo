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

Every note on an entry of a repository, wherever it is edited, shows a lock when it is Everyone's, "visible to libraries that copy this", with "make GM only" in one click: an edit of content that needs no new route (the information `PATCH` of [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md) sets `is_public`), so it is the editors', Bench's and the inventory app's, below.

## What the tests pin

- The table: a visitor with no library and a library with no access see nothing at `off`, the featured entries in their order at `showcase` and everything at `public`, with their text, kinds, parents and own stat values; a holder always sees every name and the text the switch says.
- A row that is not Everyone's, its title, its text and its picture, comes out of no route, for any reader, at any level; a picture is read only where its text may be and only under its own entry.
- What is looked at is the release and not what was edited after it; an entry added after the release is skipped until a release has it.
- A private repository is looked at by its holders and by nobody else.
- The showcase: kept in order, at most twelve, no repeats, none that is not an entry of the repository, nothing kept of a refused request; the Owner's alone.
- A release read for the preview is decoded once, again for the next release, and not kept when the setting is `0`.

## Not in scope

- **The hub's storefront preview and the editors' lock**, below.
- **Inherited and computed stat values** in the preview: own values only, until it is shown they cost nothing.
- **A SQL path for browsing a large public repository** (R2): the cache removes the repeated decode, not the first.
- **The publisher, the gates before launch and deprecating**: D6 and D8.

## Consequences

- An Owner decides, and a visitor sees by default only what the Owner chose to show: the featured entries.
- GM-only text cannot come out of a preview: the rows are chosen by `is_public` before anything else is read.
- One migration: the showcase table, its policies and its index.
