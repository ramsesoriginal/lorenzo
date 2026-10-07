# RFC: Bench — the authoring app, working offline, and room for new kinds of content

Status: accepted, decided with the maintainer on 2026-10-07: Bench is its own static Astro app (`apps/bench`) written in small, own TypeScript with no component framework, every write in it goes through a command layer that also makes working offline possible, what is stored on the device is per user and cleared on logout, inherited and computed values are marked "Out of date" rather than recomputed offline, conflicts are compared field by field against a base kept with the change, and new kinds of content arrive as registry entries, not rewrites ([§1](#1-the-app) to [§5](#5-conflicts), [§8](#8-room-for-new-kinds)). The sync API in [§6](#6-the-sync-api), the order in [§7](#7-the-editor-surface-and-the-order-it-is-built-in), the reactive layer in [§9](#9-ui-layer-rules) and the spike that gates it ([Spikes](#spikes)) are proposed. Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Row "Authoring tool" of [v1.0](../../v1.0.md); part of [RFC 0036](0036-repository-tooling.md).

## Context

Writing a repository is the work everything else in [RFC 0036](0036-repository-tooling.md) exists to carry: Studio publishes it, Shelf copies it, [RFC 0038](0038-public-repositories-and-discovery.md) lets strangers find it. This RFC is the tool that writes it.

A word first, as [identity §14.3](../brand/identity.md) does for library and tenant. What a user sees is an **entry** with one or more **kinds** (an item, a being, later a place or a clock); in the API and the database it is an `entity` row with a marker table per kind. Both words are used below, the second in the technical parts.

### What authoring needs

Writing a repository is long sessions of editing many entries at once: make an item, give it parents, set a handful of stats, write a description and notes, fix a link name, see what it inherits and what is its own, compare thirty weapons side by side, change a stat's formula and see who depends on it. It is often done where there is no good connection. The things that were found missing while shaping this:

- A way to see and change **many entries at once**: a grid of entries and stats, not one detail page per entry.
- A **stat vocabulary** editor and a **formula** editor. The API creates, lists and deletes stat groups and definitions, and has computed stats with a dry run and a "dependents" list ([ADR 0104](../adr/0104-computed-stats.md), [ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)); no screen uses them.
- **Working offline**, with what was written kept safe until it can be sent.
- **Undo** that survives a reload ([ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md) keeps descriptive-content edits such as stat values out of the activity log on purpose, and there is no per-field history).

### What exists

[RFC 0024](0024-repositories.md) §A10 said that authoring a repository's content "needs nothing new: a repository is a tenant, so its members use the same catalog, stat, and information screens as anywhere else". That holds for **tenancy**: a repository needs no new place to be written. It does not hold for **tooling**:

- `apps/inventory-web` edits catalog items one at a time: create, name, parents (the prototype set, with the ancestry tree and a "used by" lookup, [ADR 0073](../adr/0073-item-prototype-graph-inspection-and-bulk-editing.md)), descriptions and notes in LorenzoScript, link names, tags. It does not write stat values other than tags, has no stat vocabulary or formula screens, no bulk editing and no pictures, and it has no offline use at all. It is built around a table (the board, giving, moving), which a repository does not have.
- `apps/account-hub` manages who is in a repository and shows it, read-only; it has no content editors ([ADR 0178](../adr/0178-account-hub-repositories.md)).

### What the API gives an offline editor, and what it does not

Read from `apps/api` for this RFC:

- **Creates take no id.** `UuidPk` is a database default (`gen_random_uuid()`, `db.py`), and the create routes build `Entity(...)` without one (`routers/items.py`; further sites in `item_instances.py`, `groups.py`, `characters.py` and `campaigns.py`). A create whose response is lost and which is sent again makes a second row. The one natural guard is the link name: it is unique per tenant across every entity and a second create with a taken one is a 409 ([ADR 0107](../adr/0107-entity-slugs-and-batch-resolve.md), [ADR 0139](../adr/0139-name-an-item-when-it-is-created.md)).
- **`GET .../entities` is a name-ordered page of summaries**, an id and a name each (`EntitySummary`). Everything else comes from one `GET .../entities/{id}` per entry. That read gives stats by **name**, as the **effective** value with an `own` flag and no definition id, while the write is `PUT .../stats/{stat_definition_id}`; it has no kinds and no per-stat version. A mirror of a repository on today's API is one request per entry, and does not hold what it needs to write.
- **`If-Match` is optional everywhere**, so without it the last write wins. Entity ETags are the entity row's `updated_at`; a stat write checks the stat row's own `updated_at` and does not touch the entity row (`routers/entity_stats.py`), so an entity's version does not move when one of its stats does.
- **Effective values are computed on the server.** Which stored value or formula wins for an entry is decided by the view `v_effective_stat` (nearest ancestor first, [ADR 0037](../adr/0037-effective-stat-resolution.md)), and formulas are evaluated in Python (`stat_evaluation.py`, [ADR 0104](../adr/0104-computed-stats.md)); inherited descriptions accumulate down the chain ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md)).
- **Nothing records a deletion.** Items and entries are deleted with `session.delete`; `entity_change` is a player's change feed, one row per recipient and deliberately without a foreign key to the entry ([ADR 0099](../adr/0099-player-facing-change-feed.md)), not a log of the repository. `entity_prototype`, `entity_slug` and `entity_stat_group` have no timestamp columns at all.
- **No response compression is configured in the API code** (a search of `apps/api/src` finds none). Whether it comes from the edge or from a middleware is not known here.

### What binds the app

[ADR 0004](../adr/0004-static-astro-frontend.md) (every frontend a static Astro app, no server-side rendering, no secrets) is a hard rule and holds. [ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md) decided for account-hub that there is no component framework and no service worker; it is account-hub's ADR, and the second half is the one thing Bench needs different. [ADR 0080](../adr/0080-account-hub-css-conventions-and-shared-dom-helpers.md) (purpose-named classes in a stylesheet, no scoped `<style>`, no inline styles) and [ADR 0098](../adr/0098-branding-css-app-and-package.md) (brand tokens from `@lorenzo/brand`) hold. Brand [§15.1](../brand/identity.md) says state is never colour alone, which matters for [§4](#4-what-offline-cannot-compute).

## Decision

### 1. The app

**`apps/bench`: a static Astro app, the authoring tool, named "Lorenzo Bench"** (ADR 0194 fixes the name and the words used in it; the name follows brand §3.3's "Lorenzo `<descriptor>`" pattern).

- **Static Astro, `output: 'static'`, and its own small TypeScript.** No component framework: no Lit, no React, no Svelte, nothing that does the work of one. The app is one page with its own router, so the outbox runner and the editors outlive a change of view ([§9](#9-ui-layer-rules) says what the small layer is). Astro builds the page and its assets; everything else is the app's.
- **What it reuses.** `packages/api-client` (the typed client, [ADR 0122](../adr/0122-api-client-package.md)), `@lorenzo/brand`, `packages/lorenzoscript` and `packages/lorenzoscript-editor` for description and note text. It does not import from `apps/inventory-web` or `apps/account-hub`: where Bench needs something they already have, it is a second consumer, and the generic part moves to a package in the slice that needs it, as AGENTS.md asks.
- **Its own Authgear client**, as for the other apps ([ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md)), registered by the maintainer (it gates real-login testing). The client needs a **long refresh-token lifetime**, since the point is editing for long stretches away from a connection. Whether Authgear Cloud lets a client's lifetime be set that way is not known: [the deployment notes](../operations/deployment-setup.md) say the same about the CLI's client, and it is an [open question](#open-questions). An expired session never touches what is stored ([§3](#3-the-local-store-and-working-offline)).
- **Cloudflare Pages through its Git integration**, its own project and its own `PUBLIC_AUTHGEAR_*` variables, with the trailing-slash redirect path [ADR 0071's addendum](../adr/0071-account-hub-stack-auth-deploy.md) found.
- **Scaffolding follows [adding an app](../guides/adding-an-app.md)**: a `mise.toml` with `dev`, `lint`, `test` and `build`, a `release-please-config.json` entry, a Dependabot entry, pre-commit hooks, and the **`app:bench` label**, created and added to the scope table of [the labels guide](../guides/labels-milestones-and-metadata.md) in the scaffold PR. No deploy workflow, as for the other Pages apps.
- **ADR 0071 is amended, for Bench only.** The line "no service worker" was written for an app with no offline use. For Bench a **service worker is allowed, for the app shell only** ([§3](#3-the-local-store-and-working-offline)). The "no component framework" line is kept, and Bench follows it. The amendment is an addendum to ADR 0071 in slice B1.
- **Hand-off to Studio.** Bench has no publish, people or releases screens; its header has a plain link ("Publish…") to Studio in the hub, carrying the repository's id. Both apps' URLs come from env config; a shared navigation or app switcher is not part of this program ([RFC 0036](0036-repository-tooling.md)).

### 2. The command layer

**Every write Bench makes is a command.** There is no code path that calls a write route from a screen. A command is a small record:

- **A type and a version**, from a **typed registry**: `entry.create`, `entry.set-name`, `entry.set-link-name`, `entry.set-parents`, `stat.set`, `stat.clear`, `tag.set`, `description.set-text`, `note.add`, `entry.delete` and so on. A registry entry says how to **apply** the command to the local store, how to **send** it (which route, with which `If-Match` if the route takes one, built on the typed client), which **fields** it touches, which ids it **uses**, and how to make its **inverse**.
- **Its fields, each with a base.** For every field a command changes, it stores the value the user saw when they changed it, the **base**, next to the new value. This is what [§5](#5-conflicts) compares against. It is kept in the command, on the device, so no server-side snapshot or history is needed.
- **A client-made id** for anything it creates (see W2 in [§6](#6-the-sync-api)), so a later command can name a thing an earlier, still unsent command makes.

**Applying** a command changes what the user sees at once. The local store is a mirror of the server's last known state; what the user sees is **the mirror with every pending command applied in order**. That one rule does most of the work:

- A command that is still **pending** can be **cancelled**: take it out of the outbox and the view is what it was. This is undo for anything not yet sent, and it survives a reload because the outbox does.
- A command that **has been sent** is undone by **enqueueing its inverse**, built from the value the server says it replaced (`previous`, W1) or from its stored base.
- So the outbox is the undo history. The session-only undo considered for the other apps is not needed here.

**The outbox runner** sends commands **serially, in the order they were written, and in dependency order**: a command waits for any command that makes an id it uses, and for an earlier command on the same entry that is paused. It **pauses on a conflict** ([§5](#5-conflicts)) at that command and everything that waits on it; commands on other entries carry on, so one disputed weapon does not strand the typo fixes elsewhere (strict first-in-first-out is the alternative, an [open question](#open-questions)). One runner runs per user at a time: a second tab does not send, and reads the store as it changes (the browser's Web Locks API is what is to be tried for this, [Spikes](#spikes)).

A command ends in one of three states beyond "waiting": **Synced** (sent, accepted), **Conflict** (the field changed under it), or **needs attention** ([§3](#3-the-local-store-and-working-offline): it cannot be sent as written). A command that fails because there is no connection stays waiting; one the server refuses for another reason (a 422, a 403, a 409 that is not a replay) pauses the runner at that command as needs attention, with what the server said.

**Stat vocabulary editors, the formula editor and every later feature are new command types**, added to the registry once the layer exists; nothing is written around it. That is why the layer comes before them in [§7](#7-the-editor-surface-and-the-order-it-is-built-in).

### 3. The local store and working offline

**One IndexedDB database per user, keyed by the account's user id** (from `GET /me`), through a thin wrapper written for the app, with no dependency. It holds what Bench needs and nothing else:

- **The mirror**: for each pinned repository, its entries (names and bodies), its stat groups and definitions, and the ancestry Bench needs.
- **The outbox**: the commands of [§2](#2-the-command-layer).
- **Metadata**: the revision each mirror was last taken at, the outbox schema version, what was pinned.

It is Bench's only cache. The service worker does not cache API responses, and Bench has no second request cache beside the store.

**Per user, cleared on logout.** What is stored includes text only the GM may read, and the device may be shared, so:

- Nothing is stored under a name that two accounts share; a second account signing in on the device starts from an empty store of its own and never sees the first's.
- **Logging out deletes the user's database.** If the outbox is not empty, logout **warns instead of wiping**: it says how many changes have not been sent and offers to **Sync** them now, to **discard them and log out**, or to cancel. If Bench is offline, Sync is not offered, and the warning says discarding loses the changes. There is no "log out and keep them": keeping them is what the decision rules out.
- **A session that expires is not a logout.** The store stays; signing in again as the same user continues from it.
- Whether the text should also be encrypted on the device is an [open question](#open-questions); browser storage is readable by whoever can read the profile.

**The outbox outlives deploys.** Commands written yesterday are sent by tomorrow's code, and API stability is not a constraint on the API in early development, so:

- Every command carries its **type and version**, and the store an **outbox schema version**. On start, Bench upgrades old commands with a function per version.
- A command that cannot be upgraded or sent as written is not run and not dropped: it goes to **needs attention**, and the user sees what it was meant to do and can re-enter it or discard it.

**A shell-only service worker.** It precaches the built app (the page, scripts, styles, fonts, icon sprite) so Bench opens with no connection, and updates by "reload to update", never swapping code under an open edit. It does not handle requests to the API's origin at all, so an authenticated response is never in a cache that outlives a logout; and it never answers the auth redirect route from a cache. Which navigations it answers is slice B4's to specify.

**Pinned means every repository you author.** Bench makes available offline every repository in which the user's role lets them edit it (Owner, Organizer, or Author per [RFC 0040](0040-authors-and-invites.md)), found through `GET /tenants`, which returns the tenant's `kind`. There is no pinning screen to forget:

- **A cap and a size indicator.** The total kept on the device has a ceiling, and each repository shows what it takes ("Available offline, 2,140 entries, 3.1 MB"). Over the ceiling, repositories are pinned in the order they were last opened, and the rest say they are online-only until the user frees room. The ceiling's value comes from what the [spike](#spikes) measures.
- **Names first, bodies lazily.** A first pin pulls the **name list** (cheap: `GET .../entities`), so the explorer works at once, then fills in bodies in the background from the export (W3). An entry opened before its body has arrived is fetched on its own when online, and says it is not on this device yet when it is not. Filtering by kind or parent works as bodies arrive, because summaries carry neither.
- **Library and Studio stay online-only.** Offline use is for writing a repository, not for copying or publishing one.
- **Storage can be evicted.** The browser may drop a site's storage under pressure; Bench asks for persistent storage and tells the user when it was not granted. Whether a phone's browser keeps an unvisited site's storage for long is not known here ([Spikes](#spikes)).

**Terms.** The six words of ADR 0194 are used as they are, and carried by text or an icon as well as by colour (brand §15.1): **Saved on this device** (the change is stored here; shown while Bench cannot send), **Waiting to sync** (stored and queued, with a count), **Synced**, **Out of date** ([§4](#4-what-offline-cannot-compute)), **Conflict** ([§5](#5-conflicts)), and **Sync**, the action that sends what is waiting and then brings the mirror up to date. "Sync" means only this, between Bench and Lorenzo; a library bringing in a repository's changes is an update, not a sync.

### 4. What offline cannot compute

An entry's **own** values are what the user typed, and are exact. Everything the **server derives from other entries** is not: the effective stat an entry inherits, the result of a formula, the tags and descriptions it takes from its parents. Computing those on the device would be a second implementation of `v_effective_stat` and of the evaluator, and it would drift from the first.

- **Bench does not recompute inherited or computed values.** It shows the last value it fetched.
- **It marks them "Out of date" as soon as anything they depend on has changed offline**: a pending command on an ancestor's stats, tags, description or parents, on the entry's own parents, or on a stat definition or formula it reads. The test is on the local mirror's parent links, with every pending command applied, and errs on the side of marking too many; marking too few is the bug.
- **An entry made offline has no inherited values to show.** It shows them empty, with the same mark.
- **Sync clears the mark.** After the commands are sent, Bench refetches the entries that were marked, and the mark goes when the server's value arrives.
- **The mark is text as well as colour**, and uses the same grammar as other inheritance marks in the interface (brand §18).

This keeps the first rule of the layer simple: what the user wrote is stored exactly; what the server works out is shown, never guessed.

### 5. Conflicts

A conflict is a **field** that has changed on the server since the user's base. Fields are the things a command names: an entry's name, its link name, its parents, each own stat value, each tag, each note's text and readers, and so on. Before a command is sent, Bench reads the entry's current state from the server (once per entry per run), and for each field of the command compares three values: the **base** it stored, **mine** (the new value), and **theirs** (the server's now).

| Compare | Result |
| --- | --- |
| theirs equals base | send mine; nothing changed under it |
| theirs equals mine | already there (this is also how a replayed command resolves); mark Synced, send nothing |
| all three differ | **Conflict** |

- **Text is never resolved by Bench.** For a description or a note both versions are shown with their differences and the user picks **Keep mine**, **Use theirs**, or edits, even where a line-by-line merge would be clean. A wrong silent merge of someone's prose is the worse failure.
- **A set**, the parents of an entry, is compared element by element, the way [ADR 0121](../adr/0121-repository-updates-and-re-sync.md)'s updates already merge an entry's prototype set: what each side added or removed that the other did not touch carries over, and only a parent one side added and the other removed is a conflict.
- **A scalar** (a number, a tag, a name) is a choice between the two.
- **The review is the shared one.** Conflicts are shown with the same three-way review element as an update's conflicts in Shelf ([RFC 0036](0036-repository-tooling.md), slice S5), with Bench's stored base where the update has the copy's snapshot. If that element lives only in the hub when Bench needs it, Bench is its second consumer and it moves to `packages/repo-ui` ([§9](#9-ui-layer-rules)).
- **The write is guarded where the route allows.** The compare happens a moment before the write, so a command goes out with `If-Match` wherever its route takes one. Where it does not (a stat write has no version a read gives), the server's answer says what it replaced (`previous`, W1): if that is not the base, the command is marked Conflict after the fact with the replaced value in hand, and the inverse restores it.
- **Deletes are "pending, confirm on sync".** What deleting an entry would take from libraries that hold it, and how many hold it, is the warn-with-count of [RFC 0041](0041-entity-kinds-and-author-freedom.md) (slice K9), which cannot be known offline. A queued delete shows as pending; when it comes up in the run, the runner pauses, asks the server for the count, and the user confirms or cancels with the number in front of them. A delete the server refuses for a reason it states (an item still has instances) is needs attention.

### 6. The sync API

Three additions to `apps/api`. They are the work offline needs from the server, nothing else, and none of them is a new table unless W3's revision needs one, in which case it follows [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md), [ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md) and [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md).

**W1: stat writes that can be checked and undone.**

- A stat write **bumps the entity's version** (its `updated_at`, and `updated_by`), so an entity's version and the export's revision move when a stat does.
- The response says what it **replaced**: a `previous` value, for the write routes that have none. The shape (a field on the entity detail the route already returns, or a wrapper) is the ADR's. This is what makes a stat write checkable after the fact and exactly undoable.
- **`DELETE .../entities/{id}/stats/{stat_definition_id}`** clears an entry's own, direct, non-boolean value, so the entry inherits again. Booleans (tags) have `DELETE .../tags/{id}` already. Without this, undoing "I set the damage on this weapon" and "revert to inherited" cannot be written. It applies to a formula-typed stat too only if the ADR says so.
- Which other writes have no version at all (a link name and attaching a group are suspected) is for W1's ADR to audit.

**W2: ids made by the client on creates.**

- A create that Bench queues takes an **optional `id`**. Which routes: every create Bench can queue offline, which is the entry creates (`POST /items` and, once it exists, the generic entry create of [RFC 0041](0041-entity-kinds-and-author-freedom.md), K2) and the creates of information (notes). The rest are added when Bench queues them.
- **The replay rule.** If a row with that id is **visible in the caller's tenant** (row-level security decides what is visible), the create is a replay: return the existing row. Otherwise, if the id is taken by a row the caller cannot see, the insert fails and the answer is a **generic 409**; it never says the id belongs to another tenant.
- **Interim, until W2 lands: Bench always sends a link name on a create.** A replayed create then 409s on the taken link name, and the runner treats that as success only after it has read the entry by link name (`GET .../entities/by-slug/{slug}`) and found the name and parents the command carried; anything else is a Conflict. The link name is the name's slug; a genuine clash is for the user to rename.

**W3: a bulk entity export.**

- **`GET /tenants/{t}/entities/export`**, in **cursor pages** of entry detail in a stable order, **compressed** (gzip, wherever it is applied), carrying an **`ETag` that is a per-tenant revision**, so a repository that has not changed since the mirror was taken answers `304`.
- **The entry shape is W3's to define**, from what a mirror needs to be written back from: the kinds, the link name, the parents, **own stat values by definition id** (the detail today gives effective values by name), tags, information as the caller may read it, and the flags a write needs. It is not `EntityDetailOut` as it stands.
- **The revision has to move on every content write**, including deletions and the three tables without timestamps ([Context](#what-the-api-gives-an-offline-editor-and-what-it-does-not)); a maximum of `updated_at` values cannot do that. One way: a counter on the tenant row bumped in the same transaction, by statement-level triggers on the tables of `REPOSITORY_CONTENT_TABLES`. It makes concurrent writers in one tenant contend on one row, which is not measured; the ADR decides, with the cost in front of it.
- **Today's lists page by number and size**; this one pages by cursor so the mirror is consistent across pages.

**Deferred: a delta feed with tombstones.** Telling a client "what changed since revision N" needs deletions recorded (nothing records them today), row triggers on the content tables' children, and a cursor that is safe against transactions committing out of order, since a plain increasing counter can skip a row committed late. It is built only if a full refetch behind the ETag turns out not to scale ([Spikes](#spikes) measures it). Until then a changed repository is re-fetched whole.

### 7. The editor surface, and the order it is built in

In this order, each a slice in [Slices](#slices):

1. **The command layer and an online-first item editor, with the LIVE banner** (B3). Create an entry (including from a parent: `POST /items` takes parent ids), name, link name, parents, description and notes in LorenzoScript, tags, own stat values; the explorer on the name list; undo through the outbox. Online first means the outbox runs and everything is a command from the first screen, and the mirror is what is on screen; it does not yet survive a closed tab with no connection. Each entry shows "Saved on this device", "Waiting to sync" or "Synced" from here on. The **LIVE banner** says, wherever a published repository is edited, that libraries using it see edits now (private repositories read live, [ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)); for a public one [RFC 0037](0037-releases-and-public-snapshots.md) says "Edited since release X" instead, with the wording the API reports. Duplicating an entry waits for [RFC 0041](0041-entity-kinds-and-author-freedom.md) (K4); until then a variant starts from a parent.
2. **The offline foundation, then conflict review** (B4, B5): the store, outbox schema version and needs-attention state, the shell-only worker, sync status, "Out of date" marks, pinning with its cap; then the three-way review and queued deletes.
3. **The compare grid and the bulk stat read** (B6): entries as rows, stats as columns, own versus inherited told apart, edited in place through commands; it needs the bulk effective-stat read of [RFC 0041](0041-entity-kinds-and-author-freedom.md) (K7).
4. **The stat vocabulary and formula editors** (B7): groups and definitions, rename in place (the rename-only change of K6 amends [ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md)), enum values, the four formula kinds with the dry run and the dependents list. Each is new command types; they come after the layer so they are not retrofitted.
5. **Pictures** (B8), once entries can have them (K8 of RFC 0041). Not offline.
6. **A structured pack editor** (B9): rows of a count, an item and a label, written as the list the pack text already is ([RFC 0035](0035-inventory-files-and-placeholder-items.md) and [ADR 0145](../adr/0145-pack-contents-in-the-description.md) use the same grammar). Until then a pack is text.
7. **An SVG ancestry graph** (B10), last. The ancestry shown as an indented outline with ancestors and descendants panels comes earlier, and the graph uses the provenance grammar of brand §18.

### 8. Room for new kinds

[RFC 0026](0026-world-model-axes-and-address.md) and [RFC 0028](0028-time-causality-and-calendars.md) are both still "proposed, decision open". What they propose has one shape in common: a frame (plane, sphere, timeline), a connection (a portal, with its endpoints) and a calendar (a JSON definition of a stated format) are each **an entity with a marker or small subtype table**, as an item and a being are. That is [RFC 0041](0041-entity-kinds-and-author-freedom.md)'s model too (K1, a registry of copyable tables), so a new kind is a migration plus registry entries on the server. Bench's side is the same idea.

**Seams now, built into the first slices:**

- **The command registry** ([§2](#2-the-command-layer)). A new kind's commands are registry entries; the runner, the store and the review know nothing about kinds.
- **A kind-agnostic entry shell.** The entry page is a header (name, link name, kinds, parents) and sections that **editors contribute for each kind the entry has**; an entry that is an item and a being gets both. Item and being are the first two editors, written as modules the shell loads **on demand**, so an app with ten kinds does not ship ten editors to someone writing items.

**Registries later, extracted when the first place, clock or calendar kind exists** and not before, since four registries drawn from two kinds would be guesses: **types** (what kinds exist, how one is created), **connections** (kinds of link between entries), **views** (the explorer, compare grid and graph as views over entries), and **editors**. When that kind arrives, its RFC or ADR is read against this one first, and any difference is decided then, with the real kind in hand. The calendar's structured editor over its definition is one more editor.

### 9. UI layer rules

- **Own small helpers, nothing more**: a tiny signal and computed-value helper, and a thin base for **custom elements** for the parts that repeat. Elements use the **light DOM**, so the brand CSS and [ADR 0080](../adr/0080-account-hub-css-conventions-and-shared-dom-helpers.md)'s purpose-named classes apply unchanged and there is no second styling system.
- **The 300-row editable grid decides what the reactive layer must do** ([Spikes](#spikes)): changing one row's state updates that row; typing never loses a keystroke, focus or selection when rows around it change; one row can show a conflict.
- **Failing the spike is reported to the maintainer, not solved by adding a dependency.** What to do then (a narrower first grid, online drafts with the outbox as the next slice, or a change to the decision above) is the maintainer's to decide.
- **`packages/repo-ui` only when a second consumer needs the same element**, never in `apps/brand`: the conflict and diff review is the likely first, shared with Shelf and Studio ([RFC 0036](0036-repository-tooling.md), S5), the LIVE banner the second if Studio shows it too. A package starts as one element with its own tests, independently versioned.
- **Tests**: the logic (registry, runner, three-way compare, "Out of date" test, outbox upgrade) as plain TypeScript tested in Vitest; end-to-end tests with Playwright against the real API in CI as `apps/inventory-web` does ([ADR 0114](../adr/0114-inventory-web-end-to-end-tests.md)), with the browser set offline for the offline paths.

## Decided with the maintainer (2026-10-07)

- **Two apps.** Library and Studio are areas of account-hub; Bench is its own app.
- **No component framework.** No Lit, React, Svelte or similar; Astro is already a compromise. Own small TypeScript, extending the brand CSS where needed. A `packages/repo-ui` is a proper package, only when a second consumer needs the same element, and never in `apps/brand`.
- **Its own Authgear client**, and the app's URLs in env config; a shared navigation and app switcher are out of this program.
- **Offline from the start.** A command layer and a local store with an outbox, from the first slice; the first screens are online-capable on the command layer and the offline foundation follows straight after.
- **Out of date, not recomputed**, for inherited and computed values; **per-field three-way compare** for conflicts, reusing the diff element; **pinned = every repository you author**; **Library and Studio online-only**; what is on the device is **per user and cleared on logout**.
- **Seams now, registries later**: the command registry and a kind-agnostic entry shell now; the types, connections, views and editors registries when the first non-item, non-being kind exists.
- **Kinds are marker tables**; places, clocks and calendars arrive through RFC 0026 and RFC 0028.
- **Names**: "Lorenzo Bench", `apps/bench`, label `app:bench`.
- **API stability is not a constraint** in early development, so W1 to W3 may change contracts; the outbox is why Bench, unlike the API, versions what it stores.
- **Spikes run on throwaway branches**, with the findings written back into this RFC; each slice is its own short-lived branch off `main`.

## Spikes

**B0: the grid, the outbox and the export, on a throwaway branch before the scaffold.** One prototype, built on the small helpers of [§9](#9-ui-layer-rules) and a stub of the export (static JSON pages), trying together:

- **A 300-row editable grid** (name and a few stats, edited in place) driven through an outbox: each row shows its state, one row is in conflict with the three-way choice, and one is waiting.
- **Offline create, edit and sync**: create an entry offline with a client-made id, edit it and an existing one, reload the tab, go online, sync, and read what the stub saw. Playwright sets the browser offline.
- **One runner among several tabs**, with the Web Locks API, and the others following the store.
- **Storage**: that persistent storage can be requested, what a private window does, and whether a phone browser keeps an unvisited site's data (not known here).
- **Export size**: the raw and compressed size of an export of the largest repository the seed and the importer can make, and of a synthetic one ten times that, to put numbers on the cap, on whether names-first is enough, and on whether full refetch behind an ETag is workable.

What would change the decision: a grid that cannot keep focus or keep up is reported as in [§9](#9-ui-layer-rules); an export too large for a phone lowers the cap, makes names-first the only way to a first screen, or moves the delta feed out of "deferred"; storage a phone browser drops makes "available offline" a promise the app cannot keep and changes how it is worded. Findings go into a "What was tried" section here, as in [RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md).

## Slices

Each its own ADR when it lands, on its own short-lived branch off `main`. The ids are those of [RFC 0036](0036-repository-tooling.md)'s index.

| Id | What | Depends on | Touches |
| --- | --- | --- | --- |
| B0 | Spike: the 300-row grid, outbox, conflict row, offline create/edit/sync against a stub export, and export size ([Spikes](#spikes)) | none | bench (throwaway), docs |
| B1 | ADR for `apps/bench`: stack, auth, Pages, `app:bench` label, addendum to ADR 0071 (service worker for Bench only) | B0 | docs |
| B2 | Scaffold, Authgear login and repository picker, label, CI | B1; the maintainer's Authgear client and Pages project | bench |
| W1 | Stat writes bump the entity version and return `previous`; `DELETE` of a direct non-boolean stat value | none | api |
| W2 | Optional client-made ids on the creates Bench queues; the replay rule | none | api |
| W3 | Bulk entity export: cursor pages, compression, per-tenant revision ETag | none | api |
| B3 | Command layer, online-first item editor, explorer, LIVE banner, undo through the outbox | B2, W1 | bench |
| B4 | Offline foundation: per-user IndexedDB, outbox schema version and needs attention, shell-only service worker, sync status, "Out of date" marks, pinning with cap and size | B3, W2, W3 | bench |
| B5 | Conflict review: three-way compare from stored bases, queued deletes "pending, confirm on sync" | B4; RFC 0036 S5 (or its extraction to `packages/repo-ui`); RFC 0041 K9 | bench, docs |
| B6 | Compare grid and bulk stat read | B3; RFC 0041 K7 | bench |
| B7 | Stat vocabulary and formula editors | B3; RFC 0041 K6 | bench |
| B8 | Pictures | B3; RFC 0041 K8 | bench |
| B9 | Structured pack editor | B3, B6 | bench |
| B10 | SVG ancestry graph | B3 | bench |

Not slices yet: a **delta feed with tombstones**, only if the spike or use shows full refetch does not scale; and the **registries** of [§8](#8-room-for-new-kinds), when the first place, clock or calendar kind exists.

## Open questions

- **A refresh token that lasts.** Can Authgear Cloud give Bench's client a long refresh-token lifetime? If it cannot, an editing session away from a connection has a limit, and what happens at it (the store stays, sign in again) is the whole story.
- **Encryption of what is on the device.** Cleared on logout and per user is decided; whether stored text, GM-only text included, should also be encrypted with a key the user must be signed in to hold, is not.
- **First-in-first-out or chains.** Whether the runner stays strictly in the order written, or runs independent entries past a paused one as proposed in [§2](#2-the-command-layer).
- **How the revision of W3 is kept**, and what its cost is under concurrent writers in one repository.
- **Which writes have no version** besides the stat writes, and whether W1 widens to cover them.
- **Whether Bench opens a library's catalog**, now that Authors exist in libraries as well as repositories ([RFC 0040](0040-authors-and-invites.md)). Bench is repository-first; the commands do not care which tenant they write to. Inventory-web stays the place for a library's catalog until this is decided.
- **Duplicate before K4.** Whether Bench builds "duplicate" out of commands (create, copy the stats and notes) in B3, or waits for the server's duplicate.
- **The cap's value and the pin order**, once B0 has numbers.

## Not in scope

- **A native or desktop shell**, for offline or for anything else.
- **Real-time collaboration.** Two authors editing one field is a conflict the three-way compare names, not a merge made live.
- **Offline pictures.** Pictures are online-only in B8.
- **The delta feed.** Deferred as above.
- **Third-party plugins or editors.** The registries are for Lorenzo's own kinds; an extension point for others is not designed here.
- **Background or push sync.** Bench sends while it is open. It does not rely on the browser waking it up.
- **Offline for Library and Studio**, and the publishing, people and release screens, which are [RFC 0036](0036-repository-tooling.md)'s.
- **A shared navigation or app switcher** across the apps.
- **A cross-device outbox.** Each device has its own; the three-way compare is what keeps two devices honest.

## Alternatives considered

- **Lit, React, Svelte or similar.** A framework is the usual answer to a 300-row editable grid and an outbox, and the maintainer's decision is no: Astro is already a compromise, and the cost of a homegrown layer is what the spike measures rather than assumes. A failed spike goes back to the maintainer ([§9](#9-ui-layer-rules)).
- **Astro as many pages, with view transitions.** Simplest to build and in line with the other apps, but the outbox runner, the open edit and the grid would have to survive every change of page; one page with its own router keeps them alive.
- **A desktop shell such as Tauri.** The storage is the same browser storage, and it adds installers, signing and updates for a tool that needs no device feature.
- **One app with three workspaces** (Shelf, Studio and Bench together). One thing to build and one login, but offline constraints and a service worker would apply to screens that are online-only by decision, and the app would be the largest of the three audiences' tools at once. Two apps, as decided.
- **Caching in the service worker.** The browser's own cache is the cheapest offline of all, and an authenticated response in it outlives a logout and cannot be cleared per user. The store owns the data.
- **A server-side change log or CRDT instead of commands and a compare.** Right for live collaboration, which is not in scope, and a large server-side change to every write route for what a per-field compare with a stored base already answers.
- **Full refetch only, with no revision.** Every open of a pinned repository would download all of it. The revision costs a counter and makes "nothing changed" one `304`.
- **A delta feed now.** Exact and small on the wire, and the largest server change here: deletions recorded, triggers on the child tables, a cursor that survives out-of-order commits. Built only if the measurement says it is needed.
- **Recomputing inherited and computed values on the device.** Fewer "Out of date" marks and a second copy of the resolution rules and the evaluator that would drift. A mark that is honest is better than a number that is wrong.
- **Online drafts with no outbox first**, and offline later. It is the fallback if B0 fails, not the plan: every write would be written once against a different shape and again against commands.

## Consequences

- Repositories can be written with no connection, and what was written is safe until it is sent: a change is on the device, shown as such, sent in order, undone from the same list, and never silently merged.
- Bench carries more than a CRUD app does: a store, a runner, a worker, a schema version to keep. The command layer is where that cost is paid once; the editors after it are registry entries.
- The first slices do not wait for the offline foundation, and the offline foundation does not need an editor rewritten, because every write was a command from the first screen.
- The API gains three contracts (W1 to W3), none of them a new kind of data; the largest decision in them is the export's revision, with a cost to measure.
- Inherited and computed values may be marked "Out of date" for as long as the user stays offline after changing what they depend on; that is the price of not computing them twice.
- ADR 0071 gets an addendum, for Bench only, and `docs/guides/labels-milestones-and-metadata.md` a row for `app:bench`.
- New kinds from RFC 0026 and RFC 0028 cost a migration, a registry entry on the server and an editor module on the client, and nothing in the command layer, the store or the review.
- The decision to have no framework is held until a measurement says otherwise; if it does, the maintainer, not the code, decides what changes.
