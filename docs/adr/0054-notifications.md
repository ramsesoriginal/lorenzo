# 0054 - Notifications: platform/tenant/campaign/character scope, in-app inbox

Status: accepted

## Context

Users want to be notified from four different scopes: the platform itself, a tenant (invited to one), a campaign (a scheduled session), or a specific character (an in-game event). Three decisions were made with the user before this ADR:

1. **In-app inbox only for v1.** This codebase has zero outbound-delivery infrastructure - no email sending, no push, no websockets (Authgear handles its own login-related email, this app never sends any). Building a real delivery channel is separate, materially larger future work; this ADR is stored rows a client polls.
2. **Both system-triggered and manually-authored.** A tenant invite has a natural trigger to hang a notification off of; "next session Saturday" or "research complete on this character" don't - those need an explicit human (a GM) to author one.
3. **Fan out at creation** - one row per recipient, written when the notification is created. Campaign/tenant rosters are small in practice; this keeps every read a single flat query.

Grounding turned up a genuine design win: `player`/`campaign_gm`/`membership`'s RLS policies were already widened once (`migrations/versions/a22dc991a926_*.py`) from plain `tenant_id = current_setting('app.tenant_id')` to `tenant_id = ... OR user_id = current_setting('app.user_id')`, specifically so `/me` could read a caller's own rows across every tenant without looping per-tenant to swap `app.tenant_id`. `app.user_id` is set on *every* authenticated request (`dependencies.get_current_user`), not just `/me`'s. Giving `notification` this same policy from day one, plus keeping every row fully self-contained (title/body copied in at creation, never joined from live Campaign/Character data at read time), means `GET /me/notifications` needs no per-tenant looping at all - unlike `_me_out`'s own more complex dance, which loops only because it *does* need to join out to tenant-scoped rows.

## Decision

`notification(id, user_id, tenant_id, scope, source_id, type, title, body, read_at, created_by, created_at)`. `scope` (`"platform"`/`"tenant"`/`"campaign"`/`"character"`) and `type` (free-form within scope, e.g. `"tenant_invite"`) are plain `TEXT`, not native enums - the same reasoning [ADR 0017](0017-information-and-payloads.md) already gives for `information.type`: caller-chosen categorization, not a fixed schema-level discriminant. `source_id` carries the campaign id / character entity id for deep-linking when relevant; `tenant_id` alone already identifies tenant scope, and platform scope needs neither.

RLS is baked in at table creation (not a follow-up `ALTER POLICY`, since the need is known up front): `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid` - `a22dc991a926`'s exact shape. A platform-scoped row (`tenant_id IS NULL`) still satisfies the policy through its own `user_id` match.

**Reading**: `GET /me/notifications` (optional `?unread_only=true`), `POST /me/notifications/{id}/read` (idempotent - re-marking an already-read one is a no-op, matching `grant_campaign_gm`'s own idempotent-PUT precedent). Explicitly filtered by `user_id == caller.id` in the query too, not left to RLS alone (defense in depth, [ADR 0002](0002-multi-tenancy-shared-schema-rls.md)'s standing rule) - an unknown or not-mine id both 404, collapsed indistinguishably.

**Creation**, one endpoint per scope rather than a single generic polymorphic route, each reusing that scope's own existing management authorization:

- `POST /admin/notifications` ([ADR 0053](0053-platform-operations.md)'s new role) - `recipient_user_id` **required**. No broadcast-to-every-user mechanism yet - a deliberately smaller, safer slice than a mass-mailing feature.
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
