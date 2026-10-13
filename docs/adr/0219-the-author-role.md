# 0219 - The Author role

Status: accepted, decided with the maintainer on 2026-10-08. Slice U1 of [RFC 0040](../rfcs/0040-authors-and-invites.md), tracked in #545. Builds on [ADR 0010](0010-user-tenant-membership-model.md) and [ADR 0022](0022-user-tenant-membership.md) (the membership and its roles), [ADR 0036](0036-user-player-character-crud-api.md) (who manages memberships), [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (the repository's own routes) and [ADR 0194](0194-user-facing-terminology.md) (the words).

## Context

A membership had two roles, Owner and Organizer, and the code treated them as one set, "tenant admin". Seventeen router modules ask only for "a membership" (`get_tenant_context`), which meant "an administrator" by accident: `tests/test_activity_log_access.py` carried a tripwire that failed on the day a third role was added, and the docstrings of the activity log, the knowledge list, the change feed and campaign opt-out said so. [RFC 0040](../rfcs/0040-authors-and-invites.md) decides a third role, **Author**, in libraries and repositories alike: it edits content and can do nothing that changes who has access, what is published or what the structure is.

## Decision

### The role

`MembershipRole.AUTHOR`, `author` in the API and the table, shown as **Author**. One revision, `a3c81d6e0f52`, adds it to the native `membership_role` enum with `ADD VALUE IF NOT EXISTS` and nothing else: a new enum value cannot be used in the transaction that adds it, and no check, policy or backfill names it (no row-level-security policy reads `membership.role`). Postgres cannot remove an enum value, so the downgrade leaves it in place.

`MembershipRoleName` (the input of `POST` and `PATCH .../memberships`), `TenantRole` (`GET /tenants`, `GET /me`) and `ManagedTenantOut.role` gain `author`. The Owner changes a role to and from Author with the existing `PATCH`; the last-Owner guards are unchanged and still count Owners only.

### The predicates

`campaign_access.py` gains, next to `is_tenant_admin` and `is_tenant_owner`, which do not change:

- `membership_role_of`: the role a user holds in a tenant, or `None`.
- `is_tenant_author`: Owner, Organizer or Author.
- `entry_in_author_reach`: **in a repository every entry, in a library the catalog, the entries that are items.** A repository has no campaigns, players or owned entries; in a library, beings, item instances, campaigns and players stay with the administrators and GMs.
- `can_author_entry`: a member who may edit and an entry in that reach.

`can_manage_any_campaign_in_tenant` keeps its meaning, an administrator or the holder of a GM grant. The fallback for an entry nobody owns in `routers/entities.py` (information, slugs, knowers) and `routers/entity_stats.py` (stat values, tags) accepts `can_author_entry` next to it. The item-instance and character fallbacks do not: an Author reaches no instance and no character. An entry that something owns is still decided by its owner's campaigns, for an Author as for an Organizer; nothing about owned entries changes.

### Notes: an Author reads every one on the entries in reach

`InformationVisibility` gains `author_sees_all` (an Author of a repository) and `author_entry_ids` (the catalog items of a library, resolved only for an Author), both with defaults so every other caller is unchanged. `can_see` and `visible_information_clause` honour them, and the parity test over a fixed matrix of callers has the two new ones. Neither is the administrators' bypass flag: `is_admin` stays Owner or Organizer, so what an Author reads never widens past the entries in reach, and an Author reads nothing GM-only about a being or a campaign.

### The audit and the admin gate

`dependencies.get_tenant_admin_context` is `get_tenant_context` plus `is_tenant_admin`, and an Author gets **403 `tenant-admin-required`** ("Only an Owner or an Organizer can do this"): they are a member, so nothing is hidden by a 404, and a non-member still gets the 404 of the membership check before it. Every one of the 59 routes behind `get_tenant_context` goes on exactly one list:

| Tier | Routes |
| --- | --- |
| Authoring: any member, an Author too | Items: create, edit, bulk prototype changes, set prototypes, delete (with the rule below). Stat groups, stat definitions and enum values: list, read, **create and add**. Computed stats: list, set, delete, preview, dependents. Payload content. `release-preview`, `releases` and `attachments` of a repository. A library's reads of a repository: list, browse, dependencies, copy plan, updates, releases, contributions |
| Admin: Owner or Organizer, by `get_tenant_admin_context` | Tenant `PATCH` and picture (set and delete). The activity log, the knowledge list, the membership roster. The notification to everyone. Campaigns: create, delete, opt out, opt back in. `GET .../subscribers`. Deleting a stat group, a stat definition, an enum value |
| Admin unless a dry run | `POST .../copy` and `POST .../updates`. An Author may run either with `dry_run`, to check what it would do, and applying one is an administrator's: the copy brings stat groups in |
| Owner, checked in the route (each keeps its own problem type) | Deleting a tenant, adding people (one or many), changing a role, removing one (an Owner's, or your own: anyone may leave), publish, unpublish, correct a release, grant and revoke a repository, give up a grant |

The proposed rows of the matrix are decided as proposed: an Author does not rename the library or repository or change its picture, does not read the roster, the activity log or who copied a repository, and does not send a notification to everyone. Authors do read `release-preview` and the release list, which tell an editor what a publish would carry; the Owners' own list of libraries using a repository is an administrators' read.

**Deleting an entry.** An Author deletes an item no other entry inherits from (`DELETE .../items/{id}`); while another entry has it as a prototype it is **403 `inherited-entry-deletion-forbidden`** and an Owner or an Organizer decides. This is the part of the matrix [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) builds on with its subscriber warning; here it is the check on the one delete there is.

### The tripwire becomes a table

`test_membership_roles_are_all_administrative` is gone. `tests/test_author_route_audit.py` walks every route of the application, finds each one that depends on `get_tenant_context`, and asserts it is on exactly one of the four lists above and that the admin gate is on those routes and no others. A new route that forgets to choose fails the test instead of giving an Author its power, and a list that names a route that is gone fails too. It then calls every admin and Owner route as an Author (403 on each, in a library and in a repository), every Owner route as an Organizer (403) and every admin route as one (never a 403), a dry run as an Author, and every route as a stranger (404). The docstrings that said every role is administrative are corrected in the same change (activity log, knowledge, change feed, campaign opt-out).

### What carries the role

- `GET /me`, `GET /tenants` and `GET /me/managed` report `author`. `GET /me/managed` lists the Author's repositories and libraries with the role, so "My repositories" has them, and an Author sees no campaign of a library there, only any they GM: every campaign of a tenant is an administrator's.
- The change feed keeps hiding an Author's actions from players, as it hides an administrator's.
- The notices of [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (a grant, an update published, a grant ended) go to a library's or repository's Owners and Organizers, not to its Authors: `create_tenant_admins_notification` replaces `create_tenant_members_notification`. An Author is told only about their own role.

### Words

`role_names.py` holds the three names and the two words for a tenant, **library** and **repository**; the API's own role text goes through it.

- Being added: "You were added to *Name* as an Author", "You are now an Author of the library *Name*." (was "You now have `orga` access to *Name*").
- A role change, which used to write only to the activity log: `tenant_role_changed`, "Your role in *Name* is now Organizer". Nobody is told of their own change, and a `PATCH` that names the role they have changes and says nothing.
- Removal: "Your access to *Name* has ended." (was "tenant-wide membership"); a library adds that campaign seats are unchanged, a repository has none.

### The clients

The generated clients are regenerated (`packages/api-client/src/schema.d.ts`, the CLI's models). loot-bot's `/whoami` prints Organizer (it printed Orga) and Author; inventory-web gets `isTenantAdmin`, so an Author opens the catalog (any membership) and searches characters, as a player does, instead of the being search, which is an administrators' route; account-hub's `roleLabel` says Author. The hub's People tab and the meanings of the three roles are slice U3, [RFC 0040](../rfcs/0040-authors-and-invites.md) §3.

### The contract

Widening `role` in the two lists that report it is a change `oasdiff` calls breaking (a client written against two values may not handle a third). Both are accepted on purpose in `apps/api/openapi-breaking-accepted.txt`, and the commit carries a `BREAKING CHANGE` footer so release-please versions it. Every other change is additive: the 403 of the new gate, a wider request role.

## Not in scope

- **Invite links** for Author and Organizer, library-access links and the join page: slice U2. The Owners being told of a person who joined by a link is there.
- **The People tab and the links panel** of the hub: slice U3.
- **Authoring beings, groups and characters in a repository.** The entry-level routes (information, slug, stats) reach every entry of a repository for an Author; the routes that create or change a being, a group or a character stay with the existing standing (an administrator, a GM, a player of it), as does an entry that something owns. Entries of every kind in a repository are [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md)'s.
- **The count warning** on deleting an entry that libraries hold ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md)), and renaming structure.
- **A role other than Owner, Organizer and Author**, finer rights, and the GM's title (its own ADR).

## Consequences

- A repository can have people who edit without being able to publish, delete its vocabulary, hand it to anyone or see who copied it.
- The role is a permanent enum value. A mistake in the matrix is fixed in the checks.
- Every route behind `get_tenant_context` was looked at once; the table fails when a new one does not choose.
- Authors need their own predicate, so the unowned-entry fallback changes in two routers; an administrator or a GM sees no change.
- `GET /tenants/{id}/subscribers`, which was open to every member, is now an administrators' read.
- An Author reads the GM-only notes of the entries in reach and nothing else of play.
