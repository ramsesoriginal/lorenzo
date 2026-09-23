# 0099 - A player-facing change feed

Status: accepted

## Context

Accepts [RFC 0022](../rfcs/0022-player-facing-change-feed-api.md). A player wants to know what happened to their characters' belongings since they last looked: a gift from another player, an award, a confiscation, a split stack. The API has no answer. `updated_at` can't provide one (owner and container writes deliberately never bump it, [ADR 0051](0051-loot-bot-give-command.md)'s addendum), and loot-bot's `/changes` ([ADR 0097](0097-loot-bot-changes.md)) can only report what went through the bot.

One part of the RFC's context is out of date: it argued against the tenant activity log because that recorded only seven mutation points. Since [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md) every item-instance mutation is logged there. The RFC's conclusion still holds, though: that log is an administrators' accountability record, it names every actor, and serving it per player would mean filtering by reachability on every read. A per-recipient feed, fanned out at write time like notifications ([ADR 0058](0058-notifications.md)), is still the right shape. Its recording calls sit beside ADR 0084's.

The RFC's open questions were decided with the maintainer:

1. **The actor is shown only when it is another player.** A GM's or administrator's action says what happened, not who did it.
2. **"My stuff" is what a character owns or carries** - not ownership alone.
3. **Rows are kept 90 days.**
4. **Information changes ("a new note about your item") are not in this slice.**

## Decision

### Table

`entity_change(id, tenant_id, user_id, character_entity_id, entity_id, kind, actor_user_id, actor_visible, entity_name, detail, occurred_at)`.

- `user_id` is the recipient. `character_entity_id` is which of their characters the change concerns. `entity_id` is the item; it is **not** a foreign key, so a row survives the item's deletion (a `deleted` row has to).
- `kind`: `received`, `given_away`, `moved`, `split`, `merged`, `renamed`, `deleted`. Plain text, like `notification.type`.
- `entity_name`: the item's name when the change happened, copied in, so a row reads correctly after a rename or deletion. `detail`: short, id-and-count-only context (`quantity=2`), never authored content.
- `actor_user_id` is always stored (`ON DELETE SET NULL`). `actor_visible` records whether the recipient may see it, decided at write time (below). The API returns the actor only when it is visible.
- `user_id` is `ON DELETE CASCADE`: a feed belongs to its recipient.

### Row-level security: readable only by the recipient

Stricter than `notification`'s policy, which also admits anyone holding the tenant context. This is a personal feed, so:

- **SELECT and DELETE**: `user_id = app.user_id` only.
- **INSERT**: `tenant_id = app.tenant_id` - a write happens inside the mutating route's tenant context.

`notification` needed a `created_by` clause because SQLAlchemy's `INSERT ... RETURNING` re-checks the new row against the SELECT policy (ADR 0058). The feed avoids that by generating `id` and `occurred_at` in Python, so there is nothing server-generated to read back and no `RETURNING`.

### Who gets a row: owned or carried, before and after

For every recorded change, compute the **holders** of the item before and after it: the characters that own it, contain it at any depth, or own something that contains it at any depth (a sword in a bag that a character owns, lying in a room, is still that character's). The containment walk reuses `entity_access.containing_ancestors_ids`.

- A character holding it only **after** gets `received`; one holding it only **before** gets `given_away`. One holding it both times gets the change's own kind (`moved`, `split`, `merged`, `renamed`, `deleted`).
- Each holder's rows go to every user whose player controls that character (`CharacterPlayer`), once per user per character.
- **The actor gets no row for their own change.** Nobody needs to be told what they just did.
- **Moving a container records a row for the container only**, not for each thing inside it: the contents' holders didn't change unless the container changed hands, and fanning out per item could turn one move into hundreds of rows. When a container *does* change hands, its contents are still not listed individually; `received`/`given_away` on the container is the record.
- **Bulk operations write one row per affected item**, not one per call: the feed is about items, and a player cares which ones.

### When the actor is visible

`actor_visible` is true unless, in that tenant at that moment, the actor holds a `CampaignGm` row or a tenant-wide OWNER/ORGA membership. A GM confiscating an item shows as "taken from you", never "taken by your GM". A player who is also a GM is treated as a GM throughout the tenant - the safe direction to err.

### Recording points

A shared `record_change` helper, called beside `record_activity` at the item-instance write paths: create (a `received` for a new instance created straight into someone's possession), owner set/clear, container set/clear, bulk-assign, bulk-move, split, merge, rename, delete. Explicit named points, not a trigger - ADR 0063's discipline. A change that alters nothing (an idempotent repeat) records nothing.

### Reading and retention

`GET /me/changes` returns the caller's own rows across every tenant, newest first, paginated, with an optional inclusive `since` exactly like `GET /me/notifications` ([ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md)). Each row carries its tenant, character, item id and name, kind, detail, time, and the actor id only if visible.

Rows older than 90 days are deleted. There is no job runner ([ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md)), so the read route deletes the caller's own expired rows before listing them - one indexed delete, allowed by the DELETE policy. A user who never reads keeps their old rows until they do; that is bounded by their own activity and harmless.

## Not in scope

- **Information changes** (a `noted` kind). Whether a recipient may see a new piece of information depends on visibility that can change after the fact; it needs its own decision.
- Listing a moved or handed-over container's contents individually.
- Any change to the tenant activity log, which stays separate (the RFC's leaning).
- Backfill: history that was never recorded can't be reconstructed. The feed starts empty.
- Push or real-time delivery.

## Consequences

- One migration and model (`entity_change`), a `record_change` helper called from the item-instance router, `GET /me/changes`, and tests for each recording point, the holder rules, actor visibility, RLS and retention.
- Every item-instance write gains a containment walk up the tree, before and after. It is one recursive query each, already used by GM reachability.
- loot-bot's `/changes` can switch to this feed and drop its "only changes made through this bot" note, as ADR 0097 planned; account-hub and inventory-web could adopt it too.
