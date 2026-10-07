# RFC: Authors and invites — an Author role, and invite links for libraries and roles

Status: accepted, decided with the maintainer on 2026-10-07: an **Author** role in repositories and libraries alike (it edits content and cannot publish, invite, manage people or delete structure), invite links that grant a role in a library or repository and never grant Owner, single-use short-lived defaults for them as for [ADR 0177](../adr/0177-gm-invite-links.md)'s GM link, the invite code being the pasted token, the names Owner, Organizer and Author with **Admin** as the collective noun for the first two ([ADR 0194](../adr/0194-user-facing-terminology.md)), and the GM's title chosen per campaign; and, in the capability matrix, that an Author may delete an entry nobody inherits from and reads every note on the entries in reach (GM-only included), that only an Owner mints invite links, the proposed link lifetimes, and the rename of the invite table to `invite`. The rest of the capability matrix in [§1](#1-the-author-role) and the wording in [§3](#3-the-people-screen) are proposed. Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Rows "Tenant-role invite links" and "Authoring tool" of [v1.0](../../v1.0.md). Part of [RFC 0036](0036-repository-tooling.md); the library-access link is how a private repository is shared before [RFC 0038](0038-public-repositories-and-discovery.md)'s public ones exist.

Throughout, **library** and **repository** are the user-facing names for a tenant of kind `play` and of kind `repository`; the code, the API and the tables say tenant, and the role values are `owner`, `orga` and (new) `author`. A person sees Owner, Organizer and Author, never `orga` (ADR 0194).

## Context

**Two roles, both administrators.** A membership has one of two roles, `OWNER` and `ORGA` ([ADR 0010](../adr/0010-user-tenant-membership-model.md), [ADR 0022](../adr/0022-user-tenant-membership.md)). The code treats them as one set, "tenant admin" (`is_tenant_admin` in `campaign_access.py`), and says so in several places that this RFC has to revisit: `routers/activity_log.py`, `routers/knowledge.py`, `routers/campaigns.py` and `change_feed.py` each rely on "every `MembershipRole` is administrative", and `tests/test_activity_log_access.py` carries a tripwire, `set(MembershipRole) == {OWNER, ORGA}`, that is written to fail on the day a third value is added.

**What each can do today.** Only an Owner may publish, unpublish, grant and revoke a repository, remove a grant, delete a tenant, and invite, change or remove memberships ([ADR 0036](../adr/0036-user-player-character-crud-api.md), [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md), [ADR 0184](../adr/0184-deleting-a-tenant.md)). An Organizer has every other route that asks only for "a membership" (`get_tenant_context`): edit and **delete** items, add and delete stat groups, definitions and enum values (while unused, [ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)), rename the tenant, upload its picture, send notifications to everyone in it, create and delete campaigns, copy a repository and apply its updates. Seventeen router modules mention `get_tenant_context`; the audit in [§1](#1-the-author-role) goes through them. In a repository the Organizer is the author and the Owner the publisher, which is a role split the code has by accident, and an Organizer who can delete a stat group that subscribers use, or rename the repository, is not an author in any careful sense.

**What is checked where, found by reading the code.**

- `MembershipRole` is used in three places that decide anything: `campaign_access.py` (`is_tenant_orga`, `is_tenant_admin`, `is_tenant_owner`), `routers/tenants.py` (the membership routes, the last-Owner guard, tenant creation) and `routers/users.py` (the administered-tenants list behind `GET /me/managed`, and the sole-Owner check on account deletion). The role is also a closed `Literal["owner", "orga"]` in `schemas/tenants.py` and `schemas/managed.py`, and `TenantRole` adds `"participant"`.
- `can_manage_any_campaign_in_tenant` is a Python function, not SQL. It returns true for an admin, or for anyone holding a campaign GM grant. It is the fallback in `routers/entities.py`, `entity_stats.py` and `item_instances.py` for an entity nobody owns, which is how an Organizer reaches a catalog prototype or any entry of a repository (a repository has no campaigns and no GMs). **An Author would fail every one of those checks**, so the role needs its own predicate, not just an enum value.
- No row-level-security policy and no SQL function reads `membership.role`: the `membership` policy admits a user's own rows next to the tenant's (the `GET /me` migration) and the one repository function, `repository_read_tenant_id()`, reads grants and `published_at`. The migration is an enum value and nothing in the database follows from it.
- The enum is a native Postgres type, `membership_role`. `ADD VALUE` runs inside a migration's transaction on the PostgreSQL 17 the project's compose file uses (the stat-type migration for `enum` does it), but the new value cannot be used until that transaction commits.
- Several clients read the role: account-hub (`MembershipAdmin`, `format.ts`), loot-bot (`format-whoami.ts`, which prints `Orga`), inventory-web (`me.ts`, where "any membership" means "may see the whole catalog and search beings") and the CLI's generated models.

**Adding people.** A person is added by exact lookup of an email or a nickname ([ADR 0055](../adr/0055-user-lookup-by-email-or-nickname.md)) and then `POST /tenants/{id}/memberships`, or several at once ([ADR 0062](../adr/0062-bulk-invite-to-tenant.md)). Both need the other person to have an account already. The membership notification says "You now have `orga` access" and the removal text says "tenant-wide membership", which is the raw value and a technical word.

**Invite links, today, are campaign-only.** `campaign_invite` holds a hashed 256-bit token, a required expiry, an optional use cap, a use counter and `revoked_at`; a link makes a player ([ADR 0092](../adr/0092-campaign-invite-links.md), hub side in [ADR 0171](../adr/0171-account-hub-campaign-invite-links.md)), or, as a single-use link of at most seven days, a GM ([ADR 0177](../adr/0177-gm-invite-links.md)). The token is kept out of spans and logs by a tested redaction, the edge rate-limit rule is the maintainer's pre-launch task ([operations note](../operations/invite-link-rate-limiting.md)), and account-hub's join page takes "Invite link or code": a link carries the token in the fragment, and pasting the bare token works. ADR 0092 and ADR 0177 each left "tenant-role invite links" out of scope as a different, higher-privilege thing; this is that thing. The table is on `repository_access`'s excluded list ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)), so it is never repository content.

**Sharing a repository today needs an id.** A grant is `PUT /tenants/{id}/subscribers/{subscriber_tenant_id}`: the Owner of a repository must be told the library's id out of band. [RFC 0036](0036-repository-tooling.md) wants people to share a private repository without ids, and [RFC 0038](0038-public-repositories-and-discovery.md) adds a `source` to each grant (`invited` or `public`); a link the Owner sends is how a grant becomes `invited` without the Owner knowing the id.

## Decision

### 1. The Author role

**A third membership role, `AUTHOR` (`author`), in repositories and libraries.** One enum value serves both, because a membership has a single role column and a tenant's kind never changes. The name in every interface is **Author**; **Admin** is the collective noun for Owner or Organizer ("library admins"), never a role and never "Administrator" (ADR 0194). An Author is not an admin.

**What it means.** An Author edits content and can do nothing that changes who has access, what is published, or what the structure is. The matrix is the proposal; rows marked decided are the maintainer's.

| Capability | Owner | Organizer | Author |
| --- | --- | --- | --- |
| Create and edit entries: names, descriptions, notes, stat values, parents, formulas, link names, pictures | yes | yes | yes |
| Add stat groups, stat definitions and enum values; rename them once [RFC 0041](0041-entity-kinds-and-author-freedom.md) allows it (proposed: additive and non-destructive) | yes | yes | yes |
| Delete an entry that no other entry inherits from (proposed) | yes | yes | yes |
| Delete an entry that other entries inherit from, with the subscriber warning of [RFC 0041](0041-entity-kinds-and-author-freedom.md) (proposed) | yes | yes | no |
| Delete a stat group, definition or enum value (decided: an Author cannot delete structure) | yes | yes | no |
| Rename the repository or library, change its description, link name and picture (proposed) | yes | yes | no |
| Copy a repository and apply its updates; browse and run a dry run (proposed: the copy brings in stat groups, so only the copy is an admin act) | yes | yes | browse and check only |
| Publish, unpublish, release; invite a library or revoke one; remove a grant | yes | no | no |
| See the People list and the activity log (proposed) | yes | yes | no |
| Add, remove or change the role of a person; mint any role or library link (decided: an Author cannot invite or manage people) | yes | no | no |
| Send a notification to everyone in the library or repository (proposed) | yes | yes | no |
| Create or delete campaigns, opt out of campaign access (play only) | yes | yes | no |
| Reach anything tied to a campaign: players, beings and item instances in play, a GM's notes | per [ADR 0035](../adr/0035-campaign-scoped-gm-visibility.md) and [ADR 0096](../adr/0096-owner-joins-orga-in-the-information-visibility-bypass.md) | same | no |
| Delete the tenant (and the platform's `tenant-creator` role, [ADR 0184](../adr/0184-deleting-a-tenant.md)) | yes | no | no |
| Leave | yes, unless the last Owner | yes | yes |

**What an Author reaches.** In a repository, every entry (it has no campaigns, no players and no owners of entries). In a library, the **catalog**: items and the stat vocabulary, which is what a content editor for a table's equipment needs. Beings, item instances, campaigns and players stay with admins and GMs. In both, an Author reads and writes the notes on the entries in reach, GM-only notes included, since a repository has no GM and an editor who cannot see a note cannot safely replace it (proposed; see [Open questions](#open-questions)).

**How it is built, in the slice's own order.**

1. **A predicate for authoring.** `campaign_access.py` gains `is_tenant_author` (Owner, Organizer or Author) next to `is_tenant_admin`, and the fallbacks for an entity nobody owns in `entities.py`, `entity_stats.py` and `item_instances.py` accept it for an entry in an Author's reach, instead of `can_manage_any_campaign_in_tenant`, which keeps its meaning (an admin, or someone holding a GM grant). `is_tenant_admin` and `is_tenant_owner` do not change, so an Author is automatically not an admin everywhere they are used. Working names; the slice settles them.
2. **Audit every route that asks only for "a membership".** Each of the routes behind `get_tenant_context` goes into exactly one of three lists: authoring (any member, Author included), admin (Owner or Organizer), Owner. A new `get_tenant_admin_context`-style dependency carries the admin gate. The routes the audit finds that an Author would otherwise inherit today include campaign creation and deletion, the opt-out routes, the tenant `PATCH` and picture, the roster and activity-log reads, the tenant notification broadcast, the stat-vocabulary deletes, and a repository's copy and update routes. Reads of a repository (browse, copy plan, updates) stay open to any member.
3. **The tripwire becomes a table.** `test_membership_roles_are_all_administrative` is replaced by a table-driven test that walks the application's routes, finds every one that depends on `get_tenant_context`, and asserts it is on the audit's authoring list. A new route that forgets to choose then fails a test, instead of silently giving an Author its power. The docstrings that say "every `MembershipRole` is administrative" are corrected in the same change.
4. **Tests: Author cannot X.** One test per row of the matrix that says no, in a repository and in a library, plus the matching "can" rows, plus the role changes ([§3](#3-the-people-screen)) and the sole-Owner guards.
5. **The migration.** One revision adds `author` to `membership_role` and nothing else that uses it. A check constraint, a policy or a backfill that names the new value goes in a later revision, or in an `autocommit_block()`, because the value is not usable inside the transaction that adds it. Postgres cannot remove an enum value, so the downgrade leaves it in place and the code treats a missing role as no access. The production PostgreSQL version is not recorded in the repository and is assumed to be the compose file's.
6. **Everything that carries the role.** `MembershipRoleName`, `TenantRole` and `ManagedTenantOut.role` gain `author`; `GET /me/managed` (which lists only admin memberships today) includes an Author's repositories and libraries, with the role, so "My repositories" lists them; `GET /tenants` and `GET /me` report it; the change feed keeps hiding an Author's actions from players as it hides an admin's. The generated clients and the openapi snapshot are regenerated, and the clients that read the role are updated: account-hub, loot-bot (`Orga` becomes Organizer, and an Author prints as one), inventory-web (an Author may open the catalog but not search beings) and the CLI.
7. **Who is told what.** The notices of [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md) (a grant, an update published) go to admins; an Author receives only the notices about their own role ([§3](#3-the-people-screen)).

### 2. One invite table, with kinds

**One table for every invite**, not a second one beside `campaign_invite`: the same hashed token, required expiry, optional use cap, use counter, revoke, token-hash lookup policy, atomic spend and token redaction ([ADR 0092](../adr/0092-campaign-invite-links.md)) serve all four kinds, and writing them twice is the cost [ADR 0177](../adr/0177-gm-invite-links.md) already declined for a separate route family.

| Kind | Grants | Minted by | Compatible with |
| --- | --- | --- | --- |
| campaign, player | a player in one campaign | `can_manage_campaign` | [ADR 0092](../adr/0092-campaign-invite-links.md), unchanged |
| campaign, GM | a GM of one campaign, single use | `can_manage_campaign` | [ADR 0177](../adr/0177-gm-invite-links.md), unchanged |
| tenant role, Author | an Author membership in a library or repository | an Owner of it | new |
| tenant role, Organizer | an Organizer membership | an Owner of it | new |
| library access | a grant of one repository to a library the redeemer owns, with `source = invited` | an Owner of the repository | new, [RFC 0038](0038-public-repositories-and-discovery.md)'s `source` |

**Never Owner.** No kind grants Owner. Becoming an Owner stays an Owner changing someone's role in People.

**Shape (proposed; the ADR settles the details).** The existing table gains a `kind` column, its `campaign_id` becomes nullable, and check constraints tie them: a campaign kind has a campaign and a role of `player` or `gm`; a tenant-role kind has no campaign and a role of `author` or `orga`; a library-access kind has neither. The table is renamed `invite` (it is no longer about campaigns), its enum widened with `ADD VALUE` under the rule in [§1](#1-the-author-role), and `repository_access`'s excluded list and the conformance test follow the name. Existing rows become `kind = campaign` unchanged, so every link already given out keeps working. The two public routes keep their paths, `GET /invites/{token}` and `POST /invites/{token}/redeem`; a redeem response says which kind it was. Responses that name a campaign gain a name that fits the kind, and the OpenAPI changes this causes (a widened role, a nullable campaign) are recorded in `apps/api/openapi-breaking-accepted.txt` with the ADR, as ADR 0177 did.

**Per-kind rules.**

- **An Author link** is single use by default and short-lived by default; its Owner may raise the use cap, so one link can bring in a small team. It always has an expiry and a cap, never an unlimited one.
- **An Organizer link** is single use and short-lived, with no way to raise either, as a GM link is: it hands over an admin role.
- **A library-access link** is single use by default, short-lived, and its Owner may raise the use cap, since sharing a repository with a handful of tables is the point. A leaked unredeemed library link reveals a private repository to whoever uses it first, which is the cost to state to the Owner when it is made.
- **Proposed constants**, in code and easy to change: role links at most 7 days (as a GM link); library links at most 30 days (as a player link); a cap an Owner may raise to a small fixed ceiling.
- **Minting is the Owner's alone**, for the three new kinds, because adding a person or a grant is already Owner-only. Whether an Organizer may mint an Author link is an [open question](#open-questions).
- **Shown once, listed without tokens, revocable**, with creation, revocation and each redemption in the activity log (the redeemer is the actor) and the Owners told of a redemption, as for the campaign kinds.

**The preview** is unauthenticated, as today, and says only what the visitor is about to be asked: the library's or repository's name and picture and the role or the offer ("join as an Author", "a repository is being shared with your library"). The same `404` for an unknown, expired, revoked or used-up token, in every kind.

**Redeeming** needs a login (an account is provisioned on the first call, [ADR 0023](../adr/0023-authgear-token-verification.md)) and is atomic, as ADR 0092 says.

- **A role link** creates the membership with that role. **It never changes an existing one**: someone who already has any role in the tenant gets `200`, `already_joined`, no use is spent and nothing changes, so a link cannot raise or lower a role. Changing a role is People's job, by an Owner.
- **A library-access link** takes one more input, the library to share with, which the redeemer picks from the libraries (and repositories, for a bridge) they are an Owner of: the same standing that removes a grant ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). It creates the grant with `source = invited`, tells the library's members as a direct grant does, and is idempotent for a library that already holds one. A redeemer who owns no library is told so, and is offered creating one only if the platform allows it to them (the `tenant-creator` gate stays, [ADR 0175](../adr/0175-me-says-what-you-may-create.md)).
- **No tenant-wide membership is created by a campaign link**, as ever.

**The invite code is the pasted token.** The hub's join page already accepts "Invite link or code" and a bare token; that is the whole of the code. A short typeable code is not built: ADR 0092 chose 256-bit tokens so that guessing is infeasible, a short code would need its own brute-force protection, and it is listed under [Not in scope](#not-in-scope).

**The token stays out of everything.** It is in the path of the two public routes and nowhere else: the redaction of spans, access logs and `structlog` (and `tests/test_invite_token_redaction.py`) is extended with a case per kind, the library choice travels in the request body and never in the URL, and the hub keeps the token in the fragment and in `sessionStorage` only until it is used ([ADR 0171](../adr/0171-account-hub-campaign-invite-links.md)).

**Rate limiting is not part of this RFC.** The routes are the same `/invites/*` paths, so the in-process backstop already covers every kind and the edge rule, which is the maintainer's own pre-launch task, covers them without a change. It is a v1.0 row of its own: [docs/operations/invite-link-rate-limiting.md](../operations/invite-link-rate-limiting.md). A leaked Author or library link costs more than a player link, which is why the defaults above are tight and the Owner can see and revoke every link.

**The accept flows, in account-hub's join page.** One page, branching on the kind the preview returns: a campaign link as today; a role link shows "You are invited to join *Name* as an Author", then **Join** after login; a library link shows what is being shared and asks which of the visitor's libraries should receive it, then **Share**. A dead link shows the one message every dead link shows. The home card's wording ("Join a table") is covered by the terminology sweep, not here.

### 3. The People screen

One tab, **People**, in each repository's "My repositories" page and in a library's page, listing **everyone with a role**: Owners, Organizers and Authors (a library's players and GMs are on its campaigns, not here).

- **A row** shows the person's name, the role as a label, who added them, and for an Owner the actions: change role (a choice of Owner, Organizer and Author, each with one line on what it allows) and remove. The last Owner cannot be demoted or removed, and anyone may leave, as the API already guards ([ADR 0036](../adr/0036-user-player-character-crud-api.md)).
- **Add by exact lookup** of an email or a nickname ([ADR 0055](../adr/0055-user-lookup-by-email-or-nickname.md)), one person or several, each with a role; this is the existing flow with labels.
- **Add by invite link:** choose Author or Organizer (never Owner), an expiry, and for an Author link how many people may use it; the link is shown once with a **Copy** button; below, the links so far with a status of Active, Revoked, Expired or Used up and **Revoke**. The status function and the link builder ADR 0171 wrote are reused. A repository's "Invite a library" is on its Libraries using it tab ([RFC 0036](0036-repository-tooling.md), slice T2), which offers a link once U2 has landed and keeps the id until then.
- **Never the raw enum value.** Each client has one table from `owner`, `orga`, `author` to Owner, Organizer, Author, and the API's own notification text uses the same words.
- **Notifications, in words a person reads.** Being added: "You were added to *Name* as an Author" (today "You now have `orga` access to …"). A role change, which today writes only to the activity log: "Your role in *Name* is now Organizer" (proposed). Removal: "Your access to *Name* has ended", without "tenant-wide membership". The Owners are told when someone joins by a link: "*Person* joined *Name* as an Author". *Name* is a library or a repository, and the text says which. These strings are written for roles only; the rest of the sweep is [RFC 0036](0036-repository-tooling.md)'s G2.

### 4. A GM's title, per campaign

Decided with the maintainer and recorded as **its own small ADR**, not here, since it is not part of repository tooling and shares no code with the rest of this RFC: a game master may be called something else at their table (DM, Storyteller, Narrator, Master). What this RFC fixes so that the ADR can be short:

- **Per campaign**, set by the campaign's managers (a GM of it or an admin), shown wherever that campaign appears, by the hub, inventory-web and the bot.
- **Two fields, singular and plural** ("Storyteller", "Storytellers"), because the plural is not always the singular with an `s`. The default, when unset, is "GM" and "GMs", spelled out as "game master" on first use in a surface. A gender or other inflection is deferred.
- **Strings become templates** in the clients that say "GM", so the title is substituted and no surface keeps a hard-coded word. Wording that needs an article ("a GM") is rewritten to avoid one.
- **Additive API**: two optional fields on the campaign, written through the existing campaign update. The ADR settles names, length and the characters allowed (plain text).
- **Not a role.** The title is a label. It does not change what the campaign's GM may do, and invite links for it stay "GM" links in the API.

## Decided with the maintainer (2026-10-07)

- **An Author role in repositories and libraries.** It edits content; it cannot publish, invite, manage people or delete structure; deleting something that libraries hold warns with a count ([RFC 0041](0041-entity-kinds-and-author-freedom.md)) and does not block.
- **Invite links for Author and Organizer, never Owner**, single use and short-lived by default as [ADR 0177](../adr/0177-gm-invite-links.md)'s GM link is, and a library-access link on the same table, so that a private repository can be shared without an id.
- **The invite code is the pasted token.** A short typeable code, and maybe QR detection, are later.
- **The names**: Owner, Organizer, Author, with Admin as the collective noun for the first two (ADR 0194).
- **A GM's title is chosen per campaign**, with a singular and a plural field, as a small ADR of its own.
- **Repository creation stays behind `tenant-creator`**; nothing here lets an invite create a repository.
- **An Author may delete an entry nobody inherits from**, with the count warning of RFC 0041.
- **An Author reads every note on the entries in reach**, GM-only notes included, in libraries as in repositories.
- **Only an Owner mints invite links.** An Organizer does not mint an Author link.
- **The proposed lifetimes stand**: role links at most 7 days, library links at most 30 days, as a GM link and a player link are today; the use-cap ceiling is the one proposed in [§2](#2-one-invite-table-with-kinds).
- **The invite table is renamed** from `campaign_invite` to `invite`.

## Slices

| Id | What | Depends on | Touches |
| --- | --- | --- | --- |
| U1 | The `author` role: enum value, `is_tenant_author`, the route audit and the admin gate, the table-driven test in place of the tripwire, schemas and `/me` lists, "Author cannot X" matrix, role wording in notifications | none; independent of the invite table | api |
| U2 | One invite table with kinds: rename and widen, Author and Organizer links, library-access links, the accept flows and paste-code in the join page, redaction cases per kind | U1 for the role links; the library kind needs only today's grants, since every grant today is an invited one and [RFC 0038](0038-public-repositories-and-discovery.md)'s `source` column defaults to that | api, hub |
| U3 | People for libraries and repositories with Author and the labels, the links panel | U1, U2; builds on slice T1 of [RFC 0036](0036-repository-tooling.md) | hub |
| side ADR (GM title) | The GM's title per campaign, singular and plural, strings as templates | none; a lane of its own, outside repository tooling's milestone | api, hub, bot, inventory-web, docs |

Each is recorded as its own ADR when it lands. U1 and U2 each carry a migration, so they go in order with the other migrations in flight, and each regenerates the openapi snapshot and the generated clients.

## Open questions

- **The matrix's remaining proposed rows.** Whether an Author may rename the repository (proposed no), and whether the copy and update routes are an admin act (proposed yes).
- **Are Authors added to a campaign-less repository only by its Owner?** Yes under the proposal; a repository has no GM to delegate to.
- **May an Author see who else is in a repository?** Proposed no (People and the activity log are admin reads). A repository has no players, so showing co-authors would leak nothing about play; it is left out to keep one rule.

## Not in scope

- **Finer permissions**: per-entry or per-kind rights, an Author limited to one subtree, read-only members.
- **Request to join**: a person asking for a role or for a repository; an Owner sends a link instead.
- **A short typeable code** and **a QR code**, for the paste-code or the link. The token is the code; a QR could be read into the same field later.
- **An approval queue** for redemptions, as for player links.
- **A role other than Owner, Organizer and Author**, and Owner by link.
- **CLI commands for roles and links**: `lorenzo api` reaches the routes, and `lorenzo repo offer` keeps granting by id.
- **Public discovery and its grants** ([RFC 0038](0038-public-repositories-and-discovery.md)), and the public repository's own `source = public`.
- **The edge rate-limit rule**, which is operational.

## Alternatives considered

- **Reuse Organizer, with labels.** Costs nothing in code, and is the shape the code has by accident. But an Organizer can delete structure, rename the repository, copy and update, create campaigns and read the activity log; "Organizer" in a repository would say author and mean admin, and an editor of a shared repository would hold every power but publish. A new role makes the safe thing the default.
- **An Author role in repositories only.** A repository-only role needs the code to ask the tenant's kind in every check, and leaves the catalog of a library with only admins to edit it. One enum value in both is smaller and is what the maintainer asked for.
- **A separate author-invite table.** The same hash, lookup policy, atomic spend, redaction and tests written twice for one column, which [ADR 0177](../adr/0177-gm-invite-links.md) rejected for GM links; a library-access link would be a third copy.
- **Capability flags instead of roles**, a table of what each member may do. More flexible, and a larger surface to audit and to explain; the three named roles are enough for what is asked, and finer rights are not in scope.
- **A link that upgrades an existing membership.** Convenient, and it turns a pasted link into an escalation. A role changes only in People.
- **Grant by library name or slug.** Exposes which libraries exist and lets anyone send a notification to any library; an invite link names nothing and expires.

## Consequences

- A repository can have people who edit without being able to publish, delete its vocabulary or hand it to anyone, which is what lets an Owner bring in help safely.
- The role is a permanent enum value; Postgres cannot drop it. A mistake in the matrix is fixed in the checks, not by removing the role.
- Every route behind `get_tenant_context` is looked at once, and the tripwire test becomes a table that fails when a new route does not choose a gate. This is the cost of the role, and it is paid up front rather than found later.
- Authors need their own predicate, so the "unowned entity" fallback changes in three routers; an admin or a GM sees no change.
- Link kinds share one table, one set of routes and one redaction test. The OpenAPI contract changes in a few responses (a widened role, a nullable campaign), recorded as ADR 0177's was, and the generated clients are regenerated.
- A private repository can be shared with a link, so no one has to make a repository public to share it, and an Owner never needs a library's id. A leaked library link, as an unredeemed GM link, is a cost that lasts until it is used, expires or is revoked.
- Role wording changes in the API's own notifications and in four clients; the raw values stop being shown.
- The GM's title is a small, separate change that can land at any time without waiting for the rest.
