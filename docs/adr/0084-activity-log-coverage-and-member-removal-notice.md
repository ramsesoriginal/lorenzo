# 0084 - Activity log coverage policy and a member-removal notice

Status: accepted

## Context

[ADR 0063](0063-tenant-activity-log.md) built `audit_log` and `GET /tenants/{id}/activity-log` as "a deliberately narrow first slice", hand-picking seven mutation points (membership create/bulk-create/update/delete, campaign create/delete, GM grant/revoke) in `routers/tenants.py` and `routers/campaigns.py`. It named what it left out, but never said *why those seven* or what the log is ultimately for, so the split reads as accidental and nothing tells the next contributor whether a new mutation route should log.

The log exists to answer one question for a tenant OWNER: **"who did this?"** - and that question is not limited to player-initiated actions. It includes the owner's own GMs and other admins; a GM moving an item, granting knowledge, or retiring a group is exactly the kind of thing an owner asks about. Today none of that is recorded (roughly fifty tenant-scoped mutations across `item_instances`, `items`, `characters`, `players`, `groups`, `information`, `stats`, `campaigns` write nothing).

Two adjacent gaps surfaced while auditing it:

- `delete_membership` already records `membership.deleted` (ADR 0063), but with `detail=None` - it cannot say whether the member was removed by an owner or left of their own accord, or what role they held. And nothing tells the removed person. Removal ends only the tenant-wide `Membership` row: `Player` and `CampaignGm` rows reference `app_user`, not membership, so a removed member keeps any campaign seats they hold and their characters stay owned (ADR 0025's `SET NULL` only applies when a `Player` row itself is deleted, which membership removal does not do). From their side, the tenant-wide access simply disappears with no explanation.
- Once GM and player actions are in the log, who can read it matters. ADR 0063 gated it by `get_tenant_context` (any tenant-wide member). Checked while implementing this ADR: `MembershipRole` has only `OWNER` and `ORGA`, so that already means tenant administrators only - a GM or player with no `Membership` row gets a `404` today. The gate is right; what was missing was anything saying it is deliberate or guarding it.

## Decision

### What the log is for, and the coverage rule

The activity log is an **accountability timeline for tenant administrators**: who changed what shape the tenant has, who can see or do what in it, and who holds what. It is not a full change history (per-row `created_by`/`updated_by`, [ADR 0029](0029-attribution-created-by-updated-by.md), already answers "who last touched this row").

Rule: **every mutation that changes what exists, who owns or holds it, or who can see/do what - by any actor, GMs and admins included - calls `record_activity`.** Concretely:

- *Existence*: create/delete of items, item instances, characters (incl. promote/demote), groups, campaigns, players (join/leave), stat groups/definitions, information.
- *Ownership and placement*: owner set/clear, container set/clear, split, merge, bulk-assign, bulk-move.
- *Access and visibility*: memberships, GM grant/revoke, admin opt-out toggle, character-player roster links, group membership (single and bulk), knower grant/revoke.
- *Definition of what things are*: item prototype-set edits (single and the three bulk ops), since they change inherited stats.
- *Administrative settings*: tenant and campaign `PATCH`.

Deliberately **not** logged, and now documented as deliberate rather than accidental:

- Descriptive-content edits: item/instance/character renames and entity stat-value writes - high volume, low accountability value, and per-row attribution already covers them.
- Profile pictures (user/tenant/campaign) and `PATCH /me`: cosmetic, and `/me` is user-scoped with no tenant to attach an entry to.
- Notification creation/reading: communication, not tenant structure ([ADR 0058](0058-notifications.md)).
- Platform-scope events (suspension, `/admin/*`): still out of scope, unchanged from ADR 0063 - no `tenant_id` to attach them to.
- Tenant creation: the log is per-tenant and its RLS needs `app.tenant_id` set, which that route runs before. `tenant.created_by` and the new OWNER membership already record who created it.

### Shape of an entry

- `action` is `"<noun>.<verb>"` free text, as ADR 0063 already established (`item_instance.moved`, `group.member_added`, ...).
- **Bulk operations write one entry per call, not per item**, with counts in `detail` (`"3 ok, 1 failed"`). This keeps the log readable; the per-item outcome is already in the call's own response.
- **`detail` carries ids, counts and enum-like labels only - never user-authored content.** A tenant member who can read the log must not learn GM-only text from it. `information.created` records the target entity and its visibility tier, not its title or body.
- Entries are written in the same transaction as the mutation, before its commit, exactly as ADR 0063 and `activity_log.py` already require (RLS on `audit_log` is plain `tenant_id = app.tenant_id`; a post-commit write would have lost that context - see [ADR 0032](0032-item-and-item-instance-crud-api.md)).

### Read access: administrators only, already true - now pinned

`GET /tenants/{tenant_id}/activity-log` stays gated by `get_tenant_context`. That is "OWNER or ORGA only" **because every `MembershipRole` is administrative**, not because any check says so. This ADR changes no behavior and adds no `403`: a plain member cannot exist today. It adds tests proving GM-only and player-only users get `404`, and a **tripwire test** that fails if a non-administrative role is ever added to `MembershipRole` - at which point the gate must become an explicit `campaign_access.is_tenant_admin` check in the same change, or the new role would silently read every GM's and player's attributed actions.

(An earlier draft of this ADR called this a breaking narrowing needing an account-hub change. It was not: it was written before checking the role enum.)

### Member removal

- The existing `membership.deleted` entry gains a `detail`: `"removed"` vs `"left"` (actor is the target or not) plus the role held.
- **Notify the removed person, always** - including on self-service leave, per the owner's request that every departure produce a confirmation. One `scope="tenant"`, `type="tenant_membership_removed"` notification to the removed user, written by the existing notifications core helper in the same transaction as the delete. Its title/body are self-contained text (ADR 0058's rule), naming the tenant and stating plainly what changed and what did not: their tenant-wide membership ended, nothing they created was deleted, and any campaign seats (as player or GM) they hold there are unchanged. The user can still read it after losing membership: `notification`'s RLS admits `user_id = app.user_id` regardless of tenant.

## Not in scope

- An exhaustive change history of descriptive content (see above).
- Resolving `actor_id`/`target_id` to display names server-side - clients keep resolving these, as ADR 0083 already notes.
- Retention/pruning of the log. It grows unbounded, as before.
- Any change to what `created_by`/`updated_by` track.

## Consequences

- Every new tenant-scoped mutation route now has a stated default: log it if it matches the rule above. The categories excluded above (pictures, notifications, `/me`, `/admin`) need no per-route note; a one-off exclusion - a rename, a stat value, tenant creation - says so in its own docstring.
- `routers/item_instances.py`, `items.py`, `characters.py`, `players.py`, `groups.py`, `information.py`, `stats.py` gain `record_activity` calls; `routers/tenants.py` and `routers/campaigns.py` gain the remaining ones. No migration - `audit_log` is unchanged.
- The log will be markedly busier. Pagination already bounds reads ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)); a `?action=`/`?actor_id=` filter is a reasonable follow-up, not built here.
- The read gate is documented as deliberate in the router docstring, and the tripwire test names this ADR.
