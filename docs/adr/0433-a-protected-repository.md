# 0433 - A protected repository

Status: accepted. Slice H3 of [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), tracked in #1065. Builds on [ADR 0431](0431-including-a-repository-in-the-release-of-one-built-on-it.md) (the choice, the terms and the consent to include), [ADR 0432](0432-a-public-repository-that-is-not-listed.md) (the `listed` check that this slice's flips keep true), [ADR 0286](0286-the-read-switch-for-public-repositories.md) and [ADR 0287](0287-who-may-read-a-public-repository.md) (a public repository is read through its release, and who may read it), [ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) and [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (the flips and the skew gate), [ADR 0303](0303-operator-delist.md) and [ADR 0384](0384-deprecating-a-repository.md) (delisting and retiring), [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) (a manifest and its steps) and [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md) (what the Owner sees of who copied it). The choices marked *default* are the answers the maintainer gave to the RFC's open questions or the smallest ones; each is listed as a question at the end.

## Context

[ADR 0431](0431-including-a-repository-in-the-release-of-one-built-on-it.md) lets a repository B be public over a source A that stays private, by carrying A's rows as its own. Some sources cannot be included: A's Owner wants the rows to stay A's, updated and shared across the repositories built on it, and still not on Discover or copyable by anyone. [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md) calls that source **protected**: a library reads it only as a step of the copy of a public repository built on it. This is the slice with the new opening in the wall of [ADR 0002](0002-multi-tenancy-shared-schema-rls.md), so most of this record is the predicate and what is tested against it.

## Decision

### The value, and what it is

`repository_profile.visibility` is `private`, `protected` or `public`. A protected repository has a profile (no summary, no cover, no terms line, none shown to anyone but its members) and a release, made with the flip, because a library reads it through its release document like a public one: `repository_upstream.reads_through_release` is the question every reader that used to ask "is it public" for *how* a repository is read now asks (the document, the digest, the cooldown, the skew gate, the consent of ADR 0431 and the browse of an invited library), and `is_public` stays for what is true of public repositories only (Discover, the storefront, the visitors). It is on no listing, the storefront and every `/repositories/{id}` route answer for it as for a private repository, and its profile and cover are not a visitor's. Discover's three statements of the rule ([ADR 0432](0432-a-public-repository-that-is-not-listed.md)) already say `visibility = 'public'`, so none changed.

### The predicate, and the one function

A protected repository `a` is read by a request when the request **goes through** a repository `v`, named in the transaction-local `app.repository_via` that `reading_repository(..., via=v)` sets and nothing else does, and all of this holds:

- `v` is a published repository, not delisted, whose current release was made public (`tenant.released_public`) and lists `a` among what it is built on and did not include (`a = ANY(tenant.released_over)`);
- the request is in a tenant (a request in none, `NO_TENANT`, has no row, so a visitor's route is closed whatever else is true);
- `v` is not retired, unless the tenant holds a grant to it already; and `a` is a published, undelisted repository, not retired unless the tenant holds a grant to it already.

That is `repository_reached_through_another(a)`, one SQL function, and the three places that say who may read a repository call it: the gate `repository_read_tenant_id()` (so every content table's `repository_read` policy), the profile's own `repository_read` policy (the profile is the one table that cannot call the gate, [ADR 0287](0287-who-may-read-a-public-repository.md)) and the insert policy of `repository_subscription` (the library writing its own row, below). Everything else in the three is as it was.

**The recursion hazard, and what it cost.** The function can read only what no policy hides from the tenant and does not recurse into the gate: `tenant` (no policy), and the tenant's own rows of `repository_subscription`. Two things that would be natural cannot be read there. The profile of `v` is not readable by a request that asked for `a`, and a policy on the profile that reads the profile is the infinite recursion ADR 0287 found; and the tenant's copy records are read through the gate itself (`repository_read` on `repository_copy`), so a function the gate calls that reads them recurses at run time. So the two facts about `v` the rule needs are kept **on `tenant`**, beside `published_at`, `delisted_at` and `deprecated_at`, which [ADR 0303](0303-operator-delist.md) put there for the same reason: `released_over` (the repositories the current release of a public or protected repository was built on and did not include; empty while private) and `released_public`. The application writes both in one place (`repository_reach.sync_reach`), whenever the profile's `release_sources` or `visibility` change (a release is published, an earlier one is made current, any flip), and a test holds them to the profile. "The tenant holds `v`" and "holds `a`" are the tenant's grant rows, not its copy records: a library that copied a public repository holds a grant to it, always.

A grant of `source = 'protected'` is **not a grant** to the gate or to the profile's policy: the row is how the library lists what it holds through another repository and never lets it read anything alone. An invitation (`invited`) reads a protected repository as it reads a private one, and the Owner of a protected repository invites a library or a repository as of any repository.

**What is tested against it.** A Python statement of the rule is written in the test (`reached`), and the function, the gate and the profile's policy are held to it, as the restricted role, on every combination of the nine facts it reads (288 of them, the request in a library and in none included). The insert policy and the one update policy below are tested as the restricted role case by case, and so is each reader.

### The grant a library writes, and the one update

The insert policy of `repository_subscription` gains a third case beside the invitation and the public grant: the library writing its own row, `source = 'protected'`, to a published, undelisted repository whose profile says `protected`, inside the read that function allows. A library cannot write an invitation, a public row to a repository that is not public, a protected row for another library, or one through a repository that does not list the repository.

A narrow **update** policy lets a repository's side turn its rows `public` into `protected` and the other way (`USING` and `WITH CHECK` both say `source IN ('public', 'protected')`), the only update the table has had. It is what keeps a library's row true when the repository changes between public and protected, without a cut-off that the library does not need.

### How a library reads it, and how a repository builds on it

`reading_repository(session, id, via=None)` is the read; `reading_repository_held(session, id)` is the form for a reader that holds the repository already: it asks the database as it always has, and only when that says no it goes through each public repository the tenant holds whose current release lists it, until the database lets it in. The update engine, the skew gate, the stack rule, A's terms and the list of what a library holds read through it. The copy engine knows the repository it is copying, so the manifest reads every step but the head through the head: a protected step is `readable` through it and through an invitation, and `Step` says `protected`.

- **A library never copies it alone.** `copy-plan` and `copy` of a protected repository as the head are `409 repository-protected` for a library, whether it holds a row for it (it is told it is protected) or an invitation (it reads it as ever, and may not copy it). A library that holds nothing of it gets the `404` of a repository that is not there. The one head a protected repository has is a **repository** that its Owner invited: building on it takes the grant its Owner gives ([RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), hard invariants), so a repository copies it, a library does not.
- **Nothing else reads it.** Browsing it, its profile and its releases are `404` for a library that holds it only through another, as for every visitor; only the copy engine, the update check and the lists read it, through the repository that lists it.
- **The copy of a public repository inserts the grant for each step it brings**, as it does for a public step: `source = public` for a public one, `source = protected` for a protected one (`subscribe_to_public`). The row is only written when the library holds none.
- **It is not named.** A library that holds a protected repository through another, and has no invitation to it, reads "A protected repository" for its name in the copy plan, the dependencies, the list of what it holds and its copy record, and nothing for its address and description (RFC default 2). Keeping the name out of the copy record means a later update does not write it back. The Owner of a repository built on it, who was invited, reads its name in Studio.

**The update path.** A release of A is announced to the libraries that hold a grant to it, the `protected` rows included, as ever. A library reads A's update through any public repository it holds that lists it. The skew gate of a public repository built on A is unchanged ([ADR 0431](0431-including-a-repository-in-the-release-of-one-built-on-it.md)): it must have taken A's current release, and a protected A it cannot read counts as behind.

**What ends it.** The rule is checked each time, so a library's access ends with its last qualifying repository: when it is made private or protected, when its release no longer lists A (it includes it now, which is a breaking release), or when the operators delist it. A retired repository keeps what its holders read, as for any retired repository. Making a repository private or protected also deletes the `protected` rows its libraries wrote for the repositories it listed, unless another public repository they hold still lists them (`revoke_protected_through`): that is what a library lists, the reading having stopped already. Delisting is reversible by an operator, so it deletes nothing: the reading closes and opens again with it.

### The flips

| From | To | What happens |
| --- | --- | --- |
| private | protected | `PUT /tenants/{id}/protected`: atomic with the first release (the same steps, gates and notice as a public release), no summary or terms line. `409 built-on-not-public` (the stack rule below), `409 built-on-behind`, `409 repository-delisted`, `409 repository-deprecated`. |
| protected | public | `PUT /tenants/{id}/public`, as private to public: the summary, the preview and the terms line, and a release of its own; the libraries' `protected` rows turn into `public` ones. |
| public | protected | `PUT /tenants/{id}/protected`, no new release: it leaves Discover and the visitors' reads; `listed` goes back to true (the check of ADR 0432); the libraries' `public` rows turn into `protected` ones; `409 public-copies-would-be-cut-off` with their number until `acknowledge_revokes`, because the libraries that held it for itself alone lose its updates, and those libraries are told once; the libraries that held a protected repository through it lose that path. |
| protected | private | `DELETE /tenants/{id}/public`, as for a public one: `409 public-repositories-built-on-it` while a public or protected repository is built on it without including it; the libraries' `protected` rows are deleted. |
| public | private | As before; also the protected repositories it listed are no longer reached through it. |

`PUT .../protected` is refused with `public-repositories-not-available` while the deployment does not accept public repositories, as `PUT .../public` is. A repository that is public or protected is not unpublished, only made private. `PATCH .../profile` still refuses a change of `visibility`.

### The stack rule, and the gates

`built_on_not_public` (the error type and the field keep their names so the contract does) answers "not reached": a repository B is built on that is private, not included, or cannot be read just now. Protected is reached. The same function asks it for B being made public and for B being made protected, so a protected repository's own sources follow the rule. A source a repository holds only through another (it copied a public repository that brought it) is read through that repository, so the rule holds for a repository that never had an invitation.

`public_dependents` (making A private) counts every published, undelisted, not retired repository, public or protected, whose current release is built on A and did not include it (`tenant.released_over`), which is what ADR 0431 asked of a public dependent, and now holds for a protected one too. Because it reads that fact and no longer the dependent's profile, it reads nothing a protected dependent hides.

The skew gate, `built_on_not_public` and A's terms read a source through `reading_repository_held`. When A becomes protected, a repository that copied it while it was public and holds nothing else that lists it can no longer read it: it is in the count of libraries the flip names, it cannot release until A's Owner invites it, and a library that copied that repository is not affected.

### A's terms

`repository_profile.may_be_shown` is the second of A's terms, next to `may_be_included` ([ADR 0431](0431-including-a-repository-in-the-release-of-one-built-on-it.md)): a nullable boolean, null the default for the visibility, an Owner's value winning. **Only a protected repository can say no**: a private one is read by the people its Owner invites and a public one by anybody, so what an Owner said while it was protected waits for the next time it is, and reads as `true` meanwhile (`PATCH .../profile` with `terms.may_be_shown: false` is `409 repository-not-protected` for any other repository, in the same request as everything else in it). The defaults by visibility are RFC default 8: private, included off and shown on; protected, included on and shown on; public, included on and shown on whatever it says. `GET .../profile` says `terms.may_be_shown` and whether that is the default (`may_be_shown_is_default`) to its members.

`inclusion = show` follows `include` in ADR 0431: asked when the choice is set (`PUT .../inclusion` is `409 repository-not-showable`, naming the repository, unless the user is an Owner of it or its terms allow it) and again when a release is made, for the user making it (`409 repository-not-showable` naming each, writing nothing). A repository that copied A before A said "stay hidden" has `show` until it chooses, and is held to it at its next public or protected release: the choice it has is include, which A's terms allow. The API offers the choice as `showable` (`allowed`, `by`) beside `includable` on the list of what a repository copied, on the answer of the choice and in the flip check, with `protected` and `may_be_shown`. With H3 alone only `include` is offered to such an A; H4 adds `hide`.

The screen's two presets set both switches: **Open** (included on, shown on) and **Stay hidden** (included on, shown off), with **May be hidden** to join them under the same card when H4 adds `hide`: the card is a list of switches under a list of presets, and a switch is one row in each.

### The contract

Additive, with one declaration: `RepositoryProfileOut.visibility` and `FlipCheckOut.visibility` are declared with `x-extensible-enum` (`private`, `protected`, `public`) and not `enum`, since adding a value to a response enum is a break of the contract by the diff's own rules and the set is meant to grow; the request keeps its `Literal`. New: `PUT /tenants/{id}/protected` (request and answer), the errors `repository-protected`, `repository-not-showable`, `repository-not-protected` and `repository-already-protected`, `terms.may_be_shown` on the request and the member's read, `showable` and `protected` and `may_be_shown` on the reads named above, `protected` on the dependency and the copy step, and the profile's flip check naming the visibility. A visitor's list of what a public repository is built on leaves a repository that is not public out, since that list is a public view and a protected repository is named in none.

### In the hub

All in the existing files; the screens never say tenant, grant, subscription, flatten or source.

- **Studio, the visibility card.** A third state, **Protected**: "Not on Discover, and not copied on its own. A library gets it with a public repository built on it, and keeps reading it only as long as it holds one. The libraries you invite read it as they read any repository." with "Make public…" and "Make private…". A private repository has "Make public…" and "Make protected…", a public one "Make private…" and "Make protected…" (not while it is off Discover or retired, which refuse it).
- **The dialog.** One dialog for the three flips. "Make *name* protected" lists what stands in the way (the same list as for public, "Before you can make it protected"), what it does, the built-on choices, a release (for a private repository only), the acknowledgement of the libraries that lose its updates alone (for a public one) and no summary, preview or terms line; "Make protected and publish release", or "Make protected" for a public repository.
- **The built-on choices.** Each repository a repository is built on says Public, Protected or Private; "Keep separate and visible" is not offered where A's terms forbid it, with the words ("You cannot keep *name* separate and visible here: its Owner has asked that what is built on it does not show it. Include it in this repository instead, or ask its Owner."), and what keeping a protected one separate means ("stays a protected repository of its own").
- **A's terms card** (Studio, Profile): the presets **Open** and **Stay hidden**, and the switches under them, **May be included** and **May be shown**; "May be shown" and the preset "Stay hidden" wait for the repository to be protected and say so.
- **Shelf.** A repository a library holds through another reads "A protected repository" with a **Protected** pill, the note "Your library holds this repository through a public repository built on it. It cannot be copied on its own, and its updates come for as long as your library holds a repository built on it.", and neither "Copy" nor "Copy again" is offered; "Check for updates" is. In a copy plan a protected step reads "Protected, comes with this repository" and is not a repository the library cannot take in.
- **A phone.** One column, every control a row of 44 pixels, nothing scrolls sideways.
- [Identity §14.3](../brand/identity.md#143-terminology) gains the rows the screens use.

## The RFC's open questions, as settled for this slice

- Question 1. **Three switches, two presets** (Open and Stay hidden), no "Sealed". H3 builds `may_be_shown` and both presets; `may_be_hidden` is H4's.
- Question 2. **A protected source is not named in any public view or to a library that holds it only through another repository**; an included one still is, with its licence. Its Owner's members and the Owners of the repositories it invited read its name.
- Question 3. **No re-targeting** of a flattened row. (H1.)
- Questions 4 and 7. **Hidden rows** are H4's.
- Question 5. **H4's spike decides** whether hiding rides on RFC 0044's audiences.
- Question 6. **Changing the choice before the first public release is free.** (H1.)
- Question 8. **A default is stored as nothing.** A public repository's `may_be_shown` is always true, and a private one's too: only a protected repository can say no.

## Not built

- Hiding (`inclusion = hide`, `may_be_hidden`): H4.
- Pruning the `protected` rows of a library when a repository's new release stops listing a source, and writing a row again for one that went: the reading ends and begins by itself, since the database asks each time, and the row is only what the library lists. A library that lost the row of a repository it still reads through another lists it as no longer offered, until it copies a repository that brings it again.
- A switch for naming a protected repository to the libraries that hold it through another: it is never named to them (above).
- A notice to the Owner of A when a repository starts or stops listing it: the dependents list shows the repositories built on it ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md)), and the libraries that hold it through them are counted with the ones that copied a public repository, never named ([ADR 0299](0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md)).
- A command-line command: `lorenzo api PUT /tenants/<id>/protected --data '{}'` does it.

## What the tests pin

- The function, the gate and the profile's policy against the Python statement on every combination of the facts, as the restricted role; a `protected` row reads nothing alone and an invitation reads as for a private repository; the repository named in `via` is the only one asked; nothing is ambient; delisting, retiring and an unpublished repository close it; the visibility changing makes it read as such; the helper that goes through each repository a reader holds; the insert policy (the one way a library writes a protected row, and the ones it cannot), the update policy (public and protected only, the repository's own side only), the checks, and the columns on `tenant`, which follow the profile after every flip and release (the function reads them, so they cannot differ).
- Every reader against every state, through the HTTP API: a visitor (the profile, the cover, the releases, the browse, the stat groups, the dependencies, the preview and the storefront, and Discover), an operator, a library that holds nothing, a library through a public repository, a library invited, the Owner's own, the repository that was invited and builds on it; each against protected, public, private, retired, delisted and not published.
- The flips: private to protected is atomic with the release, refused for a source that is not reached and for a repository retired or delisted, and needs no summary; protected to public needs them and makes a release; public to protected needs the acknowledgement, turns the rows, resets `listed` and tells the libraries once; protected to private is refused while a repository that shows it is built on it and allowed once each includes it; the libraries' rows go with the last repository that listed it.
- A repository is public over a protected source and a library copies both in one action, not named; the diamond (two repositories built on the same protected one: one set of its rows, and it stays readable while one of them lists it); a release of A reaches the libraries that hold it, the skew gate holds the repositories built on it, and a library takes the update through them; a release that no longer lists it ends the way to it.
- A's terms: only a protected repository can say no; the default; refused for the others; `show` refused by the terms and by a release, an Owner of A exempt; include as the way out; the answers carry `showable`.
- In the hub, unit: the card in each state, the second button, what is disabled and why, the lines, acknowledgement and body of the dialog, the choices offered and the words for each reason, the presets and what they send, and Shelf's words. Against the real API: an Owner makes a repository protected in Studio, a repository built on it is made public over it, a visitor finds neither it nor its name, a library copies the repository and Shelf shows the protected repository with its pill and no way to copy it alone; stay hidden leaves a repository built on it with include and says why; a protected repository with a public one built on it is refused in words and with a link; and at 375 pixels nothing scrolls sideways and every control is 44 pixels high.

## Questions for the maintainer

- Is a **repository an Owner invited** the right (and only) head a protected repository has, rather than none at all? It is what keeps "building on A takes the grant A's Owner gives", and it means an invited *library* reads it as a private repository and still cannot copy it.
- Should a **protected repository need the terms line** the way a public one does (it publishes content to libraries that copy a repository built on it, and the line says publishing cannot be recalled)? It does not, as the RFC says only the flip to public does.
- Should **public to protected** keep the libraries' access that does not depend on another repository (it cuts it off, with the acknowledgement and a notice), or refuse while any library copied it by itself?
- A repository built on A is **left unable to release** when A becomes protected and it holds nothing else that lists A, until A's Owner invites it. Is that the right place to put it, or should the flip refuse?
- The **response `visibility` is an extensible enum**, so the contract has no break. Is that preferred to accepting the break, which versions the API's major?

## Consequences

- A repository's Owner can publish a rules text, a licensed base or a half-finished setting that many public repositories build on, that no library reads or copies on its own, and that updates for the libraries that hold it through them.
- A second opening in the wall of ADR 0002, narrower than public's: one function, read only inside `reading_repository` with the repository the reader goes through, never ambient and never by the visitors' routes, written in the three places the database says who may read and tested against a statement of the same rule.
- One migration: two columns on `tenant` and a check, a column on the profile, two checks widened, the function and its three callers, and one narrow update policy. No new tenant table, so `copyable_tables.py` needs no line.
- A repository built on a protected one learns of it by invitation as before; a library that holds it through another never learns its name, and what it holds ends with its last way in.
- The hub's three flips are one dialog, and the choices of a repository built on a source say what that source's Owner allows.

Closes #1065
