# RFC: Public repositories and discovery — letting a repository be found and copied by any logged-in user, and the gates that come before that

Status: accepted, decided with the maintainer on 2026-10-07: public discovery is part of v1.0; it is opt-in for each repository and a repository is private until its Owner says otherwise; only logged-in users can see it; copying a public repository subscribes the library to it, as `lorenzo repo offer` does today; the licence is optional; the preview's default is `showcase`; GM-only text stays in a public repository's copy; the edge rate-limit rule is the maintainer's task before launch and the build does not need it; a takedown process is a future matter. The shape of the profile, the preview matrix, the exact gates and their limits, the flip rules and the deprecate state are proposed, and what is still open is in [Open questions](#open-questions). Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. It requires [RFC 0037](0037-releases-and-public-snapshots.md), because a public repository is read from its releases, not from its live rows, and it is part of the programme in [RFC 0036](0036-repository-tooling.md). Row "Publish, subscribe, update screens" of [v1.0](../../v1.0.md).

## Context

Today a library gets a repository by being **granted** it: the repository's Owner puts the library's tenant id into `PUT /tenants/{tenant_id}/subscribers/{subscriber_tenant_id}`, and the id reaches the Owner out of band ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). [RFC 0024](0024-repositories.md) §8 scoped v1 to unlisted-and-granted and left discovery out, because it "implies moderation, abuse-reporting, and trust signals nobody has designed". The v1.0 plan puts it back in, so this RFC designs those things before anything can be public.

What the code does today, which this builds on or has to change (read in `apps/api`):

- **There is no way to find a repository.** The API has no listing of repositories you are not already granted, and an Owner cannot look a tenant up by name. `GET /tenants/{tenant_id}/repositories` lists what one library holds.
- **A repository has almost no description of itself.** `tenant` carries a name, a slug, a description and a picture. There is no summary, licence, credit, tag, system, language or cover.
- **The picture is open to anyone.** `GET /tenants/{tenant_id}/picture` has no authentication at all, deliberately, so that a plain `<img>` can load it ([ADR 0056](../adr/0056-profile-pictures.md)). For a play tenant that is a profile picture; for a private repository it is a hole once repositories are meant to be private.
- **A subscriber can look at names, not text.** The browse routes return an entry's name, kinds and parents, and no description or note: "structure, not text" ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). What a library then sees of the text it copies follows the ordinary rules: Everyone text is readable, and GM-only text is visible to the library's Owner and Organizer ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)) and, once [RFC 0036](0036-repository-tooling.md) A4 is built, to a campaign's GMs.
- **Only the repository's side creates a grant.** The insert policy on `repository_subscription` is `repository_tenant_id = app.tenant_id` ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)), so a library cannot subscribe itself to anything.
- **The read gate needs a grant.** `repository_read_tenant_id()` returns a repository's id only when the current tenant holds a grant and the repository is published. A logged-in user with no library, or a library with no grant, reads nothing.
- **Grants are not transitive.** A bridge's Owner cannot grant somebody else's repository ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), so copying a repository that is built on others needs a grant from every Owner in the stack.
- **Publishing notifies in the request.** `PUT /published` writes a notification for every member of every subscribing tenant inside the request that publishes (`_notify_members_of` in `routers/repositories.py`). There is no job queue: [ADR 0008](../adr/0008-deferred-taskiq-and-fastapi-limiter.md) deferred one.
- **There is an operator role and an `/admin` router.** `platform-operator` gates `/admin/*`, with account suspension ([ADR 0057](../adr/0057-platform-operations.md)). Nothing in it knows about repositories.
- **Pictures are bytes in Postgres** ([ADR 0017](../adr/0017-information-and-payloads.md)). The only upload cap I found in the code is `profile_picture_max_bytes`; I found none on a picture attached to an entry's note, and no cap on how many entries a repository holds.
- **Deleting a repository is refused while anyone holds a grant** (`409 repository-still-granted`, [ADR 0184](../adr/0184-deleting-a-tenant.md)).

What the maintainer wants: a Discover page where a logged-in user can browse public repositories, look inside before copying, and copy one into a library in a click, with the library then getting its updates exactly like one that was invited. The vocabulary is ADR 0194's, which is on another branch: Library, Repository, Owner, Organizer, Author, Copy and Update, Invite a library, Release, Built on, Everyone and GM only. In this document a repository is a tenant with `kind = repository`, a library is a play tenant, and a grant is a row in `repository_subscription`; those technical terms are used below where a table or a route is meant.

## Decision

### 1. Visibility: private or public

- **A repository has a `visibility`, `private` or `public`.** It is `private` unless its Owner changes it; nothing about an existing repository changes when this is built. A play tenant has no visibility. Setting it is an Owner's action, the same standing as publishing.
- **A grant says how it came about.** `repository_subscription` gains `source`, `invited` or `public`. An Owner's `PUT .../subscribers/...` writes `invited`; a library copying a public repository by itself ([§3](#3-public-read-for-any-logged-in-user-and-copying-subscribes)) writes `public`. A library that holds both keeps `invited`: an invitation outranks a public copy, so a repository going private later does not cut off a library it invited.
- **Repository creation stays behind `tenant-creator`** ([ADR 0033](../adr/0033-tenant-creation-and-update-api.md)). Making a repository public needs no further role: the gates in [§6](#6-gates-before-launch) are what stand between a user and an abuse, not a second key. A stricter publishing role stays what RFC 0024 §2 said it was, a possible later step.
- **Where it lives.** `visibility` and the other fields of [§2](#2-the-repository-profile) sit on one additive row per repository, so the grant table and `tenant` stay as they are. The `public` value is refused by the API until the slices D2 to D6 are in, so nothing can be made public before its gates exist.
- **Only a published repository with at least one release is listed or readable as public** ([RFC 0037](0037-releases-and-public-snapshots.md)). A draft stays invisible to everyone, as in ADR 0118.

### 2. The repository profile

What a repository says about itself, on a new table (`repository_profile`, one row per repository, `tenant_id` primary key, created with the repository and backfilled for the ones that exist):

| Field | What it is | Rules |
| --- | --- | --- |
| Summary | One or two plain sentences for a listing | Plain text, length-capped. The long description stays `tenant.description`. |
| Licence | Optional: a label from a short list or free text, and an optional link | Optional by decision. Empty reads as "no licence stated", not as a licence. |
| Credits | Who made it: name, role, optional link | A list, capped. Separate from the publisher in [§6](#6-gates-before-launch). |
| Tags | Free-text labels for search | Normalised to lower case, capped in number and length. |
| System | The game system, one value | A distinguished tag, so it can be a filter of its own. |
| Languages | The languages the content is written in | Language codes. |
| Cover | A wide picture for the repository's page | Stored like the existing picture, in the same blob table, with the same size cap. |

- **Links are `https` only**, checked when saved, and shown with `rel="nofollow noopener"`. No other scheme is stored.
- **It is not content** in the sense of [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md): a copy never carries it, and the table goes in `repository_access`'s list of tables that are not content, with a `tenant_id` column, `FORCE ROW LEVEL SECURITY` and `same_tenant_fk` keys ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md), [ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)). The tests that fail on a tenant table in neither list cover it.
- **Readable beyond the tenant, narrowly.** Discover has to read the profile of a repository the reader is not a member of. That is a `FOR SELECT` policy on the profile and cover rows of a repository that is public, published, listed and not delisted, and nothing else. It is a second opening in the wall of ADR 0002 after ADR 0118's, and is tested the same way ([§Consequences](#consequences)).
- **Who edits it.** An Owner. Whether an Author may edit the profile is [RFC 0040](0040-authors-and-invites.md)'s to say; this RFC assumes not, since the profile is how the repository presents itself.
- **Studio** gets the profile screens, and a readiness check (summary, cover, upstreams public) before the visibility switch; the screens are in [RFC 0036](0036-repository-tooling.md) (T5, T7).

### 3. Public read for any logged-in user, and copying subscribes

- **Anyone logged in may browse.** Discover and a public repository's page, preview and counts need an authenticated user and nothing more: no library, no role, no grant. Discover without login is an alternative in [Alternatives considered](#alternatives-considered).
- **The read gate grows a second branch.** `repository_read_tenant_id()` today returns the repository only on a grant. It gains a branch for a public, published, listed repository, independent of the current tenant, so a user with no library can read. For a public repository the rows read are those of its releases ([RFC 0037](0037-releases-and-public-snapshots.md)), not its live rows; how that read is wired into the policy is that RFC's. Nothing else about the gate changes: still asked for, never ambient, still `FOR SELECT` only.
- **Copying a public repository subscribes the library to it, as `lorenzo repo offer` does.** [`repo offer`](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) grants the library and its manifest and copies them in order. The web does the same for a public repository, on the library's own authority: one action inserts the `repository_subscription` rows, with `source = public`, for the repository and every repository it is built on, then runs the copy. The insert policy gains a second case, a `FOR INSERT` where `subscriber_tenant_id = app.tenant_id`, `source = 'public'`, and the repository is public, published, listed, not delisted and not deprecated.
- **Every repository in a stack must be public** for this to work, because the library cannot be granted a private upstream by an Owner who never saw it ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)). The rule is enforced when the repository is made public ([§7](#7-flips-and-deprecate)), so a public stack is always copyable in one action.
- **Who may copy.** Whoever may copy into a library today, which is a member (Owner or Organizer). An Author may not: copying subscribes a library and changes what it holds, which is [RFC 0040](0040-authors-and-invites.md)'s capability matrix.
- **After the copy it is an ordinary subscription.** Updates, the update inbox, revoking, "drop the grant, keep the copy" all behave as they do for an invited library. What differs is only what the repository's Owner can see of it ([§6](#6-gates-before-launch)) and what a flip does to it ([§7](#7-flips-and-deprecate)).

### 4. Discover

One listing and search endpoint, and one page.

- **The endpoint** takes a free-text `q` (name, summary and tags), and filters on tag, system and language, and returns a page. It follows the API's paging convention.
- **Fields of a result:** name, slug, summary, tags, system, picture, publisher ([§6](#6-gates-before-launch)), the label and date of the latest release, and a size (how many entries and how many stat definitions). Nothing of the content.
- **What is listed:** repositories that are public, published, with a release, not delisted and not deprecated.
- **No ranking.** The order is by name or by date of the latest release, as the user chooses, never by how often a repository was copied. A popularity order would be a marketplace feature, and it would need the counts kept visible, which [§6](#6-gates-before-launch) keeps from owners.
- **A paging cap.** A hard maximum page size and a hard maximum depth, whatever the caller asks for, so that the listing cannot be used to walk the whole directory in a few requests. The values are in [Open questions](#open-questions).
- **Search** starts as a case-insensitive match, as the `/admin/users` search does ([ADR 0057](../adr/0057-platform-operations.md)); a trigram index or a derived search column is added only if [Spikes](#spikes) says the plain match is too slow.
- **The page** is the hub's Discover page and a repository's storefront (cover, summary, long description, tags, system, licence, credits, publisher, latest release and notes, what it is built on, the preview of [§5](#5-the-preview), a Report link, and "Copy to a library"); the screens are RFC 0036's S6.

### 5. The preview

Looking inside before copying is what makes a repository worth copying, and ADR 0118's "structure, not text" forbids it. This RFC amends that rule, narrowly and with an owner's switch.

- **The owner's switch**, `preview`: `off`, `showcase` or `public`. The default is **`showcase`** (decided with the maintainer). The switch is on the profile row and is asked for in the dialog that first makes a repository public, so the default is a choice the Owner saw.
- **What is never exposed:** GM-only text. The preview reads only information rows that are Everyone's (`is_public`) and the pictures attached to them (a picture is a payload of an information row, so its visibility is that row's), plus stat values. It never reads a row by who knows it, and a test asserts that no non-public row can come out of any preview route.
- **Showcase** means the Owner has chosen which entries to feature: an additive table of entries (`tenant_id`, `entity_id`), not content, in the not-content list. An Owner who has chosen none shows names and counts only. Which entries, and how many, is the Owner's call, with a cap ([Open questions](#open-questions)).
- **What each reader sees**, by owner's switch. A "holder" is a library with a grant, invited or public. A "visitor" is anyone else logged in; an "invite visitor" is someone who opened an invite link for a private repository and holds no grant yet ([RFC 0040](0040-authors-and-invites.md)).

| Reader | `off` | `showcase` | `public` |
| --- | --- | --- | --- |
| Invite visitor (private repository) | Profile and counts | Profile and counts | Profile and counts |
| Logged-in visitor (public repository) | Profile and counts | Profile and counts, and the Everyone text, pictures and stat values of showcase entries | Profile and counts, every entry's name, kinds and parents, and every entry's Everyone text, pictures and stat values |
| Holder | Names, kinds and parents of every entry, as today | As `off`, and the Everyone text, pictures and stat values of showcase entries | As the visitor's `public` column: everything Everyone's |

A holder at `public` sees nothing a library could not already copy (ADR 0119 copies all Everyone text), so it reveals nothing new to them. For a visitor it is the Owner's deliberate choice. An invite visitor sees only what the invite itself shows, and nothing in this table widens that.

- **A gated entity read.** A new route returns one entry: name, kinds, parents' names, its Everyone information (title and description), its pictures on those rows, and its stat values, filtered by the table above. The list routes ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)'s browse, with `q`) keep returning names only, at the level the table allows. Both come in two forms: under a library for a holder, and library-less for a logged-in visitor of a public repository.
- **The authors' side.** Every note on a repository's entry, wherever it is edited, shows a lock when it is Everyone's, "visible to libraries that copy this", with a one-click "make GM only". It applies to every repository, public or not, because Everyone text is already copyable by any grant today; the preview only widens who sees it before copying. Authors may use it, since it is an edit of content.
- **This amends ADR 0118** ("structure, not text"): a preview of Everyone text, to the readers and under the owner's switch above. The amendment is recorded in the ADR that builds it.

### 6. Gates before launch

Each of these is a precondition of the `public` value being accepted. They are small and independent, and each has a test.

1. **Operator delist.** `PUT /admin/repositories/{repository_id}/delist` and `DELETE` on the same path, in the existing `/admin` router behind `platform-operator` ([ADR 0057](../adr/0057-platform-operations.md)), with a free-text reason. A delisted repository leaves Discover, closes its preview and blocks new copies, and reads as unpublished to everyone but its members and operators. Libraries that already copied it keep their copies. **Suspending a user delists the repositories they own** (where they are an Owner). Un-suspending does not relist; an operator does, with the same call. This is the minimum that lets an abusive repository be dealt with without editing the database, and it is not a takedown process, which stays a future matter.
2. **A release cooldown and an asynchronous fan-out.** A repository may release at most so often (the interval is a setting, in [Open questions](#open-questions)); a release inside the interval is refused with when it is allowed again. The notification to the libraries that hold the repository leaves the request: the release writes its row and the fan-out is done after the response. Today it is in-request, which for a repository copied by thousands of libraries is a timeout and a half-sent announcement. The mechanism is a [spike](#spikes), since there is no queue.
3. **Quotas on a repository.** A maximum number of entries, a maximum total of picture bytes, and a maximum size for one picture, enforced where entries and pictures are written, for every repository tenant. The limits are set above what the seeded repositories hold, once measured ([Open questions](#open-questions)).
4. **Privacy of the libraries that copied it.** A repository's Owner sees how many libraries copied it, never which. `GET .../subscribers` lists invited libraries by name and public ones as a count, and the activity log of the repository does not record a public copy by the library's name (the library's own log does, as for any removal today). "Libraries using it" in Studio shows the invited names and one number.
5. **Publisher identity from the account.** A storefront and a Discover result say who published it from the Owners' accounts (their account names), never from a free-text field, so a repository cannot claim to be somebody else's. The Credits field of [§2](#2-the-repository-profile) is for naming those who made the content and is not the publisher. The publish dialog states that the account's name is shown.
6. **A report link and a terms line.** Every storefront has a Report link, a `mailto:` to an address set in the deployment's configuration; there is no report inbox in Lorenzo yet. The dialog that makes a repository public carries a line the Owner agrees to: that they have the right to publish it, and that publishing cannot be recalled, since libraries that copied it keep their copies. The wording is the maintainer's ([Open questions](#open-questions)).
7. **Authentication on a private repository's picture.** `GET /tenants/{tenant_id}/picture` and the cover require a logged-in user when the tenant is a private repository. A public repository's picture and cover stay open, as they are shown to every user anyway; a play tenant's picture is unchanged by this RFC. A browser `<img>` cannot send a bearer token, so a private picture is fetched by the app with the token and shown from the response ([ADR 0056](../adr/0056-profile-pictures.md) is why it was open); the API change and the hub change come in the same slice.
8. **The Discover paging cap** of [§4](#4-discover), built with the listing in D3.

### 7. Flips and deprecate

- **Private to public** is one atomic action with the repository's first release ([RFC 0037](0037-releases-and-public-snapshots.md)): the release is made, the visibility changes and the preview switch is set, together or not at all. It requires every repository this one is built on to be public already; the dialog lists the ones that are not and offers to make each public if the user owns it, and says whom to ask if not. It requires a summary, and shows the terms line and the account that will appear as publisher. It warns that GM-only text is in what a library copies ([Decided with the maintainer](#decided-with-the-maintainer-2026-10-07)).
- **Public to private** removes the repository from Discover at once and revokes every `source = public` grant, after a warning with the number of libraries it covers. The copies stay, as after any revoke, and those libraries lose their update path; the revoke notice (RFC 0036's A3) goes out through the same asynchronous fan-out. Invited grants stay. It is refused while another public repository is built on this one, naming them, since that would leave a public stack no one can copy.
- **Deleting a repository** keeps ADR 0184's rule that no grant may remain: public grants count. The refusal says to make it private first, which revokes them after the warning.
- **Deprecate** is a state a repository can be put in, public or not: it keeps its updates for the libraries that already copied it, and blocks new copies, and it leaves Discover. It carries an optional message the libraries see. It is how an Owner retires a repository without cutting off the libraries using it, which unpublishing does ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). A deprecated repository can be un-deprecated.

### 8. Operations

- **The edge rate-limit rule is the maintainer's task before public launch, and the build does not need it.** [The runbook](../operations/invite-link-rate-limiting.md) describes the rule for `/invites/*`, which has to be in place before the API gets a public production address. Discover and the copy of a public repository are new routes of the same kind: authenticated, but cheap to call in a loop. D7 extends the runbook to name them, so there is one rule set to configure. The in-process limiter, per instance, stays what the runbook says it is, a backstop.
- **A takedown process is a future matter.** The delist in [§6](#6-gates-before-launch) is the lever; who may ask for it, how a complaint is judged, and what the Owner is told are not designed here.

## Later, not now: pass-through grants for a private upstream

Grants are not transitive ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), so a private repository built on another private one needs the Owner of each to grant every library, and a public repository must have public upstreams ([§7](#7-flips-and-deprecate)). Public repositories remove most of the need for anything else. What remains is a private upstream whose Owner is willing for their repository to reach libraries only through bridges built on it. An opt-in pass-through is the likely shape: that Owner allows a named bridge to pass their access on to the libraries the bridge's Owner invites. It would change the SQL read gate (a second route to a grant: through a bridge), the manifest, and the revoke rules, so it is not built or sketched in more detail here. It starts when someone has a private upstream to share.

## Decided with the maintainer (2026-10-07)

- **Public discovery is in v1.0.** Opt-in for each repository, private by default, for logged-in users only.
- **Copying a public repository subscribes the library**, as `lorenzo repo offer` does today.
- **The licence is optional.**
- **Takedowns are a future matter.** A minimal operator delist comes before discovery, because without it the first abusive repository can only be fixed in SQL.
- **The preview's default is `showcase`.**
- **Releases are snapshots only for public repositories** ([RFC 0037](0037-releases-and-public-snapshots.md)); a private repository is read live.
- **The edge rate-limit rule is the maintainer's task** before public launch; the build does not need it.
- **Repository creation stays behind `tenant-creator`.**
- **Pass-through grants for private upstreams** are for later, with the upstream owner's consent.
- **GM-only text stays in a public repository's copy**, as it does for an invited library. The author chooses what to mark GM only (the lock in [§5](#5-the-preview)), the flip to public warns that GM-only text is in what a library copies, and the preview never shows GM-only text. A library's campaign GMs read it too ([RFC 0036](0036-repository-tooling.md) A4).

## Spikes

- **The fan-out mechanism.** What must be tried: moving the release notification out of the request on what exists (a background step after the response, a table of pending notices drained by a scheduled call, or a Cloud Run job), against a repository with a few thousand subscribing libraries, and whether a half-finished fan-out can be resumed after an instance dies. What would change the decision: if an in-process step is lost with the instance and cannot be resumed, a durable pending table is required, which means a drain trigger the deployment does not have; and if even that is too heavy, ADR 0008's queue, with the Redis it needs, is no longer deferrable.
- **Discover's query at scale.** What must be tried: the listing and search against a few thousand generated repositories with profiles, with the plain case-insensitive match and with a trigram index. What would change the decision: if the plain match is too slow at the sizes in the test, a derived search column or a trigram index is part of D3, and if filters on tag and language need their own tables to be fast, the profile's lists stop being columns.
- **The public read through a release** is gated by [RFC 0037](0037-releases-and-public-snapshots.md)'s round-trip spike (R1). If a release document cannot reproduce a repository's content exactly, D2 to D6 do not start, and this RFC's public read is rewritten around whatever that spike finds.

## Slices

| # | What | Depends on | Touches |
| --- | --- | --- | --- |
| D1 | `visibility`, `preview` and the profile fields on a profile table, `source` on the grant, the cover, the `https`-only check; `public` refused until D6 | none | api |
| D2 | The public branch of the read gate, the library-less read routes, and copying a public repository subscribes the library and its stack (`source = public`) | D1, [RFC 0037](0037-releases-and-public-snapshots.md) R1 and R6 | api |
| D3 | The Discover listing and search endpoint, with the paging cap, and the hub's Discover page and storefront (RFC 0036 S6) | D1, D2, RFC 0037 R3 | api, hub |
| D4 | The preview: the owner's switch, showcase entries, the gated entry read, the "visible to libraries that copy this" lock on notes | D2, RFC 0037 R5 | api, hub, bench |
| D5 | The flips: private to public with the first release, public to private, the dependents rule, delete; Studio's visibility switch and warnings (RFC 0036 T7) | D1, RFC 0037 R5 to R8 | api, hub |
| D6 | The gates: operator delist and suspension, release cooldown and asynchronous fan-out, quotas, privacy of copying libraries, publisher identity, report link and terms line, picture authentication | D1; the cooldown after RFC 0037 R3 | api, hub |
| D7 | The runbook extended to Discover and public copy, for the maintainer to apply before launch | none | docs |
| D8 | Deprecate | D1, D2 | api, hub |

D6's parts are independent and may each land as their own change. The spikes come first where a slice depends on one: the fan-out mechanism before the asynchronous part of D6, the Discover query with D3. `public` becomes accepted when D2 to D6 are in; D7 is before launch on the production address and not a condition for building.

## Open questions

- **How many showcase entries, and whether items already in the public catalog count.** A cap keeps a showcase from becoming the whole repository. The item field `in_public_catalog` is a ready-made "featured" flag for items but not for beings.
- **Limits.** The release interval, the entry quota, the picture quotas, the maximum page size and depth, the lengths of summary and tags, and the number of credits and tags are settings whose values come from measuring the seeded repositories and the Discover spike.
- **What a delist does to libraries that already hold the repository.** The proposal is that the copies stay and update checks stop, since an update check serves the content again. The other reading is that updates continue and only discovery stops.
- **Which repositories a suspension delists,** when the suspended user is one Owner of several.
- **Who may see a private repository's picture.** Authentication alone is the decision; membership or a grant is stricter, and would also need the invite visitor to count.
- **The wording of the terms line and the report address.** The maintainer's.
- **Whether a public repository's dependents block it going private,** or only warn. The proposal is to refuse, since the stack would otherwise be broken for new copies.
- **Whether the preview shows inherited stat values** or only values set on the entry itself. Inherited ones need the stat resolution applied to the release; the proposal is to show them if that costs nothing extra in D4.
- **Whether a deprecated repository names a successor.** A message is decided; a link to a replacement is a small addition.
- **Whether the in-process limiter also covers Discover.** It is keyed by client address for the invite routes; Discover is authenticated, so a per-user key is possible.

## Not in scope

- **A marketplace:** ranking by popularity, featured and trending lists, curated collections.
- **Ratings, reviews and comments** on a repository.
- **Payments and paid repositories.** The grant is still the place a payment step could plug in (RFC 0024 §8), and nothing here moves it.
- **A takedown process:** who can ask, how it is judged, appeal, the notice to an Owner. Only the operator's delist is built.
- **Directory access without logging in,** and a public, unauthenticated read of a repository's content.
- **Making a repository public by default,** and any way to make an existing one public without its Owner.
- **Requests for access** to a private repository by name or slug.
- **Pass-through grants** (above), **partial copies** and **a repository split tool**.

## Alternatives considered

- **Grant by slug or name search, instead of a directory.** An Owner, or a library asking, looks a repository or tenant up by name. That is an enumeration surface over every tenant, it invites notification spam to whoever is found, and it still gives a library no way to see what it would be getting. Discover shows only what an Owner chose to make public.
- **A directory without login.** Easier to share and to index, and a new anonymous surface: scraping, cost, a picture endpoint that is open already, and nobody to attach a report to. Logged-in only costs one click for a visitor and keeps the Owners' account names (which the publisher line shows) among people who have accounts.
- **Public by default.** Publishing cannot be recalled: libraries keep what they copied. An Owner should choose that, with the terms line in front of them.
- **A public repository read live.** Cheaper to build, and the repository's Owner then edits what strangers are reading. [RFC 0037](0037-releases-and-public-snapshots.md) gives a public repository releases, so what a stranger copies is what the Owner released.
- **Showing the whole of a repository's text to any holder, with no switch.** A holder could copy it all anyway, but an Owner might not want it shown to people deciding whether to. The switch has `public` for the Owner who does.
- **Ranking in Discover** by number of copies. It needs those counts shown, which [§6](#6-gates-before-launch) keeps private, and it rewards size over fit.
- **Letting a library subscribe to a private repository by itself** with a link. That is [RFC 0040](0040-authors-and-invites.md)'s invite for a library, which an Owner creates; a library's own subscription is for public repositories only.

## Consequences

- **A library can find and copy a repository without anyone's tenant id,** and the repository's Owner stays out of it until they choose to see counts.
- **The wall of ADR 0002 gets a second, narrow opening.** After ADR 0118's read of a granted repository, a logged-in user can read a public repository's profile, and its releases through the public branch of the gate. Both are `FOR SELECT` only, both are tested the way ADR 0118's are (unset, wrong repository, draft, delisted, private, deprecated, writes touch nothing), and the test that fails on a tenant table in neither list covers the new tables.
- **ADR 0118 is amended** in one sentence, "structure, not text": a preview of Everyone text, under the Owner's switch.
- **A grant now has a source,** and everything that lists or revokes grants has to know it: the subscribers list, delete, a flip, `lorenzo repo` (which keeps meaning `invited`).
- **A new set of tables** (profile, cover, showcase entries) is not content: nothing a library copies carries them.
- **Publishing a public repository is a heavier act** than today's `PUT /published`: a profile, a release, upstreams that are public, a terms line and a cooldown. That is the cost of discovery, and none of it is added to a private repository's way of working.
- **Public repositories are bounded:** an entry quota, a picture quota and a cap on pictures protect the database, which holds pictures as bytes.
- **Moderation starts as one lever and a mailto,** which is enough to stop an abuse and not enough to judge a dispute. The process is a later decision and will need its own RFC.
- **The hub gains Discover and a storefront,** and Studio a profile, a visibility switch and flip warnings; Bench shows the lock on notes ([RFC 0036](0036-repository-tooling.md)).
