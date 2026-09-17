# 0058 - Notifications: platform/tenant/campaign/character scope, in-app inbox

Status: accepted

## Context

Users want to be notified from four different scopes: the platform itself, a tenant (invited to one), a campaign (a scheduled session), or a specific character (an in-game event). Three decisions were made with the user before this ADR:

1. **In-app inbox only for v1.** This codebase has zero outbound-delivery infrastructure - no email sending, no push, no websockets (Authgear handles its own login-related email, this app never sends any). Building a real delivery channel is separate, materially larger future work; this ADR is stored rows a client polls.
2. **Both system-triggered and manually-authored.** A tenant invite has a natural trigger to hang a notification off of; "next session Saturday" or "research complete on this character" don't - those need an explicit human (a GM) to author one.
3. **Fan out at creation** - one row per recipient, written when the notification is created. Campaign/tenant rosters are small in practice; this keeps every read a single flat query.

Grounding turned up a genuine design win: `player`/`campaign_gm`/`membership`'s RLS policies were already widened once (`migrations/versions/a22dc991a926_*.py`) from plain `tenant_id = current_setting('app.tenant_id')` to `tenant_id = ... OR user_id = current_setting('app.user_id')`, specifically so `/me` could read a caller's own rows across every tenant without looping per-tenant to swap `app.tenant_id`. `app.user_id` is set on *every* authenticated request (`dependencies.get_current_user`), not just `/me`'s. Giving `notification` this same policy from day one, plus keeping every row fully self-contained (title/body copied in at creation, never joined from live Campaign/Character data at read time), means `GET /me/notifications` needs no per-tenant looping at all - unlike `_me_out`'s own more complex dance, which loops only because it *does* need to join out to tenant-scoped rows.

## Decision

`notification(id, user_id, tenant_id, scope, source_id, type, title, body, read_at, created_by, created_at)`. `scope` (`"platform"`/`"tenant"`/`"campaign"`/`"character"`) and `type` (free-form within scope, e.g. `"tenant_invite"`) are plain `TEXT`, not native enums - the same reasoning [ADR 0017](0017-information-and-payloads.md) already gives for `information.type`: caller-chosen categorization, not a fixed schema-level discriminant. `source_id` carries the campaign id / character entity id for deep-linking when relevant; `tenant_id` alone already identifies tenant scope, and platform scope needs neither.

RLS is baked in at table creation (not a follow-up `ALTER POLICY`, since the need is known up front), but split by command - unlike every other RLS'd table so far, this is the first table where the writer and the row's own "owner" are routinely different people. `SELECT`/`UPDATE` extend `a22dc991a926`'s self-access-OR-tenant-scoped shape with a third clause: `tenant_id = app.tenant_id OR user_id = app.user_id OR created_by = app.user_id`. That third clause exists purely because of a genuine Postgres RLS wrinkle, found the hard way: `INSERT ... RETURNING` (which SQLAlchemy's ORM always uses, to read the server-generated `id`/`created_at` back) re-checks the just-inserted row against the table's *own SELECT policy*, raising the same "violates row-level security policy" error if it doesn't satisfy it - even though the `INSERT`'s own `WITH CHECK` already passed. A platform notification (no `tenant_id`, written by an operator *for* a different recipient) satisfied neither of the first two clauses, so every platform-scope creation failed purely on the `RETURNING` read-back. Letting a caller also read back what they themselves just created (`created_by = app.user_id`) is a narrow, harmless extension - every notification's `created_by` is always the caller a scope's own authorization gate already approved, and the clause only matches while `app.user_id` still equals that same value, not a standing way to read someone else's notifications afterward.

`INSERT` itself stays permissive (`WITH CHECK (true)`): the row's `user_id` (the recipient) is essentially never `app.user_id` (the actor) either, so the insert-time check can't reasonably key off it. Authorization for *who* may create a notification is fully handled at the API layer, one gate per scope (see below) - RLS's job here is read-scoping, not write-authorization, matching this schema's own standing "defense in depth for a missed filter, not a replacement for filtering deliberately" principle ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)).

**Reading**: `GET /me/notifications` (optional `?unread_only=true`), `POST /me/notifications/{id}/read` (idempotent - re-marking an already-read one is a no-op, matching `grant_campaign_gm`'s own idempotent-PUT precedent). Explicitly filtered by `user_id == caller.id` in the query too, not left to RLS alone (defense in depth, [ADR 0002](0002-multi-tenancy-shared-schema-rls.md)'s standing rule) - an unknown or not-mine id both 404, collapsed indistinguishably.

**Creation**, one endpoint per scope rather than a single generic polymorphic route, each reusing that scope's own existing management authorization:

- `POST /admin/notifications` ([ADR 0057](0057-platform-operations.md)'s new role) - `recipient_user_id` **required**. No broadcast-to-every-user mechanism yet - a deliberately smaller, safer slice than a mass-mailing feature.
- `POST /tenants/{id}/notifications` - gated by `get_tenant_context` (any tenant-wide member, matching `update_tenant`). Omitted recipient broadcasts to the tenant's full roster (the same Membership+Player+CampaignGm union `list_tenant_roster` already computes).
- `POST .../campaigns/{id}/notifications` - gated by `can_manage_campaign` (matching `update_campaign`). Omitted recipient broadcasts to that campaign's Player + CampaignGm rows.
- `POST /tenants/{id}/characters/{id}/notifications` - gated by the same authorization `PATCH /characters/{id}`'s rename path already uses. Omitted recipient broadcasts to every player controlling that character via `CharacterPlayer` (roster reuse, ADR 0025 - a character rostered into two campaigns notifies every player controlling it in either).

**One system-triggered wiring** for this pass, to prove the pattern end to end rather than leave it purely theoretical: `create_membership` also creates a `scope="tenant", type="tenant_invite"` notification for the new member, in the same transaction.

## Not in scope

- Any real delivery channel (email, push, webhooks) - see context.
- An unread-count/badge endpoint, dismiss-without-reading, editing or deleting a notification, digesting/deduplication of repeated notifications.
- Broadcast-to-every-user at platform scope.
- A generic polymorphic creation endpoint - each scope's own route, deliberately.

## Consequences

- New migration + `models/notification.py`; `schemas/notifications.py` (`NotificationOut`, `NotificationCreate`).
- `exceptions.py`: `NotificationNotFoundError`.
- `routers/users.py`, `routers/tenants.py` (plus `create_membership`'s new wiring), `routers/campaigns.py`, `routers/characters.py`, `routers/admin.py` each gain their scope's notification route.
