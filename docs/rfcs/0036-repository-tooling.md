# RFC: Repository tooling — Shelf, Studio and Bench, and the order they are built in

Status: accepted, decided with the maintainer on 2026-10-07: the three workspaces and two apps ([§1](#1-three-workspaces-two-apps)), the rules every slice follows ([§2](#2-rules-every-slice-follows)), the Shelf and Studio screens ([§3](#3-shelf-a-librarys-repositories) and [§4](#4-studio-running-a-repository)), the three small API slices ([§5](#5-small-api-support)), the order of the work ([§6](#6-the-order-of-the-work)), and the decisions listed in [Decided with the maintainer](#decided-with-the-maintainer-2026-10-07). The parts that depend on a spike (the shared review element's extraction, the update badge's exactness) are proposed. Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Rows "Publish, subscribe, update screens" and "Authoring tool" of [v1.0](../../v1.0.md), tracked in [#376](https://github.com/ramsesoriginal/lorenzo/issues/376). This is the umbrella: the topics that are large enough to carry their own decisions are [RFC 0037](0037-releases-and-public-snapshots.md) to [RFC 0041](0041-entity-kinds-and-author-freedom.md), indexed in [§7](#7-what-the-topic-rfcs-own).

## Context

A repository is a tenant of kind `repository`, called a **repository** in Lorenzo's interfaces: a space nobody plays in, whose content libraries copy and then receive updates from ([RFC 0024](0024-repositories.md), [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md) to [0121](../adr/0121-repository-updates-and-re-sync.md); a **library** is a play tenant, per [identity §14.3](../brand/identity.md)). What exists, read from the API and the apps:

- **The command line does all of it.** `lorenzo repo` publishes, invites, copies, checks for updates and applies them ([ADR 0159](../adr/0159-lorenzo-repo-commands.md)). The API under it is complete for one repository at a time.
- **The hub has no screens for it.** account-hub creates a repository, renames it, manages its people and shows "Draft" or "Published *date*" ([ADR 0178](../adr/0178-account-hub-repositories.md)). Publishing, inviting, copying and updating "stay on the CLI until the row is built". A library admin has no way to see what a repository offers, and a repository's owner has no way to see who uses it.
- **Only names are browsable.** A library the repository is granted to can list its entries' names, kinds and parents and its stat groups, and no text ("structure, not text", [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). What a copy would bring in is counts and name clashes, from the copy plan.
- **Publishing is an announcement and reads are live.** `PUT /published` sets a timestamp and notifies the libraries; it freezes nothing. `copy-plan`, `copy`, `updates` and browse read the repository's current rows, so an author's half-finished edit shows up in a library's update check ([ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md): "Publishing is how an author says 'look now'"). There is no version, no release note and no history; the only signal is `published_at` against a library's `synced_at`.
- **A diff speaks in ids.** `GET .../updates` names other rows by their origin id, so a human-readable change needs the names looked up. Descriptions, notes, containment and ownership are copied once and never compared ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).
- **Access is by tenant id.** The owner grants a library by its id, which they have to be told out of band, and revoking sends no notification. There is no way to find a library, and no invite link into one.
- **Authoring has gaps.** A repository's members edit it with the ordinary catalog, stat and note screens ([RFC 0024](0024-repositories.md) A10), but there is no screen for stat vocabulary, computed stats, or prototypes across kinds, stat groups and definitions cannot be renamed, and an entry cannot be created except through its kind's own route. [RFC 0041](0041-entity-kinds-and-author-freedom.md) owns those.
- **Phones are not supported.** The only responsive rule in the shared CSS is the sidebar collapse at 720px.

The v1.0 table has two rows for this: "Publish, subscribe, update screens" and "Authoring tool", both New. "Redesign with shared nav and app switcher" is a third row nearby that this RFC does not touch ([§2](#2-rules-every-slice-follows)).

Three groups of people have a need here. They are listed as needs, not as types of user, because one person is often all three:

- **Library admins** (Owners and Organizers of a library) need to see which repositories their library may use and which it already copies, to know what a copy would bring in and what it would collide with before it happens, to copy with confidence, and to apply later changes without losing their own edits or being surprised. They are often on a phone.
- **Repository owners** need to create and describe a repository, say who works on it and who may publish, see which libraries use it and which repositories it builds on, publish a new version with a label and a note, and see what a library sees before it does.
- **Authors** need to create and edit entries and their stats, parents and text in long sessions, on a laptop or a phone, sometimes without a connection, without being able to publish by accident.

## Decision

### 1. Three workspaces, two apps

| Workspace | For | Where | Navigation label |
| --- | --- | --- | --- |
| **Shelf** | A library admin: the repositories their library copies, and its updates | an area of `apps/account-hub` | "Repositories" |
| **Studio** | A repository's owner: creating, describing, staffing, publishing it | an area of `apps/account-hub` | "My repositories" |
| **Bench** | An author: editing entries in a repository, with offline work | a new app, `apps/bench` ("Lorenzo Bench") | its own header |

Shelf and Studio are names for areas of the hub, not apps. Bench is an app. The names are spoken ones ("check it in Studio"); the labels in the navigation stay descriptive, and a screen never says "Shelf" or "Studio" to someone who has not been told what it is. ADR 0194 (user-facing terminology) records the three names and adds them to [brand §3.3](../brand/identity.md) as names of places, with Bench named "Lorenzo Bench" by the family's "Lorenzo" plus a descriptor pattern.

**Why two apps, not one and not three.** Shelf and Studio are a few screens each, made of forms, lists and an outline, and they need what the hub already owns: the library and repository list, memberships, pictures, the activity log, notifications, `GET /me` capabilities ([ADR 0175](../adr/0175-me-says-what-you-may-create.md)) and the existing "Your repositories" section ([ADR 0178](../adr/0178-account-hub-repositories.md)). A separate app would copy all of that and add a seam between a repository's people and the people who use it. Bench is a different kind of tool: long editing sessions with state that must survive a reload, a grid of many rows, and working offline from the start ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md)). That is the opposite of the hub's page-per-route, query-parameter model, and it gets its own Authgear client and deploy so that a service worker and a local database never touch the hub. A new app costs a `mise.toml`, a CI-graph node, release-please and Dependabot entries, a label and a Cloudflare Pages project ([adding an app](../guides/adding-an-app.md)); for Bench that is the price of the offline requirement and is paid once.

**How they connect.** Studio's repository page has an "Edit entries" link to Bench for that repository, and Bench carries a banner when the repository is published and visible to libraries while you edit it, with a "Publish..." link back to Studio. These are plain links ([§2](#2-rules-every-slice-follows)).

### 2. Rules every slice follows

- **No component framework.** Not Lit, React, Svelte, Preact or similar. The frontends are static Astro ([ADR 0004](../adr/0004-static-astro-frontend.md)) with plain TypeScript, [ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md) says "no component framework" for the hub, and Bench follows the same line: its own small TypeScript (a command layer, a store, a few custom elements written by hand), no runtime dependency that is not already in the repository. Extending `apps/brand`'s CSS is fine.
- **`packages/repo-ui` only when a second consumer needs it.** A shared element lives in the hub until Bench needs the same one; then it is extracted to a proper package under `packages/`, never into `apps/brand` (which is CSS and tokens, [ADR 0098](../adr/0098-branding-css-app-and-package.md)). The first candidate is the review and diff element ([S5](#slices)), wanted by the update inbox and by Bench's conflict view. Bench's spike ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md)) decides whether the extraction is needed at all.
- **The brand guidelines bind every screen.** [Identity §8](../brand/identity.md) for layout, §12.2 for the web-app shell, §15 for accessibility (no meaning carried by hue alone, native elements, a text name on icon-only controls, reduced motion, dense data that stays readable and zoomable), and §18 for any view of provenance or inheritance: one edge grammar, an outline first, a spark only for "canonical", never for navigation.
- **Phone layouts are acceptance criteria.** Every Shelf and Studio slice ships with a single-column layout that works at phone width, targets large enough to press, no hover-only controls, and no side-by-side diff (was, now and yours stack). The shared base for it is [S1](#slices), because today only the sidebar collapse exists.
- **Deep links, not a shared shell.** The apps do not share a navigation bar or an app switcher; that row of v1.0 stays New and is not part of this program. Where one app sends someone to another, it links to a URL read from the build's environment configuration, the way the API URL is today.
- **One Authgear client per app** ([ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md)). Bench gets its own; its refresh-token lifetime is a requirement of offline work ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md)).
- **Words come from ADR 0194.** A tenant is a library or a repository, never "tenant" on screen; Owner, Organizer, Author; "inherits from" and "built on"; "Invite a library", "Copy", "Update", "release". New screens use the new words from their first slice; the old surfaces are swept afterwards ([G2](#slices)), so for a time the apps disagree, which is accepted.
- **Each slice is verified in a real browser against the real API.** The hub's real-API browser tests ([ADR 0136](../adr/0136-account-hub-client-and-tenant-slug.md)) run locally and are not a CI job; inventory-web's do ([ADR 0114](../adr/0114-inventory-web-end-to-end-tests.md), the `inventory-web-e2e` suite of `.github/ci-graph.toml`). [S2](#slices) brings the hub's real-API tests into CI in the same way, so every later Shelf and Studio slice is tested where it is merged.

### 3. Shelf: a library's repositories

Shelf is where a library admin (an Owner or Organizer; copying and updating are theirs, and stopping updates is the Owner's alone) sees what the library may use. It is a page per library under the label "Repositories". Each screen below is built on the API as it is, unless a slice in [§5](#5-small-api-support) is named.

**The list.** One card per repository the library has an invitation to or has copied, with its picture, name, a line of its description, and a state:

- **Not copied yet**: invited, nothing copied.
- **Copied**: the library has it and nothing newer is known.
- **Update announced**: the repository was published after the library's last update. This is what `published_at` against `synced_at` can say, so it is worded as "announced", not as a count; a count needs the updates check, which runs per repository, and whether a badge for a whole library can be exact is a spike result ([Spikes](#spikes)).
- **No longer offered**: the invitation is gone. The copy stays and so do its contents; there will be no more updates.

**A repository's page.** Its name, picture and description (rendered LorenzoScript), what is inside as counts (entries, stat groups, stats, notes, and one sentence for attachments since there is no noun for them in the interface), and a browsable list of names: entries with their kinds and parents, stat groups with their stats. It says plainly that only names show until the library copies it (the showcase and public text preview of [RFC 0038](0038-public-repositories-and-discovery.md) widen that). Under that, the library's history with it: when it was copied, when last updated, and what it brought, from `contributed`. Actions: **Copy**, **Check first**, **Update**, and **Stop updates from this repository**, the last one only for an Owner and worded as what it does ("the copies stay yours; you will not get later updates unless you are invited again").

**Built on, as an outline.** A repository can be built on other repositories, which the library must also be invited to, one by one: invitations are not transitive ([RFC 0024](0024-repositories.md) A8). The page shows the chain as an indented, keyboard-navigable outline in the copy plan's order, each repository with its state: **Copied**, **Invited, not copied**, **Not invited**, **Not published**. The missing link says what to do ("Ask the owner of *Core* to invite your library"). Edges follow [brand §18](../brand/identity.md): a solid line for built-on, a muted node for a repository the library cannot read. An SVG graph comes later if the outline proves too small; chains are a handful of nodes. The plan as it is shows `granted` and `published` for each step; showing a repository the library has *no* invitation to needs [A2](#5-small-api-support), so [S2](#slices) first ships the outline for what the plan returns and A2 completes it.

**The copy wizard.** Four steps, one primary button each:

1. **Check first.** Runs the plan: what would be copied, in counts, and what it would clash with. A sentence states the limits before anything else: **a copy cannot be undone as a whole** (a library can only remove what it copied piece by piece, or copy again with *purge*, which also removes its own additions to those entries, with the count shown), **a library works with one game system at a time for now** ([RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) §9), **notes the repository marks GM only are copied along and, until [RFC 0024](0024-repositories.md) A9 is closed, only the library's Owners and Organizers can read them, not a campaign's GM**, and that there is no way to remove a game system from a library once copied ([ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)).
2. **Name clashes.** One card per clash, in words: "Your library already has a stat called *Weight*". The three choices are **Keep both**, **Use the existing one** and **Leave it out** (the API's rename, merge and skip), with the recommended one marked and a "do what is recommended for all" at the top. On a phone one clash fills the screen.
3. **Review.** The dry-run result as a receipt: "would add 309 entries, use 2 existing stats, keep both of 1; nothing has changed yet", with the full list folded away.
4. **Done.** What was copied, and a link to it. "Copy again" is in the page's overflow menu, with the `also_removed` counts of a dry run in front of the *purge* choice.

Errors that the API reports as a conflict (an invitation or a publication missing, a formula cycle) are explained at the outline node or the step where they arise, not as a status line.

**The update inbox.** One screen per library, a row per repository ordered by what needs the library: "Core equipment: 4 changed, 12 new, 1 removed upstream, 2 conflicts". Inside a repository, rows are grouped **New**, **Changed**, **Removed upstream** and **Conflict**, and the page gives:

- **Human-language diffs.** A changed field shows its label, what it was when the library last updated, what it is upstream now, and, if the library changed it too, what the library has: "Was / Now / Yours", stacked on a phone. Values that are ids show names. [S4](#slices) resolves them in the browser from the browse reads; [A1](#5-small-api-support) returns display values from the API so that a row about something deleted upstream still reads correctly.
- **Row by row, and all clean at once.** Each row can be applied, skipped or, for a removed one, detached. **Apply all clean** applies every row the library has no edit in, and **never includes** a row [RFC 0037](0037-releases-and-public-snapshots.md) marks as breaking, an edit made since the last release, or an attachment (a parent a bridge adds to entries the library already holds): each of those needs its own decision. Updates **never apply by themselves**.
- **Released versus edited.** A repository's rows are marked as part of its latest release or edited since it, when [RFC 0037](0037-releases-and-public-snapshots.md) provides the mark; until then the inbox shows what the API returns.
- **What is not compared.** Descriptions and notes, containment and ownership are copied once and never updated ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)). The inbox says so in one sentence at the top, so that a fixed typo that does not arrive is not a surprise.
- **Revoked and unpublished.** A repository that is no longer offered stays in the list with that state and says why updates stopped, since revoking sends no message today ([A3](#5-small-api-support)).
- **Players see nothing of this.** The inbox says that applying changes what players see, once, where it matters.

Notifications about a published repository deep-link into the inbox for that repository.

### 4. Studio: running a repository

Studio is where a repository's owner works, under the label "My repositories". A repository's page has these tabs: **Overview**, **Profile**, **People**, **Built on**, **Releases**, **Libraries using it**. It is built on the API as it is, with each slice naming what it waits for.

- **Create** ([T1](#slices)). The existing create form, shown only when `GET /me` says the account may create one; **creating a repository stays behind the `tenant-creator` platform role** ([ADR 0175](../adr/0175-me-says-what-you-may-create.md)). Name, link name (slug) and description; the repository opens on its Overview.
- **Overview.** State (Draft or Published, with the latest release label once [RFC 0037](0037-releases-and-public-snapshots.md) exists), the number of libraries using it, and, on a private repository that is published, a persistent **LIVE banner**: "Libraries that copy from this repository see your edits when they next check for updates." That sentence is true today ([ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)) and stays true for private repositories after the work in the other RFCs; a public repository reads from its latest release instead ([RFC 0037](0037-releases-and-public-snapshots.md)).
- **Profile** ([T5](#slices)). Summary, cover, licence, credits, tags, system. The fields, who reads them and when are [RFC 0038](0038-public-repositories-and-discovery.md)'s; the screen is Studio's.
- **People** ([T1](#slices)). Everyone with a role on the repository, with the role's meaning written next to it. An **Owner** has full control: publishes, invites libraries, manages people, deletes. An **Organizer** edits content and cannot publish or hand out access. An **Author** edits content only: cannot publish, invite, manage people or delete structure. The Author role itself is [RFC 0040](0040-authors-and-invites.md)'s ([U1](#slices)); until it exists, People shows Owner and Organizer and says an Organizer is the one who edits. People are added directly (as today) or, with RFC 0040, by an author invite link.
- **Built on** ([T2](#slices)). The repositories this one copies from: when last updated, how many updates are waiting, **Review updates** (the same screens as Shelf, since a repository is a tenant that copies from another, [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), and **Add**, which copies another repository into this one with the same wizard. The dependency outline of [§3](#3-shelf-a-librarys-repositories) shows this repository and, below, the repositories built on it.
- **Libraries using it** ([T2](#slices)). A table of libraries with an invitation or a copy: invited on, copied or not, last updated, and (with [RFC 0037](0037-releases-and-public-snapshots.md)) which release. **Invite a library** by its id, kept for people who have it, and by invite link when [RFC 0040](0040-authors-and-invites.md) has built them; **Stop inviting** says what it does (copies stay) and notifies the library ([A3](#5-small-api-support)). For a public repository the table shows counts, not library names ([RFC 0038](0038-public-repositories-and-discovery.md)).
- **Releases** ([T4](#slices)). The list of releases and the composer: a free-text label, a "breaking" flag, notes, and a summary of what changed since the last release. Owned by [RFC 0037](0037-releases-and-public-snapshots.md).
- **The guarded publish dialog** ([T3](#slices)). Publishing and unpublishing go through a dialog that says what will happen before it does: how many libraries will be told; whether a repository this one is built on is not published (a copy of this repository is refused while any step is unpublished, [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)); that notes marked GM only travel with a copy; and, on unpublish, that libraries lose browse, copy and updates while their copies stay. Before the release composer exists the dialog carries no label; T4 replaces its body.
- **View as a subscriber** ([T6](#slices)). A button that creates a scratch **Test library** the owner owns, invites it to this repository, and opens Shelf for it, so the owner sees exactly what a library admin sees, with the same screens and no second read path. "Reset" copies again with *purge* into the Test library. Nothing is added to the API.
- **The visibility switch** ([T7](#slices)). Private or public, with the warnings and the rules for a switch from [RFC 0037](0037-releases-and-public-snapshots.md) and [RFC 0038](0038-public-repositories-and-discovery.md): the count of libraries affected, built-on repositories that must be public first, and that a first public release is made with the switch.

### 5. Small API support

Three slices belong to this RFC because Shelf and Studio need them and no topic RFC does. Each is additive or a fix, each is its own ADR, and none is a reason for a Shelf or Studio slice to wait for the first version of its screen.

- **A1. Display values in update diffs.** `FieldChangeOut` carries ids in `base`, `upstream`, `local`, `added` and `removed`. The response gains names (a side map of id to name for every id it mentions, or a name beside each value), so a client does not need the browse reads and a row about something deleted upstream still reads. The client-side resolution of S4 is the fallback it replaces.
- **A2. The dependencies endpoint.** For a repository the caller may read, its built-on repositories as name, slug and the asking library's state (invited, copied, published), never contents. It is what makes the outline complete for a repository the library holds no invitation to. Whether an owner may hide the names of built-on repositories that belong to someone else is an [open question](#open-questions).
- **A3. A revoke notification.** `DELETE /subscribers/{id}` removes the invitation and tells no one. It sends the library's members a notification, in the pattern `PUT /subscribers/{id}` already uses.

### 6. The order of the work

Order and dependencies only, no schedule. The work is in waves; a wave starts when what it needs is merged, and slices inside a wave are independent unless [Slices](#slices) says otherwise.

- **W0.** The terminology branch ([G1](#slices)) and this RFC's branch; the spikes ([Spikes](#spikes)); the phone base ([S1](#slices)); Bench's Authgear client and Pages project, which the maintainer sets up.
- **W1.** Shelf's first screens on the existing API ([S2](#slices), [S3](#slices), [S4](#slices)) with [A1](#slices) to [A3](#slices); the API slices Bench's offline work needs ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md) W1 to W3) and the first author-freedom routes on draft repositories ([RFC 0041](0041-entity-kinds-and-author-freedom.md) K2, K3); Bench's ADR, scaffold and first online editor (B1 to B3).
- **W2.** Studio's first cut ([T1](#slices) to [T3](#slices)); then the release ledger ([RFC 0037](0037-releases-and-public-snapshots.md) R3, R4) and the release composer ([T4](#slices)); the visibility and profile columns ([RFC 0038](0038-public-repositories-and-discovery.md) D1); the Author role and invite links ([RFC 0040](0040-authors-and-invites.md) U1 to U3); the terminology sweep per surface ([G2](#slices)); Bench's offline foundation and conflict review (B4, B5); the shared review element ([S5](#slices)); the copyable-table registry ([RFC 0041](0041-entity-kinds-and-author-freedom.md) K1) before the routes that need it.
- **W3.** The rest of author freedom (K4 to K9) and Bench's grid, vocabulary and picture work (B6 to B9); the profile screens ([T5](#slices)) and view-as-subscriber ([T6](#slices)).
- **W4, gated by the release round-trip spike and the release document slices (R5 to R8).** Public reads, discovery and the pre-launch gates ([RFC 0038](0038-public-repositories-and-discovery.md) D2 to D6), Discover and the storefront ([S6](#slices)), the visibility switch ([T7](#slices)). The maintainer's edge rate-limit work (D7) is done before launch; the build does not need it.

**Hard constraints.** Migrations are serial. Regenerating `openapi.json` and `schema.d.ts` is serial. RFC and ADR numbers are serial, and a new number is claimed early. Discovery does not start until the release round-trip spike has passed.

**Branches.** Each slice is its own short-lived branch off `main`, with its own ADR, issue and PR. This deliberately departs from [AGENTS.md](../../AGENTS.md)'s pattern of a feature branch with sub-branches: these slices are independently shippable behind existing navigation, `main` stays releasable throughout, and there is no long-lived branch to drift or to collide on numbers. Spikes run on throwaway branches that are not merged, and what they found is written back into the RFC that asked for them.

### 7. What the topic RFCs own

| RFC | Owns |
| --- | --- |
| [0037, releases and public snapshots](0037-releases-and-public-snapshots.md) | The release ledger (label, notes, breaking flag), the digest that marks rows released or edited, the release document for public repositories, the read switch, retention and rollback, the rules for switching a repository between private and public |
| [0038, public repositories and discovery](0038-public-repositories-and-discovery.md) | Visibility and profile, public reads for logged-in users, copying a public repository (which invites the library as `lorenzo repo offer` does), Discover and the storefront, showcase preview, the gates before launch (operator delist, publish cooldown, quotas, privacy of libraries, publisher identity, picture access) |
| [0039, Bench](0039-bench-authoring-offline-and-extensibility.md) | The authoring app: stack, auth, command layer, offline store and outbox, sync, stale markers, conflict review, pinned repositories, device security, the sync API, extension seams |
| [0040, authors and invites](0040-authors-and-invites.md) | The Author role in repositories and libraries and what it may do, one invite-token model for campaigns, roles and libraries, pasting a code, the People screens' data, a campaign's GM title |
| [0041, entity kinds and author freedom](0041-entity-kinds-and-author-freedom.md) | Kinds as marker tables, creating entries with kinds, parents across kinds, duplicate and new-from-parent, filters and ordering, rename-only stat PATCH, bulk effective-stat read, pictures, warning on delete with a count, RFC 0018's status |

This RFC owns Shelf, Studio, the terminology sweep and the three API slices of [§5](#5-small-api-support).

### 8. Why it is shaped this way

These were decided while shaping the program, and each has a reason that is easier to keep than to rediscover.

- **Two apps, not one app with a mode.** A mode switch puts two audiences' controls on every screen and hides the difference in permissions; Shelf and Studio share data and people, Bench shares neither the page model nor the lifecycle. Three apps, with Shelf on its own, was rejected because a repository that builds on another needs exactly Shelf's screens inside Studio.
- **No framework, and no shared package up front.** A component library earns its place when two screens share a component; nothing here does until Bench exists. Extracting `repo-ui` first would block the first deliverable on a package nobody else uses yet, and a framework would be a new dependency to maintain for a few screens of forms and lists. What Bench needs (a command layer, a small store, an outbox) is written for Bench, and is tested by the spike before the app is scaffolded.
- **Live reads plus a release ledger, not drafts.** The behaviour libraries rely on today is that nothing changes in their library until they say so; live reads do not break that. They do show half-finished work in the inbox and cannot reproduce "version 1.2". A ledger (label, notes, breaking flag, a digest of what the engine compares) fixes the honesty of "publish" without touching the copy and update engines. Releases that cannot be changed afterwards are needed only where strangers read, which is why snapshots are for public repositories alone, and private repositories stay live with the LIVE banner ([RFC 0037](0037-releases-and-public-snapshots.md)).
- **A digest, not `updated_at`, marks released versus edited.** The compared tables do not all have `updated_at` (`entity_prototype`, `entity_stat_group` and `entity_slug` have none) and rows are deleted outright, so a maximum timestamp misses edits; hashes of the compared fields do not.
- **No draft flag on an entry.** A second visibility model on a single entry would have to be honoured by the repository read policy on every content table, and by copy, updates and browse, and a forgotten flag would leak a draft. The private, never-invited repository is already a draft, and a release is the only thing a public repository's readers see.
- **No staging repository made by copying.** A copy brings only a repository's own rows and copies text once, so a staging repository would drift from the real one and never receive later edits.
- **Invite links, not search by name.** Searching libraries by slug or name lets anyone enumerate them and gives an owner a way to push notifications at libraries that never asked. An invite link is created by the owner, expires, can be revoked and, for a library, is a pasteable code ([RFC 0040](0040-authors-and-invites.md)). Granting by id stays for people who have it, and the command line.
- **A release is a document, not a cloned tenant.** `entity.id` is the table's own primary key, so a cloned tenant cannot keep its entries' ids and every copy's link to its origin would break. A stored document with the ids kept is read by the same engines through `load_content()` ([RFC 0037](0037-releases-and-public-snapshots.md)). It is gated on a spike that proves the document reproduces the content exactly.
- **View as subscriber through a Test library.** It reuses Shelf and the ordinary read path, so what the owner sees is what a library sees by construction, and nothing is added to the API.
- **An outline before a graph.** Dependency chains are a few nodes long and a keyboard-navigable outline is accessible by default; the inheritance graph of a large repository is Bench's, and the brand grammar of [§18](../brand/identity.md) applies to both.
- **Apply all clean excludes breaking rows and attachments.** An attachment changes the stats of entries a library already holds, and a breaking row changes what a library built on. A bulk button that took them would make "clean" a lie.
- **Phone first for Shelf.** A library admin checks "did the update arrive before the session" on a phone at the table. The heavy flows (a copy with many clashes) work on a phone and are designed for a desk.
- **Per-slice branches.** See [§6](#6-the-order-of-the-work).

## Decided with the maintainer (2026-10-07)

- **Two apps.** `apps/account-hub` hosts Shelf and Studio, a new `apps/bench` hosts Bench. The names are Shelf, Studio and Bench; the navigation labels stay descriptive ("Repositories", "My repositories").
- **No Lit, React, Svelte or similar.** Own small TypeScript, extending `apps/brand`'s CSS where needed. A `repo-ui` package is a proper package under `packages/`, not in `apps/brand`, and is extracted only when a second consumer (Bench) needs it, after a spike on a 300-row editable grid.
- **No shared navigation or app switcher** in this program. Plain deep links, with the URLs in environment configuration. One Authgear client per app.
- **Shelf and Studio on the existing API first**, with phone layouts as acceptance criteria and the brand guidelines binding.
- **Repository creation stays gated** by the `tenant-creator` platform role.
- **Releases** have a free-text label and a "breaking" flag. Release snapshots exist for **public repositories only**; private repositories read live, with a LIVE banner. Public discovery is **in v1.0**, opt-in per repository, for logged-in users, with the preview defaulting to a showcase; copying a public repository invites the library as `lorenzo repo offer` does today; a licence is optional; takedowns are a future matter, with a minimal operator delist before discovery launches ([RFC 0037](0037-releases-and-public-snapshots.md), [RFC 0038](0038-public-repositories-and-discovery.md)).
- **An Author role** in repository and play tenants, who edits content only. Authors are added directly or by invite link; an invite link never grants Owner, and an invite code is the pasted token ([RFC 0040](0040-authors-and-invites.md)).
- **Deleting something libraries hold warns with a count and does not block.** Stat PATCH is rename-only and amends [ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md) ([RFC 0041](0041-entity-kinds-and-author-freedom.md)). Kinds are marker tables; places, clocks and calendars arrive with [RFC 0026](0026-world-model-axes-and-address.md) and [RFC 0028](0028-time-causality-and-calendars.md).
- **Offline in Bench from the start**, on a command layer with a local cache and outbox; the first Bench is online-capable on that layer; stale markers on inherited and computed values; a per-field three-way compare on conflicts; the repositories you author are available offline; Shelf and Studio are online only; local data is kept per user and cleared on logout ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md)).
- **The words** of the glossary, recorded as ADR 0194 on its own branch, first; new screens use them from the start and the sweep follows ([G2](#slices)).
- **API stability is not a constraint** while Lorenzo is in early development; a break is made on purpose and recorded.
- **One short-lived branch per slice off `main`**, a deliberate departure from AGENTS.md's feature-branch pattern; spikes on throwaway branches with findings written back into the RFCs.
- **Order, not estimates.** The program is ordered by dependency; no durations or sizes are recorded.

## Slices

Each its own ADR when it lands, on its own branch. "Touches" names the part of the system. Ids match the tracking issue's checklist; the topic RFCs' slice ids (R, D, B, W, U, K) are in their own documents.

| Id | What | Depends on | Touches |
| --- | --- | --- | --- |
| G1 | Terminology: the glossary into identity §14.3, product names into §3.3, ADR 0194 and its sweep slices | none | docs, brand |
| S1 | Phone base: shared single-column layout rules, target sizes and an outline pattern in the brand CSS | none | brand |
| S2 | Shelf: the repositories list, a repository's page with counts and names, and the built-on outline (from the plan); brings the hub's real-API tests into CI | S1, G1 | hub |
| S3 | Shelf: the copy wizard (check first, name clashes, review, done) with the limits stated in the flow | S2 | hub |
| S4 | Shelf: the update inbox with human-language diffs, row by row and apply all clean, names resolved in the browser | S2 | hub |
| A1 | Display values (names) in `updates` responses | none | api |
| A2 | Dependencies endpoint: built-on repositories as name, slug and the library's state, never contents | none | api |
| A3 | A notification when an invitation is revoked | none | api |
| T1 | Studio: create a repository, the People tab with labelled roles | S1, G1 | hub |
| T2 | Studio: libraries using it (invite by id, stop inviting), built on (review updates, add), the activity log | T1, S3, S4, A2, A3 | hub |
| T3 | Studio: the guarded publish and unpublish dialog | T2 | hub |
| T4 | Studio: the release composer | T3, [RFC 0037](0037-releases-and-public-snapshots.md) R3 and R4 | hub |
| T5 | Studio: the profile screens | T1, [RFC 0038](0038-public-repositories-and-discovery.md) D1 | hub |
| T6 | Studio: view as a subscriber through a scratch Test library | T2, S4 | hub |
| T7 | Studio: the visibility switch and the warnings for a switch | T5, [RFC 0037](0037-releases-and-public-snapshots.md) R8, [RFC 0038](0038-public-repositories-and-discovery.md) D5 | hub, api |
| S5 | The review and diff element shared by the inbox and the conflict view; extracted to `packages/repo-ui` only if Bench needs it | S4, [RFC 0039](0039-bench-authoring-offline-and-extensibility.md) B5 | hub, bench |
| S6 | Shelf: Discover and the storefront | S2, [RFC 0037](0037-releases-and-public-snapshots.md) R6, [RFC 0038](0038-public-repositories-and-discovery.md) D2 to D4 | hub |
| G2 | The terminology sweep, one slice per surface: hub, inventory-web, loot-bot, CLI, API messages | G1 | hub, inventory-web, bot, cli, api |

## Spikes

Run on throwaway branches; the finding is written back into the RFC that asked for it. The spikes themselves are described where their subject lives; these are the ones whose result changes a decision in this RFC.

- **Scale of the updates check and the copy plan** ([RFC 0037](0037-releases-and-public-snapshots.md) R2). Whole-repository work at several thousand and at twenty thousand entries. If the updates check for one repository is too slow to run for every repository on a list, the Shelf list keeps the "Update announced" state from `published_at` and the count appears only inside a repository; if it is fast enough, a per-library summary and a badge are added.
- **The 300-row editable grid with an outbox and a conflict row** ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md) B0). If a hand-written grid and conflict row are workable without a framework, S5 is extracted to `packages/repo-ui` only when Bench actually wants the diff element; if they are not, the app's scope and this RFC's no-framework rule are revisited before Bench is scaffolded.
- **The release round-trip** ([RFC 0037](0037-releases-and-public-snapshots.md) R1). Does a serialised release document reproduce the content exactly? A failure does not change Shelf and Studio, but it blocks W4, so [S6](#slices) and [T7](#slices) wait.

## Open questions

- **Hiding built-on names.** A2 returns the names of built-on repositories to a library that has no invitation to them. Whether an owner may mask a name that belongs to someone else's repository, and what the library then sees, is A2's to decide.
- **A system tag.** Shelf says "one game system at a time" as a sentence. Whether, once a repository's profile carries a system, the wizard warns or blocks when a library already uses another is decided with [RFC 0038](0038-public-repositories-and-discovery.md)'s profile.
- **Bench next to inventory-web.** inventory-web already edits items in a repository's catalog. Whether Bench replaces those screens for repositories or sits beside them, and how Studio's "Edit entries" link chooses, is [RFC 0039](0039-bench-authoring-offline-and-extensibility.md)'s.
- **Who may copy and update once there is an Author.** Today Owners and Organizers of a library do. The matrix for the Author role is [RFC 0040](0040-authors-and-invites.md)'s.
- **A line in AGENTS.md.** Whether the per-slice branch convention is written into AGENTS.md, or stays recorded here and in the first slice's ADR.

## Not in scope

- **A shared navigation bar and app switcher.** The v1.0 row stays as it is.
- **A native mobile or desktop app.** Shelf and Studio are responsive web, Bench is a web app that works offline, and the Discord bot is the at-the-table surface for in-session actions. A manifest for installing a web app is a later, cheap addition.
- **Partial copy, bundles and per-kind include filters.** A copy is all of a repository and its dependencies; a repository that is too big is split. A split advisor is help text, not a tool.
- **Undoing a copy.** There is no un-copy; it is named as a limit in the flow.
- **Automatic updates,** version ranges and pinning to a release for private repositories.
- **Ratings, comments, forks and pull requests,** a marketplace, payments, and real-time collaboration.
- **An SVG graph of ancestry** in Shelf or Studio; Bench may draw one later ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md)).
- **Text comparison of descriptions and notes in updates.** They stay copied once.
- **Retiring or deprecating a repository** (a deprecated state, a successor): [RFC 0038](0038-public-repositories-and-discovery.md). Deleting a repository stays as [ADR 0184](../adr/0184-deleting-a-tenant.md) has it.

## Alternatives considered

- **One app for everything.** One header and one login, and no seam between the audiences. But authoring needs a long-lived client state, a local database and a service worker, none of which belong in a page-per-route hub, and a single bundle would carry them to everyone. Two apps keep the hub light.
- **Everything in the hub, authoring included.** The hub's model (static pages with query parameters, a small stale-while-revalidate cache) does not carry an editing session that must survive a lost connection. Offline editing is a decided requirement.
- **Lit, React, Svelte or Preact.** A framework would help the editing grid most, and the grid is the one place a hand-written approach is untested; the spike decides whether that holds. For Shelf and Studio the existing template-and-renderer pattern is enough, and a framework would be a second way to build the same screens.
- **A native or desktop app.** The needs are forms, lists and editing. A web app installs, works on phone and laptop, and works offline with a service worker. Native adds stores and a second codebase for no hardware need.
- **An entity-level draft flag.** Discussed in [§8](#8-why-it-is-shaped-this-way): a second visibility model on a single entry, honoured on every read path.
- **A staging repository made by copying.** Also in [§8](#8-why-it-is-shaped-this-way): it drifts and never receives text edits.
- **Snapshotting by cloning the repository into a hidden tenant.** Ids cannot be kept, so copies' links to their origin would orphan, and every read site would need an id map. A serialised document keeps the ids ([RFC 0037](0037-releases-and-public-snapshots.md)).
- **Snapshots for every repository.** Private repositories have a small, known audience that already trusts the owner; storing and migrating a document for each of them costs more than the LIVE banner and the ledger.
- **Search for libraries by name to invite them.** Enumeration and notification spam, as in [§8](#8-why-it-is-shaped-this-way).

## Consequences

- A library admin can browse, copy and update from the hub on a phone, and the command line is no longer required for any of it. The limits that cost people trust (no undo, one system, GM-only text, descriptions not updated) are said where they matter.
- A repository owner sees who uses a repository and what a library sees, and publishes through a dialog that names the consequences. The LIVE banner makes the live-read behaviour visible instead of surprising.
- The hub grows two areas without a new app, and the program adds exactly one app, `apps/bench`, with a new `app:bench` label and its own deploy, Authgear client and CI-graph node.
- The three small API slices change `apps/api` additively (names in a response, a new read, a notification) and are the only API work this RFC owns; the rest is in the topic RFCs.
- For a time the apps use different words for the same thing, until the sweep ([G2](#slices)) reaches each surface.
- The per-slice branch model means more, smaller PRs and one ADR per slice; migrations and generated-schema changes must be merged in order, which the waves are arranged around.
- No decision here is taken from the API's existing behaviour except where the Context says it is read from the code; the screens described are built to the API as it is, and every change to the API is its own slice.
