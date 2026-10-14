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

### The hub: Discover and the storefront

The account hub reads these routes in one page, `/discover/`: the list, and for `?repository=<id>` a repository's page ([RFC 0036](../rfcs/0036-repository-tooling.md)'s S6, without the preview). The words are those of [ADR 0194](0194-user-facing-terminology.md): library, repository, release, Owner, entry, copy, built on, public; never tenant, grant or subscription.

- **The link and the page.** The header has a "Discover" link only when `GET /discover/facets` says `enabled`. Where it does not, or the answer does not come, there is no link, and the page reached by its address says "Nothing is public yet." and shows no search. A deployment that accepts public repositories and has none listed says the same under the search.
- **The list.** A search box (a word of the name, the summary or a tag) that is sent when it is submitted, not on each keystroke, three filters from the facets (tag, game system and language: the thirty most used, each with how many repositories have it, and the value the address names if it is not among them) and the order (by name, or newest release first), which are applied when chosen. All of it is in the address (`?q=&tag=&system=&language=&sort=&page=`, what is the default left out), so a result list can be linked, and a link that is mistyped shows the list. A result is a card: the cover (or the first letter of the name, which stays where there is no cover), the name as a link to the repository's page, the summary, its tags, and one line of small print: the game system, "Release 1.2" and "309 entries". Nothing says how often a repository was copied.
- **The pager.** Twenty to a page, "Previous", "Page 2 of 5" and "Next" as links that keep the search, shown for a list of more than one page. A listing past what the API goes into (`422 discover-too-deep`) says "Narrow your search with a word or a filter." with a way back to the first page, and a page after the last says there is nothing on it and leads to the last one. A search with no result says "Nothing found. Try another word, or remove a filter." and offers "Clear the search".
- **A repository's page.** The cover, the name, the summary, the tags (each a link to the list narrowed by it), the game system, languages, entries and stats, the long description (rendered as the hub renders every description, as LorenzoScript), the licence (a link with `rel="nofollow noopener"` where it has an `https` address, "No licence stated" where it has none), the credits (name, role, a link likewise), the latest release with its notes and the earlier ones in a fold, "Built on" (each repository a link to its own page where it is public; "Not public" and a sentence saying that only a library its Owner invited can copy it where it is not) and the button "Copy to a library…". The latest release is the current one ([ADR 0288](0288-retention-and-making-a-release-current.md)), which is the newest unless an Owner made an older one current again, and the fold is then headed "Other releases". A repository that is not listed says "This repository is not listed. It may be private, it may not have a release yet, or it may not exist.", the same whichever it is. The cover is read with the token and shown from a blob, since an `<img>` cannot send it. The releases and what it is built on come from their own routes ([ADR 0287](0287-who-may-read-a-public-repository.md)), and one failing leaves the rest of the page.
- **Copying.** "Copy to a library…" opens a choice among the libraries the person is an Owner or an Organizer of (and the repositories that copy from others, as Shelf lists them), since a copy changes what the library holds; where there is none it says so and links to their libraries. "Continue" goes to Shelf's copy wizard ([ADR 0201](0201-shelf-the-copy-wizard.md)) for that library and repository, the page that checks first: the plan of the whole stack, the clashes, the review, the copy. The wizard takes its repository as a subject that is either an entry of the library's list or a public repository the library holds nothing of. For the second, Shelf asks the storefront whether the repository is listed, plans and copies as for any other, and the wizard's "Back to the repository" goes to its page on Discover, not to Shelf. A stack with a repository that is neither public nor offered to the library says so, by name, and who to ask: "X is not public, and your library is not invited to it. Ask its Owner to make it public, or to invite your library." After the copy the repository is an ordinary entry of the library's Shelf, and the last step links to its page there.

What is not in it: the preview of what a repository holds, for which the page has a marked place after "Built on" and nothing on screen (D4); the publisher, the Report link and the terms line (D6); delisting and deprecating (D8); a search by anything but a word, a tag, a game system and a language; and any count of copies.

## What the tests pin

- Only public, published repositories with a release are listed; a draft, a private one and one with no release are not, and their storefronts are `404`.
- Signed-in users only, with or without a library.
- The word matches the name, the summary and the tags without regard to case, and a wildcard is a plain character; the tag, system and language narrow exactly; the order is by name or by latest release and a sort by popularity is refused.
- A page is capped at 50 whatever is asked, the page says its size, and a listing past 1,000 deep is `422 discover-too-deep`.
- The facets count what the listed repositories say of themselves, not the private ones'.
- A storefront is the entry, the description and the profile.
- A publish, a rollback and a relabel keep the label, date and size of the current release.
- The profile of a listed repository is readable with no library and no gated read, those of a private, a draft and an unreleased one are not, and no entry or release of it is.
- In the hub, against the real API: a public repository is found by a word, by a tag, a game system and a language, and its page opens with its cover, licence, credits, releases and notes; a private repository, a draft and one that does not exist are not found; a library that holds no invitation copies it through Shelf's wizard and has it in its Shelf; a stack with a repository that is not public is said so with who to ask; there is no link where the deployment accepts no public repositories; the pager and the too-deep answer; and at 375 pixels nothing overflows and everything pressed is at least 44 pixels high. In unit tests: the address of a search both ways, the filters, the card's lines, the pager and the words.

## Not in scope

- **The preview** a storefront shows before copying, and what a visitor may look at of the entries: D4.
- **The publisher**, from the Owners' accounts, the Report link and the terms line, delisting and deprecating: D6 and D8.

## Consequences

- A listing costs one query however many repositories there are, and cannot be used to read what they hold.
- Any publish or rollback changes what a listing says, in the same transaction.
- One migration: four columns, one policy and one index on the profile.
- A library copies a public repository from Shelf's wizard like any other, which is where its checks, its clashes and its review already are; Discover adds a way to it and no second copy flow.
