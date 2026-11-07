# 0431 - Including a repository in the release of one built on it

Status: accepted. Slice H1 of [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), tracked in #1063. Builds on [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) (a bridge carries only what it authored, and every copy link names an origin), [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) (the digest, the released rows and the detector), [ADR 0214](0214-the-release-document.md) (the document and its versions), [ADR 0286](0286-the-read-switch-for-public-repositories.md) (a public repository is read through its current release), [ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) (the rules of the flips and the skew gate), [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing facts and the storefront), [ADR 0299](0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md) (the terms line) and [ADR 0385](0385-studios-profile-editor-and-the-cover-controls.md) (Studio's profile and visibility cards). The choices marked *default* are the answers the maintainer gave to the RFC's open questions or the smallest ones; each is listed as a question at the end.

## Context

[ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) refuses to make a repository public while a repository it is built on is not, because a library that copies it could not be granted the other by an Owner who never saw it. [RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md) asks for ways to publish a repository over a source that stays private. This slice is the first and cheapest: B's Owner may **include** A, so that B's release carries A's rows as B's own and a library that copies B never reads A.

## Decision

### The choice, and where it lives

`repository_copy.inclusion` is B's record of how it carries a repository it copied: `show` (the default, and what has always happened) or `include`. The check allows only these two; later slices widen it. It is on the copy record because the copy record is already B's account of A, B's Owner is the only one who writes it, and A's Owner already reads it ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md)): `GET /tenants/{A}/subscribers` now carries `inclusion` for each library or repository that copied A, so A's Owner sees each dependent and the choice it made. A library's is always `show`, and copying A again starts over at `show`, with the rest of the copy.

`PUT /tenants/{B}/repositories/{A}/inclusion` with `{"inclusion": "show" | "include"}` sets it, for the Owner of B only (an Organizer or an Author is `403`, a stranger `404`, a library `409 not-a-repository`, a repository B has not copied `409 repository-not-copied`). Saying what it already is changes nothing and is not logged; a change is logged in B's own log as `repository.inclusion_set`. The answer says whether the caller may include A and why (`includable`), how the current public release carried A (`inclusion_in_release`) and whether the next release is breaking for it (`breaking_next_release`).

It is read in three places: `GET /tenants/{B}/repositories` (the list Studio's Built on tab is drawn from) gains `inclusion`, `includable` and `inclusion_in_release` on each repository B copied, `GET /tenants/{B}/flip-check` gains `built_on` (every repository B is built on, with the same facts and whether it is public and owned), and `GET /tenants/{A}/subscribers` gains `inclusion`. A library's read of what a repository is built on (`GET .../repositories/{id}/dependencies`, [ADR 0198](0198-the-dependencies-endpoint.md)) is unchanged: for a flattened repository it simply has no step for A.

### A's terms

`repository_profile.may_be_included` is a nullable boolean: A's Owner's answer to "may a repository built on this one include it". Null is *the default for the repository's visibility*, read by the application and stored as nothing, so it follows the repository when it changes visibility: **private, no; public, yes** (RFC default 8). An Owner's own value wins. A public repository can be copied by anyone, so a public one that says nothing may be included; a private one that says nothing may be included by its own Owners only (below).

It is read and written through the profile. `PATCH /tenants/{id}/profile` takes `terms: {may_be_included: true | false | null}` (`null` is the default again, `{}` says nothing, anything else is `422`), for an Owner, as the rest of the profile is: an Organizer and an Author cannot change it, and every member reads it as `terms: {may_be_included, is_default}` on `GET /tenants/{id}/profile`. It is not on a visitor's or a library's profile.

The RFC's three switches and two presets are H3's and H4's: H1 builds the one switch, "May be included", under the heading "How repositories built on this one may use it", with no preset (RFC open question 1: no "Sealed" preset; the presets come with the second switch).

### Consent

`include` needs a yes from A's Owner: the user is an Owner of A, or A's terms allow it. **A grant to read A is not that yes** ([RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), hard invariants). `repository_inclusion.includable` is the one place that asks: an Owner of A (read from the user's own membership) is `by: owner`; otherwise B reads A's profile through the gated read it already has (an invitation, or A is public) and the terms decide, `by: terms`. A is never read for anything else.

It is asked **once, when the choice is set**: `include` is `409 repository-not-includable` naming A, and nothing is kept. A release of B does not ask again, and neither does making an earlier release current: what B's Owner was allowed to choose stays chosen (the maintainer's decision). A's Owner turning the terms off, or A turning private so that its terms are the default of a private repository again, therefore changes only the choices made afterwards: not a choice already made, and not the release of the repository that made it. An Owner of A is exempt when the choice is set, as ever.

### The release

When B is public, its release document is built from B's **flattened** content: `repository_inclusion.flatten` makes B's copies of each included repository B's own rows. `repository_digest.assess` does it right after loading B, so the digest, the released rows, the counts, the comparison and the detector are all made from what the document holds, and a library and the Owner see the same rows. A repository that is not public is read live and whole by libraries (ADR 0286), so nothing of it is flattened.

**Which rows are B's copies of A.** B's rows with a copy link whose origin is A's: every entry, stat group and stat definition B copied from A, which is what `repository_copy_link_*` records with `source_tenant_id = A`. A stat group or definition B *merged* A's into is B's own row and is carried; it is a row of A's origin for the link and B's for the content, so it is flattened with the rest. A row B deleted after copying (a link with no local row) is **not carried**: it is simply not B's. What B copied from other repositories stays a copy of theirs, A's rows that refer to them included: those references reach a library through the copy links of that repository, as before.

**What changes in the content.** The links of those rows go: `links.entity`, `links.stat_group` and `links.stat_definition` lose them, so `Content.own` is true of them; `links.merged`, `links.deleted`, `links.snapshots` and `links.origin_tenant` lose everything that named A's rows; `links.attachments` loses the attachments taken from A; and `links.copies` loses A, so A is not among the repositories the release is built on and `read_release_copies` consequently excludes it. A parent B put on a row it holds is still carried, as the edge itself, from the prototypes.

**Which edits of B on them travel.** All of them, since the rows are carried as they are in B now: B's values, formulas, kinds, names, link names, prototypes, texts, pictures and knowledge on A's rows, and B's own rows that refer to them. A flattened release is therefore a different set of rows from a separate one: what a library would get of A as a step, plus B's work on it, which [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) otherwise leaves out of what libraries get. A library takes the rows with B's ids as their origins.

**What does not change.** B's tenant and its live copy of A: its copy record, its copy links and its rows are untouched, B goes on authoring on top of A and taking A's updates, and only the published document is flat.

**The document records how it carried each source.** [`FORMAT`](0214-the-release-document.md) becomes 37: `Content.sources` maps each repository B is built on to `{inclusion, name, licence}`, the name and the licence being a snapshot of A as B's Owner can read it when the release is made (`licence` is `{label, url}` or none). Documents of an earlier version read with none (`READERS[36]` adds the empty record); the serialiser test that fails when `Content` gains a field the format does not write stays, and now covers it.

**Digest and released rows.** The rows are hashed by the same functions from the flat content, so a released row's id is B's, and `release-preview` compares the same way: `matches` is true after the release, an edit afterwards is a change to the row that came from A. `make_release_current` recomputes the rows from the document and the hash check holds, because the document is the content the digest was made from.

**What the profile keeps.** `repository_profile.release_sources` is how the *current public release* carried each repository: `[{id, name, inclusion, licence_label, licence_url}]`, null until the first public release. It is written with the listing facts ([ADR 0292](0292-discover-the-listing-and-the-storefront.md)) when a public release is published and when an earlier one is made current, so it is always the current release's. It is a snapshot in the profile for two readers that must not open a document: the storefront, and the rule below. Retention ([ADR 0214](0214-the-release-document.md)) is unchanged: a document pruned is gone, a release without one cannot be made current, and the profile never needs one.

**`plan_copy` and `compute_updates` on a flat document.** Neither changed. `upstream_copies` reads the document's `links.copies`, so the manifest of a library has no step for A; `Content.own` is true of A's rows, so the step copies them; the update engine finds them as rows of B it has links for or not (added, changed, removed) like any other. Tests: a library copies a flattened B and never reads A; B takes A's release and releases again and the library takes the rows as B's; the diamond (B and C both include A: a library that takes both holds two sets of A's rows, with different origins, and the collision list resolves the overlap by name, stat and link name); and B includes A while C, built on the public A, keeps it separate (a library that holds C holds A's rows from A, and B's flat copies of them collide with those).

### The gates

- **`built_on_not_public`** (the stack rule of making B public) skips a repository B includes: it is not a dependency, since the release carries it as B's own. Whether the user may include it is the release's question, above. A repository that is not public and not included still stops it, and the dialog now says whether it can be included instead.
- **`public_dependents`** (making A private) skips a dependent whose **current release** carries A included, by what the dependent's profile recorded, not by the choice its Owner has made since: what a library reads is the release, so a choice not yet released does not let A go private, and a release that carried it lets it. A public repository built on A that shows it still stops it.
- **The skew gate** (`built_on_behind`) is unchanged and reads every repository B is built on, included ones too: B cannot flatten a stale copy, so an included A must be current when B releases, and a release of A has to be taken by B before B can release. A it cannot read counts as behind: when A goes private, the grant B gave itself by copying the public A is revoked as ever, so B cannot release again until A's Owner invites it. The libraries that took the flat B are not affected.

No policy and no gate function changes: the three places that say who may read a repository ([ADR 0287](0287-who-may-read-a-public-repository.md)) are about who reads, and nothing here opens a new way in. A reads nothing of A but what the gated read already gave it. `repository_copy` has its tenant isolation and the Owner's read of who copied it, which now shows the choice; the two profile columns are in a row the existing policies govern. The migration is therefore columns and a check and no policy: `copyable_tables.py` needs no line (no new table; the test that every tenant table is registered holds).

### Changing the choice

Before B's first public release it is free, as often as the Owner likes (RFC default 6). After it, the next release must be breaking and says so. The detector's mechanism is the acknowledgement (`acknowledge_breaking`, the box of the composer), but its reasons are a fixed list of the API's contract, and a new reason would change a response enum, which the contract's diff calls breaking. So the rule is a second list beside the first, additive: `Assessment.inclusion_changes` is each repository whose choice now differs from the one `profile.release_sources` records, a repository that is new since that release (it has no record, and its rows are added) not counting. The release preview carries them as `inclusion_changes`; a publish with any, or with detector hits, is `409 release-has-breaking-changes` with `inclusion_changes` beside `breaking_rows` until `acknowledge_breaking` says it; the release is then marked breaking whether or not the detector found a row. Moving between two releases (`PUT .../releases/{id}/current`) is held to the same rule by comparing the document's `sources` with the profile's. Show to include only adds rows, which the detector does not call breaking, so the choice is what makes it so; include to show removes them, which the detector also finds.

A repository whose last public release predates this one has no record, so the first release after changing a choice is not found breaking by this rule. No public repository exists in production yet ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) is built behind a deployment variable), so the gap is empty today.

### Attribution

B's storefront says what it includes and under which licence, from the snapshot in the release, so a visitor never has to read A, which may be private: `RepositoryProfileOut.includes` is `[{name, licence}]`, on the storefront's profile, a visitor's and a library's read of it, and Studio's, and holds only the repositories the current release carries included; a repository B shows is not in it, since it is a repository of its own (RFC default 2). No id is in it. A's Owner still sees B among A's dependents, since the dependents list reads B's copy record, which an included copy leaves in place.

## In the hub

All in the existing files; the screens never say tenant, grant, subscription, flatten or source.

- **Studio, Built on.** Under each repository a repository copied, a group "How is it carried in this repository?" with two choices, "Keep separate and visible" and "Include in this repository", a sentence under it for the one chosen ("The entries of *Armoury* become this repository's own when you publish a release. A library that copies this repository does not need *Armoury* and never reads it. Your copy of *Armoury* here is not changed, and you keep taking its updates."), and, once a release carried it, "Changing how this is included makes a breaking release." Where the user may not include it the choice is not offered and the reason is said: "You cannot include *Armoury* here: its Owner has not allowed repositories built on it to include it, and you are not one of its Owners. Ask its Owner to turn on “May be included”, or keep it separate." Only an Owner chooses; the others read.
- **The Make public dialog.** The same list under "How this repository carries what it is built on", one row for each repository, with whether it is public, so that a repository that is not public is answered by including it ("Or include it in this repository, below.") where that is allowed. Choosing saves it and the dialog reads what stands in the way again. A release that is breaking for how it carries something shows it in the box of breaking changes ("“*Armoury*” was kept separate in the last public release and is included now…") and has to be acknowledged like a row.
- **Studio, Profile.** A card "How repositories built on this one may use it" with the switch "May be included" and a sentence on who chose, which an Owner changes (saved at once, not with the profile's Save) and the other members read; and, among the facts of "What people will see", "Includes content from *Armoury*, *CC BY 4.0*".
- **The storefront.** A section "Includes" with "Includes content from *Armoury*, *CC BY 4.0*", the licence a link where it has an https address and "no licence stated" where it has none.
- **Libraries using it.** A repository that includes this one says "includes it in its own release".
- **A phone.** One column, every choice a row of 44 pixels, nothing scrolls sideways.
- [Identity §14.3](../brand/identity.md#143-terminology) gains the four rows the screens use.

## The RFC's open questions, as settled for this slice

1. **Terms are three switches with two presets** ([RFC 0051](../rfcs/0051-building-on-a-repository-you-do-not-publish.md), Open and Stay hidden); no "Sealed". H1 builds the include switch only.
2. **An included source is always named** on B's storefront, with its licence, from the snapshot. A protected source is not named in any public view (H3).
3. **No re-targeting** of a flattened row to a library's existing copy of A: the collision list resolves the overlap.
4. **Hidden rows** nothing visible uses are removed with the update that drops them (H4).
5. **H4's spike decides** whether hiding rides on RFC 0044's audiences.
6. **Changing the choice before the first public release is free**, after it the next release is breaking.
7. **Hidden rows do not count** toward a library's entry limit (H4).
8. **A default is stored as nothing**: null means the default for the repository's visibility; an Owner's value wins. (A public repository's "may be shown" being always true is H3's.)

## Not built

- The "may be shown" and "may be hidden" switches, the presets and `hide` (H3, H4), and a protected repository (H3): the terms card has the one switch.
- Re-targeting a flattened row to a library's existing copy of A (RFC, not in scope).
- A command-line command: `lorenzo api PUT /tenants/<id>/repositories/<a>/inclusion --data '{"inclusion": "include"}'` does it.
- A notice to A's Owner when a repository includes it: the dependents list shows it.
- A baseline for a repository whose last public release predates this one (above).

## What the tests pin

- The document: A is not among what B is built on, none of its rows is a copy, they are B's own with B's ids and B's edits (a changed stat, a formula that reads it, a deleted row left out), `sources` has the name and licence, B's tenant and its copy links are unchanged, the released rows are the flat ones, the digest matches the release and an edit afterwards is a change to a row that came from A. A private repository's release holds no document, flattens nothing and records no sources.
- The pure parts: which rows `flatten` makes own and what is left of each link, with two sources, one of them merged and deleted from; flattening nothing; a flat content round-trips through the document; version 36 reads with none, sources round-trip, an unknown field of a source is refused; what a release records of its sources; what is a change of choice and what is not; the default of the terms.
- What a library reads: it copies a flattened B, its plan has no step for A, its entries are B's with B's edit and B's deletion, its copy records are B's only, and it and a visitor read nothing of A (`404`); B takes a release of A, releases again and the library updates through B; the diamond; B includes the public A while C shows it.
- The choice: kept on the copy record and listed, in the three reads; only an Owner chooses, only for what it copied, `422` for any other word, `409` for a library; the database allows only two words.
- Consent: another Owner's repository is refused without the terms (naming it, in the list, in the flip check), allowed with them, not asked again at the next release or when an earlier release is made current when the terms are taken back (only a choice made afterwards is refused), and the terms follow the visibility until an Owner says otherwise, in both directions, with `null` as the default again, an empty `terms` as nothing, and nobody but an Owner changing them.
- The gates: an included repository does not stop B being public; one that is not included does; A is made private while B's release carries it included, and not while only C shows it, and not for a choice not yet released; a library that took the flat B keeps reading it when A goes private and a latecomer still copies it; the skew gate refuses a stale included A.
- Changing it: free before the first public release; after it, `breaking_next_release`, the preview's `inclusion_changes`, the `409` with both lists, acknowledged to publish, marked breaking even where the detector found no row; moving to an earlier release is held to it too.
- Attribution: the storefront, a visitor's and a library's profile and Studio's say what is included with its licence from the snapshot, without an id, and what B shows is not named; changing A's licence changes nothing until B releases again.
- The audit of the owner tier (an Organizer and an Author are refused the route), the profile tests with the two fields, the contract has no breaking change.
- In the hub, unit: the words, what is offered and why not, the note, the terms, the lines of a storefront, of the dialog and of a release that is breaking for a choice, the blockers and the acknowledgement. Against the real API: an Owner includes a private repository in the dialog, makes the repository public, a second user finds it on Discover with "Includes content from …", copies it and holds the rows with no access to the other; a refused include shows its words and goes back; the terms card is changed by an Owner and read by an Author; and at 375 pixels each choice is 44 pixels high and nothing scrolls sideways.

## Questions for the maintainer

- Is **a public repository that has said nothing may be included, and a private one may not** the right default (RFC default 8)? It means A's Owner of a public repository has to turn the switch off to stop it.
- Should **copying A again** keep the choice (it resets to `show`, with the rest of the copy record)?
- The **breaking rule is a second list** beside the detector's, to keep the contract additive. Is that the right trade against adding a reason to the detector (an accepted break of the contract, with this ADR as its record)?
- Should **A's Owner be told** when a repository includes it, beyond the dependents list?

## Consequences

- A repository can be public over a source that is not, when the source's Owner agrees (or is the same person), and a library that copies it never reads the source.
- A flattened source gives up live updates from A and shared identity across repositories: B's Owner takes A's updates and releases again, and two repositories that include A give a library two sets of its rows.
- The document, the digest and the released rows all describe the flat content, so a public release is exactly what a library reads, and a private repository is unchanged.
- One migration: a column and a check on `repository_copy`, two columns on `repository_profile`, no policy. One new document format, and an additive contract: new fields on the reads named above (the list of repositories, the flip check, the Owner's list of who copied, the profile, the release preview), a route, an optional field of the profile update, and one error type. A user of B learns of A only whether they may include it.
- Changing the choice after a public release is a breaking release, acknowledged like any other, and the composer and the dialog say why.
