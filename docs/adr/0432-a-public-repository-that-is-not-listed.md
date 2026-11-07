# 0432 - A public repository that is not listed

Status: accepted. Slice H2 of [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), tracked in #1064. Builds on [ADR 0286](0286-the-read-switch-for-public-repositories.md) (a public repository is read through its current release), [ADR 0287](0287-who-may-read-a-public-repository.md) (who may read one), [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing, its facets and the storefront, and the `discover_read` policy), [ADR 0303](0303-operator-delist.md) and [ADR 0384](0384-deprecating-a-repository.md) (the two other ways a public repository leaves Discover), [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (the flips) and [ADR 0385](0385-studios-profile-editor-and-the-cover-controls.md) (Studio's profile and visibility cards). The choices marked *default* are the answers the maintainer gave to the RFC's open questions or the smallest ones; each is listed as a question at the end.

## Context

A public repository is on Discover: anyone signed in finds it, opens its page and copies it. Some Owners want the second and third without the first: a repository for the people they send the address to, a playtest, a supplement for one group. [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md) calls it *public but unlisted*. It stands alone and needs nothing of the other slices.

## Decision

### The flag

`repository_profile.listed` is a boolean, true by default: whether Discover lists the repository while it is public. An Owner of a public repository may turn it off and on again.

It is **not a second kind of visibility**. An unlisted repository is public in every other way: the gate function, the profile's `repository_read` policy and the insert policy of `repository_subscription` are about who may read or copy a repository by its address, and an unlisted one is read and copied like any public one, so none of them changes. The summary, the terms line, the release, the quotas, the cooldown, the skew gate, delisting and retiring all apply as they did. The flag only answers one question: is it on the list.

A check ties it to the visibility, `listed OR visibility = 'public'`: not listed is a fact about a public repository only. The flips keep it true: a repository that is made public starts listed, and `make_private` sets it back to listed in the same transaction as the visibility, so a repository made public again is on Discover as every repository made public is, and the Owner chooses again. The alternative, keeping the flag across a private spell, would publish a repository as unlisted without its Owner having looked at the switch since it was a different repository to them. The check makes a flip that forgets fail loudly instead of leaving a repository quietly unlisted: **H3's flip from public to protected has to set it back too**, and the check will say so if it does not.

### Who writes it, and when

`PATCH /tenants/{id}/profile` takes `listed: true | false`, for an Owner, as the rest of the profile is (an Organizer and an Author are `403`; every member reads it as `listed` on `GET /tenants/{id}/profile`, and a visitor and a library read it on the profile they already read). `null` and any other word are `422`.

For a repository that is **not public**, `listed: false` is **refused**, `409 repository-not-public`, in the same request as everything else in it (nothing is kept): there is no listing it is on to leave. It is refused and not ignored, so that an Owner is never told "saved" for a switch that did nothing. `listed: true` is what a private repository is already, so it is accepted and changes nothing (it is not logged either). A change is logged as `repository.profile_updated` with `fields=listed`, names only, like every field of the profile.

`GET /tenants/{id}/flip-check` carries `listed` too, so that the visibility card has what it needs in the read it already makes.

### What Discover leaves out, and what it keeps

The rule that says what Discover lists was written in three places that must say the same thing, and this changes all three:

- `discover.listed()`, the statement of the listing, its search (`q`, tag, system, language) and its page (`search`), is now `public_repository()` and `listed`. `public_repository()` is the former statement, public, published, with a release, not delisted, not retired, which is also what a storefront is read through.
- `_LISTED_SQL`, the statement of the facets (tags, systems, languages), gains `p.listed`.
- `discover_read`, the second `FOR SELECT` policy on the profile ([ADR 0292](0292-discover-the-listing-and-the-storefront.md), narrowed by ADR 0303 and ADR 0384), gains `listed`, so that a listing query that forgot the condition still could not read an unlisted repository's profile through it. It is the only policy that says "listed"; `repository_read` and the function say "may read", and `discover_read` is the policy a visitor reads with no repository context.

A test pins the three together: every combination of what the rule reads (public or not, released or not, published or not, delisted or not, retired or not, listed or not; the 48 the check allows), written straight in the database, is listed by the Python statement, by the facets' SQL and by `discover_read` as the restricted role (in no tenant and in a library) exactly when all six hold. The same test as the restricted role shows that an unlisted profile is not read through `discover_read` by a visitor or a library, is read through the gated read, and is read by its own tenant.

`GET /discover/repositories/{id}` (the storefront) is **not** a listing: it opens for any signed-in user who has the address, for any public repository, listed or not. It is read now through the gated read (`discover.storefront_of`, which replaces `listing_of`), whose public branch answers for exactly what the storefront answered for (published, public, not delisted, not retired) and not through `discover_read`, which answers only for what is listed. It is still `404` for a private repository, a draft, one with no release, a retired and a delisted one, the same as for one that does not exist. The `/repositories/{id}/...` reads (profile, cover, releases, entries, stat groups, dependencies, preview, an entry and its pictures) already went through the gated read and are unchanged: they work for an unlisted repository, which the tests show one by one. A library copies it by its address (`copy-plan` and `copy`) and takes its releases as it does a listed one; the Owner learns of those copies as a number, as before ([ADR 0299](0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md)).

There is no other search of public repositories: the entry search, the pickers and the relationship reads are inside a tenant, and the operators' lists (admin) read every repository whatever its flag.

**The hub's cache** ([ADR 0292](0292-discover-the-listing-and-the-storefront.md) kept it out of the listing and the storefront on purpose, `force: true`, and that stands) holds the facets for up to half an hour, and a write of the person who made it empties the cache. So an Owner who turns the switch sees the change at once; another person's session may still show a tag or a game system of that repository in the filters for the time the cache holds it. A facet is a word and a count, never an address, and the listing and the storefront it would lead to are read fresh.

### What an Owner sees

- **Studio, visibility card.** For an Owner of a public repository, under the button: a switch "Listed on Discover", saved when it is turned, with a sentence for each state and the link "Open its page", which is the address to share, since nothing on screen says it otherwise. On: "Anyone signed in to Lorenzo can find it on Discover." Off: "It is not on Discover, and no search finds it. Anyone who has its address can still open its page and copy it, so share the address only with people you want to have it." It is not offered for a private repository, an Owner who is not one (the card is the Owner's), and a repository the platform's operators took off Discover or its Owner retired: it is off Discover already, and a second switch beside the note would say the opposite of it.
- **The storefront.** For a repository that is not listed, its Owners read at the top of the page: "This repository is not listed on Discover. Only people who have its address can open this page." Nobody else is told anything: a visitor with the address sees the same page as for any public repository. The Owner is known from the person's own libraries and repositories, which are read after the page is drawn and cannot hold it up.
- **The words.** [Identity §14.3](../brand/identity.md#143-terminology) gains "Listed on Discover". The page that says a repository cannot be opened (a `404`) no longer says "not listed", which now means something exact: "This repository cannot be opened. It may be private, it may not have a release yet, it may have been retired, or it may not exist."
- **A phone.** One column, the switch a row of 44 pixels, the note inside the width.

## The RFC's open questions, as settled for this slice

H2 touches none of them. The defaults of the common brief stand for the slices after it.

## Not built

- A "Listed on Discover" choice in the Make public dialog: a repository is made public listed, and its Owner turns the switch on the card after.
- A way to copy the address in Studio beyond the link "Open its page".
- A notice to the libraries that hold a repository when its Owner leaves it off Discover: it changes nothing a library has or reads.
- Leaving a private repository off a listing in advance, so that it is unlisted from its first release: refused by design (above).
- A command-line command: `lorenzo api PATCH /tenants/<id>/profile --data '{"listed": false}'` does it.

## What the tests pin

- The API, with the database as the restricted role: the default (a public repository is listed and says so, to its members and to a visitor); turning it off removes the repository from the listing by its word, its tag, its system, its order, its total and the facets, for a visitor and for a library's user, and turning it on puts it back; the storefront and every `/repositories/{id}` read answer for an unlisted repository, with the profile saying `listed: false` and nothing else changed; a library copies it by its address, updates it and the Owner counts it; retired and delisted stay closed to a visitor whether it is listed or not.
- Who may: an Owner turns it off and on, an Organizer and an Author read it and are `403`, a stranger is refused; a repository that is not public refuses `false` (`409 repository-not-public`) and keeps nothing of the request, accepts `true` as nothing and logs nothing; `null` and a word are `422`; a change is logged by field name once.
- The flips: making it private puts it back to listed and making it public again lists it; the database refuses a private repository that is not listed.
- The three statements of the rule (the Python statement, the facets' SQL and `discover_read`) agree on every state, and the restricted role cannot read an unlisted profile through `discover_read`.
- The profile tests and the audit of the owner tier for the new field, the contract has no breaking change.
- In the hub, unit: the card's switch for each state and each reason it is not offered, what is sent, the words, the storefront note for an Owner and for nobody else. Against the real API: an Owner turns the switch off in Studio and it is kept; the repository is gone from Discover's search, its tag choice and the facets; a second user opens its page by its address, sees no note, and a library copies it; its Owner sees the note on the page; turning it on again lists it; the switch is not offered for a private repository or to an Author, and the API refuses with the words; and at 375 pixels the switch is 44 pixels high and nothing scrolls sideways.

## Questions for the maintainer

- Should **a repository that stops being public** go back to listed (it does), or keep the Owner's choice for when it is made public again?
- Should the **Make public dialog** offer "Listed on Discover", so that a repository can be unlisted from its first release? It is the one case where an address cannot yet have been shared and the repository is on the list for the minutes between the flip and the switch.
- Is **refusing** `listed: false` for a repository that is not public (`409`) the right answer, or should it be ignored?
- Should a repository its Owner left unlisted be **mentioned to the libraries that hold it**, which today are told nothing?

## Consequences

- A repository can be public and shared by its address without being offered to everyone: one column and one condition on the listing, its facets and its policy, a route's read through the gate it already had, and a switch.
- An unlisted repository is as public as any other: anyone with the address can read it and copy it, and the screen says so. The switch hides a repository from a list; it is not secrecy and is not presented as such.
- One migration: a column, a check and the redefinition of one policy; no new table, so `copyable_tables.py` needs no line. The contract is additive: `listed` on the profile reads and on the flip check, an optional field of the profile update, one error type, and the descriptions of two routes.
- The public stack rule, the skew gate and every other gate are unchanged: whether a repository is on the list is no part of whether it may be built on or copied.
- H3 has one new thing to do for it: its flip from public to protected puts the flag back, which the check enforces.

Closes #1064
