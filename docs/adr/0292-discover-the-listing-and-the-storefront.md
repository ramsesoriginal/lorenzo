# 0292 - Discover: the listing and the storefront

Status: accepted, decided with the maintainer on 2026-10-14. Slice D3 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), tracked in #725. Builds on [ADR 0287](0287-who-may-read-a-public-repository.md) (anyone signed in reads a public repository), [ADR 0288](0288-retention-and-making-a-release-current.md) (the current release), [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (how a repository becomes public) and [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (the profile).

## Context

[RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §4 asks for one listing and search endpoint and one page: what is public, found by a word or by a tag, a game system or a language, ordered by name or by date and never by popularity, with a hard cap on a page and on how deep a caller can go, and a repository's page, its storefront. Its Spikes ask whether the plain case-insensitive match is fast enough or needs a trigram index or a derived column. The preview a storefront shows before copying is D4's, and the publisher, delisting and deprecating are D6's and D8's.

## Decision

### What is listed

A repository is listed when it is **public, published and has a release**; the listing is one query over the profile (`repository_profile`) and the tenant row (name and slug). Delisted and deprecated repositories leave it when those states exist (D6, D8), by one more condition in `discover.listed()`. A repository that is public but has not released yet is not listed and its storefront is `404`, the same as for a private repository, a draft and one that does not exist.

### The listing facts, on the profile

A listing shows the latest release's label and date and how big the repository is (entries, stat definitions). A document has them and opening a document for each result is exactly what [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md)'s scale spike measured against, so a publish writes them to the profile: `release_label`, `released_at`, `entry_count` and `stat_definition_count`, set whenever a release is published, made current again ([ADR 0288](0288-retention-and-making-a-release-current.md)) or relabelled while it is the current one, from the `Content` the publish loaded or the rollback read. A listing never opens a document. The migration sets the label and date of the repositories that have a release already; their size is written by their next publish.

### The wall: `discover_read`

The listing reads the profile of every public repository, so the profile gets a second `FOR SELECT` policy beside `repository_read` and `tenant_isolation`: `visibility = 'public'`, a release, a published repository, whoever asks and whatever they have asked to read (RFC 0038 §2: a second opening in the wall of ADR 0002 after ADR 0118's). It reaches **no other table**: an entry, a release, a document of a listed repository is as closed as ever outside the gated read, which a test asserts as a request with no library and no gated read.

### The routes

For any signed-in user, with or without a library (the context of `PublicReader`, [ADR 0287](0287-who-may-read-a-public-repository.md)):

- **`GET /discover/repositories`**: `q` (a case-insensitive part of the name, the summary or a tag, its `%` and `_` plain characters), `tag` (exact, case folded), `system` (exact, case folded), `language` (exact code), `sort=name` (the default) or `sort=released` (the latest release first), `page` and `size`. A result is `{id, name, slug, summary, tags, system, languages, has_cover, release: {label, released_at}, entries, stat_definitions}`: what the repository says of itself and its size, never what it holds. The cover is `GET /repositories/{id}/profile/cover`.
- **`GET /discover/facets`**: the tags, game systems and languages in use among the listed repositories with how many each, the most used first, at most a hundred of each, for the filters. It says too whether the deployment accepts public repositories at all (`enabled`, ADR 0290), so a client shows Discover only when it does.
- **`GET /discover/repositories/{id}`**: the storefront's data: the listing entry, the long description (`tenant.description`) and the whole profile (licence, credits, the preview switch). Its releases, what it is built on and its copy are the routes D2 built under `/repositories/{id}`; what may be looked at before copying is D4's.

**No ranking.** Never by how often a repository was copied: that would need the counts kept from Owners (RFC 0038 §6).

### The paging cap

A page is **at most 50** repositories, whatever `size` is asked (a bigger one is 50; the page says which size it is), and a listing goes **at most 1,000 deep** (`page` times `size`): past that `422 discover-too-deep` says to narrow it with a word, a tag, a system or a language. The page is built by hand (`items`, `total`, `page`, `size`, `pages`, the shape of every page of the API) because the paging library would refuse only past 100 and could not clamp. The cap is what keeps the directory from being walked in a few requests, with the rate limit at the edge (RFC 0038 D7).

### The spike: Discover's query at scale

Twenty thousand listed repositories in a scratch database (names, summaries of a sentence, two tags, a system and a language each; Postgres 17, default settings, measured as the migration role, which is faster than the app role by what its policies cost):

| Query | Time |
| --- | --- |
| `q` matched against name, summary and tags with `ILIKE`, by name, 20 rows | 23 ms |
| The count of the same | 23 ms |
| No word, by latest release, the page at depth 980 | 1.7 ms |
| By tag | 4 ms |

The plain match is enough at this size: a full scan of 20,000 narrow rows costs what a few index probes would. **No trigram index and no derived search column are built**, and the tags stay a column; the facets (a scan and a group) take a few tens of milliseconds at the same size. The depth cap bounds the offset a caller can ask for. What would change this is a listing in the hundreds of thousands, or an `ILIKE` that has to read wide text: neither is near.

## What the tests pin

- Only public, published repositories with a release are listed; a draft, a private one and one with no release are not, and their storefronts are `404`.
- Signed-in users only, with or without a library.
- The word matches the name, the summary and the tags without regard to case, and a wildcard is a plain character; the tag, system and language narrow exactly; the order is by name or by latest release and a sort by popularity is refused.
- A page is capped at 50 whatever is asked, the page says its size, and a listing past 1,000 deep is `422 discover-too-deep`.
- The facets count what the listed repositories say of themselves, not the private ones'.
- A storefront is the entry, the description and the profile.
- A publish, a rollback and a relabel keep the label, date and size of the current release.
- The profile of a listed repository is readable with no library and no gated read, those of a private, a draft and an unreleased one are not, and no entry or release of it is.

## Not in scope

- **The preview** a storefront shows before copying, and what a visitor may look at of the entries: D4.
- **The publisher**, from the Owners' accounts, the Report link and the terms line, delisting and deprecating: D6 and D8.
- **The hub's page.** The Discover page and the storefront are the hub's, below.

## Consequences

- A listing costs one query however many repositories there are, and cannot be used to read what they hold.
- Any publish or rollback changes what a listing says, in the same transaction.
- One migration: four columns, one policy and one index on the profile.
