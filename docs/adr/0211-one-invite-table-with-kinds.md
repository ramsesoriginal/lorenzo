# 0211 - One invite table, with kinds

Status: accepted, decided with the maintainer on 2026-10-08. Slice U2 of [RFC 0040](../rfcs/0040-authors-and-invites.md), tracked in #546. Builds on [ADR 0092](0092-campaign-invite-links.md) (campaign invite links), [ADR 0177](0177-gm-invite-links.md) (the GM link), [ADR 0171](0171-account-hub-campaign-invite-links.md) (the hub's side) and [ADR 0210](0210-the-author-role.md) (the Author role, which a link can make). The `source` of a grant, which [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) adds, is another slice's; a grant made by a link is what every grant is today, an invited one, and nothing here leaves it out of reach.

## Context

Invite links were campaign-only: a hashed 256-bit token, a required expiry, an optional use cap, a use counter, revoke, a policy that lets the holder of a token read that one row, an atomic spend and a redaction of the token from spans and logs. They made a player or, as a single-use link of at most seven days, a GM. [ADR 0092](0092-campaign-invite-links.md) and [ADR 0177](0177-gm-invite-links.md) each left "tenant-role invite links" out as a different, higher-privilege thing. [RFC 0040](../rfcs/0040-authors-and-invites.md) decides them: a link that makes an Author or an Organizer of a library or repository, never an Owner, and a link by which the Owner of a private repository shares it with a library without knowing the library's id.

## Decision

### One table, with a kind

`campaign_invite` is renamed `invite` (migration `c4a2f7e91b35`; the model is `Invite`), not joined by a second table: the hash, lookup policy, atomic spend, redaction and tests are written once.

| `kind` | `campaign_id` | `role` | `tenant_id` is | Redeeming makes |
| --- | --- | --- | --- | --- |
| `campaign` (every row there was, the default and the backfill) | the campaign | `player` or `gm` | the campaign's tenant | a player, or a GM, as before |
| `tenant_role` | none | `author` or `orga` | the library or repository | a membership with that role |
| `library_access` | none | none | the repository | a grant of that repository to a library the redeemer owns |

`campaign_id` and `role` become nullable. Two check constraints keep it honest: `invite_kind_shape` ties the three columns to the kind (a null role does not satisfy a role link, whatever `NULL IN (...)` says), and `invite_non_campaign_capped` says a link that is not for a campaign always has a `max_uses`. The role enum becomes `invite_role` and gains `author` and `orga`; the checks compare it as text, because a value just added to an enum cannot be used in the transaction that adds it, and the migrations of a new database run in one. The composite foreign key to the campaign (`invite_campaign_id_fkey`) does not apply to a row without a campaign. The two policies keep their meaning and are renamed `invite_tenant` and `invite_by_token`; the table is on [`repository_access`](../../apps/api/src/lorenzo_api/repository_access.py)'s excluded list under its new name, so it is never repository content, and the conformance test passes. No kind makes an Owner: not in the enum, not in the schema, refused by the route.

### Making and managing links

A campaign's links are `POST`, `GET` and `DELETE /tenants/{id}/campaigns/{campaign_id}/invites` as before, minted by whoever can manage the campaign. They report `kind` and a nullable `campaign_id` and `role`, and refuse `author` and `orga`.

A library's or repository's own links are `POST`, `GET` and `DELETE /tenants/{id}/invites[/{invite_id}]`, **an Owner's alone** (403 `invite-management-forbidden` for an Organizer or an Author, 404 for a stranger; an Organizer does not make an Author link, as [RFC 0040](../rfcs/0040-authors-and-invites.md) decides). The body is `{kind, role?, expires_at?, max_uses?}`:

- `kind: tenant_role` with `role: author` or `orga`; `kind: library_access` with no role, and only for a repository (409 `not-a-repository` for a library).
- **Every one ends and is capped.** `max_uses` left out is 1. An Author link and a library link may be raised to **10**, a small fixed ceiling, so one link can bring in a team; an Organizer link is single use, as a GM link is.
- `expires_at` left out is **3 days** for a role link and **7** for a library link, the longest being **7** and **30**, as a GM link and a player link are. These are constants in `invites.py`.
- Shown once, with the token; listed newest first with `kind`, `role`, `is_active`, `use_count` and never a token; revoked instantly and idempotently. Revoking leaves what people already took.
- The activity log gets `invite.created`, `invite.revoked` and `invite.redeemed` (the redeemer is the actor), never the token. A campaign's keep their `campaign_invite.*` names.

### The preview, before anyone accepts

`GET /invites/{token}` is unauthenticated and says what the visitor is about to be asked and nothing more: `kind`, `name` (the campaign, library or repository the link is for, the repository for a library link), `campaign_name` (the campaign's, null for the other kinds, as the field always was), `tenant_kind` (`play` or `repository`, null for a campaign), `picture_url` (the campaign's, or the tenant's, whose picture is public by its address already) and `role` (null for a library link). No tenant id, no member, no count: a leaked link shows a name, a kind and a role, and a test reads the whole response for ids. A link that is unknown, expired, revoked or used up is the same `404` in every kind.

### Redeeming

`POST /invites/{token}/redeem` needs a login and is atomic; its response carries `kind`, `tenant_id`, a nullable `campaign_id`, `role` and `player_id`, and `library_id`. A campaign link is as before.

- **A role link creates the membership with the link's role, attributed to whoever made the link, and never changes an existing one.** Someone who already holds any role in the tenant gets `200`, `already_joined`, no use is spent and nothing changes: a link can raise or lower no one's role, which stays an Owner's act in People. The tenant's **Owners** are told, in words ("*Person* joined *Name* as an Author", `invite_role_redeemed`).
- **A library link takes the library in the body**, `{"library_id": ...}`: never in the path, with the token. It is any tenant the redeemer is an **Owner** of other than the repository itself (a repository too, for a bridge): the standing that gives a grant up ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). Without it, `422 invite-library-required`; one that does not exist, is not theirs or is the repository itself, `422 invalid-invite-library`, the same answer, so it tells no one which libraries exist; neither spends a use. Otherwise it makes the grant the Owner naming the library would make: the one function, `repository_grants.grant_repository_access`, writes it, logs `repository.granted` with the redeemer as actor and tells the library's Owners and Organizers (`repository_granted`), and the route also logs `invite.redeemed` and tells the repository's Owners (`invite_library_redeemed`). A library that already holds the grant gets `200` and spends nothing. A redeemer who owns no library is told so by the hub; offering to make one is the hub's, and only if the platform allows it to them ([ADR 0175](0175-me-says-what-you-may-create.md)).
- Nothing is created for a campaign link beyond what it was: no tenant-wide membership, ever.

`notify_tenant_admins` and the grant move out of `routers/repositories.py` into `repository_grants.py`, which both doors call; `PUT .../subscribers/{id}` behaves as before.

### Redaction, per kind

The token is in the path of the two public routes and nowhere else. `redaction.py` keeps scrubbing the segment after a root-level `/invites/`, and now exempts `/tenants/{id}/invites/{invite_id}` as it exempts the campaign path, since that last segment is an id. `tests/test_invite_token_redaction.py` has a case per kind: the token of a role link and of a library link in no span and no log line, the library's id in the body and never in the address or a span, and the management paths left alone.

### The contract

What a link reports is wider: `campaign_name`, `role` of the preview, `campaign_id` and `role` of a redemption and of a campaign's list and creation become nullable. `oasdiff` calls each a breaking change; all eight are accepted on purpose in `apps/api/openapi-breaking-accepted.txt`, and the commit carries a `BREAKING CHANGE` footer, as [ADR 0177](0177-gm-invite-links.md) did. Everything else is additive: the `kind`, `name` and `tenant_kind` of the preview, the `library_id` and an optional body of the redemption, and the new routes.

### The hub's join page

One page, branching on the kind the preview returns, [ADR 0171](0171-account-hub-campaign-invite-links.md)'s as it was for a campaign. A role link says "You've been invited to join the library *Name* as an Author" (or Organizer, or the repository), and the button after login says **Join as an Author**; on success "You're in. *Name* lists you as an Author", or, for someone already in, that a link does not change anyone's role, and where to go next (the library, or the repository in Studio). A library link says which repository is being shared and shows, after login, **Share it with** a list of the libraries and repositories the visitor owns, labelled by what each is, and **Share**; a visitor who owns none is told so, and offered **Make a library** only if `GET /me` says they may create one. The token waits in `sessionStorage` through the login and the making of a library. A dead link shows the one message every dead link shows. **A box for a link or a code** (the token is the code) is on the page whenever there is no link in the address, and pasting opens it as a link someone had opened; the home page's box and this one share `pastedInvite` and its message, which no longer says "your GM". The words are Owner, Organizer, Author, library and repository, never `orga`, tenant or grant. The page is checked at 375 px.

The People links panel, which makes these links from the hub, is slice U3.

## Not in scope

- **The People links panel** (making, listing and revoking role links in the hub) and a repository's "Invite a library" button: slices U3 and T2. The API is ready for both.
- **The `source` of a grant**, [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)'s: a grant made by a link is an invited one, and the column, when it comes, defaults to that.
- **CLI commands for links**: `lorenzo api` reaches the routes.
- **A short typeable code, a QR code, an approval queue, request to join, Owner by link**, and the edge rate-limit rule, as in [RFC 0040](../rfcs/0040-authors-and-invites.md).

## Consequences

- A person can be brought into a library or repository, and a private repository shared, with a link and no id, and no link can make an Owner.
- A leaked unredeemed Author or Organizer link makes a role for whoever uses it first, until it is used, expires or is revoked; a leaked library link reveals a private repository the same way. The defaults are tight and an Owner sees and revokes every link.
- One table, one set of public routes and one redaction test serve four kinds; the cost is the nullable columns, held by the shape check.
- The OpenAPI contract changes in eight responses, recorded.
- Downgrading deletes the links that only the wider table can hold; the enum keeps `author` and `orga`, since Postgres cannot remove a value.
