# RFC: A player-facing change feed in `apps/api`

Status: accepted - landed in [ADR 0099](../adr/0099-player-facing-change-feed.md)

Numbered 0020 originally; renumbered to 0022 alongside [RFC 0021](0021-loot-bot-player-toolkit.md), which it is the companion to (see that RFC's own history note).

## Context

[RFC 0021](0021-loot-bot-player-toolkit.md)'s `/changes` command answers "what happened to my own stuff since I last looked" — but with no API support it can only report actions the Discord bot itself recorded. Anything done through `apps/inventory-web`, `apps/account-hub`, or the API directly is invisible to it, and so are actions *other people* took that affected the player (a GM confiscating or awarding an item, another character giving them something) unless they happened to go through the bot.

The API has one change log today, and it is the wrong shape for this:

- [ADR 0063](../adr/0063-tenant-activity-log.md)'s `audit_log`/`GET /tenants/{id}/activity-log` is **tenant-admin only**, and deliberately narrow — only seven named mutation points (membership create/bulk-create/update/delete, campaign create/delete, GM grant/revoke) call `record_activity`. None of them are item-instance gives, moves, awards, confiscations, renames, merges, or splits.
- `updated_at` is a poor substitute: owner and container writes deliberately never bump it ([ADR 0051](../adr/0051-loot-bot-give-command.md)'s addendum), so an `updated_at`-based "changed since" would miss exactly the events a player cares about most.

This RFC is a proposal only. Nothing in [RFC 0021](0021-loot-bot-player-toolkit.md) depends on it landing.

## Decision (open — proposal, not consensus)

### A per-recipient change feed, not a widened tenant log

Model it on the notification system ([ADR 0058](../adr/0058-notifications.md)) rather than on `audit_log`: a mutation that changes something a *character* owns or carries writes one row per affected player/user at write time, so reads are a single flat, RLS-safe query with no reachability walk at read time.

- **Table**: `entity_change(id, tenant_id, user_id, character_entity_id, entity_id, kind, actor_user_id, occurred_at, ...)` — `kind` a small enum (`received`, `given_away`, `confiscated`, `moved`, `renamed`, `merged`, `split`, `noted`). `tenant_id` plus the same `FORCE ROW LEVEL SECURITY` policy convention as every tenant table ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)); a `user_id = app.user_id` self-access clause (the shape `notification`/`player` already use) so a player reads only their own rows.
- **Read**: `GET /me/changes?since=&limit=`, cursor-friendly, newest-first — no per-tenant looping, same reasoning as `GET /me/notifications`.
- **Write**: a shared `record_change` helper, called from the item-instance write paths that already exist (owner set, container set/bulk-move, split, merge, bulk-assign, rename, delete). This is the same "explicit named mutation points, not a catch-all" discipline ADR 0063 chose — deliberately not a DB trigger or middleware that would record every write.

### Visibility follows information visibility, not the actor

A change to a GM-private note must not appear in a player's feed, and a confiscation should say *that* an item was taken, not necessarily by whom if the actor is a GM acting privately. What a change row may reveal (the actor, the item's current name) is decided with [ADR 0040](../adr/0040-item-instance-read-visibility.md)'s owned-instance narrowing in mind — an open design question, not settled here.

## Open questions

- Whether `actor_user_id` is ever shown to the recipient, or stored only for the tenant activity log.
- Retention: this table grows with every item write. A TTL, a per-user cap, or aggregation of bulk operations into one row.
- Whether the tenant-admin `activity-log` should be re-expressed as a view over this table's writes (one recording path) or stay separate. Leaning separate, to keep ADR 0063's deliberately narrow scope intact.
- Backfill: none is possible for history that was never recorded; the feed starts empty.

## Alternatives considered

- **Widen ADR 0063's `audit_log` and add a player-scoped read.** Rejected as the default: it mixes an admin accountability log with a per-player experience feed, and forces read-time filtering by reachability for every row — precisely what ADR 0058's per-recipient fan-out avoided for notifications.
- **Reuse notifications for it.** Rejected: notifications are sender-authored, have a read/unread lifecycle, and would flood a player's inbox with every internal move.
- **Derive it from `updated_at`.** Rejected: owner/container writes don't bump it ([ADR 0051](../adr/0051-loot-bot-give-command.md)).

## Consequences (if adopted)

- One new tenant table with an RLS policy, one migration, one read route, and a `record_change` call added to each item-instance write path — real, cross-cutting `apps/api` work, hence its own RFC rather than a rider on the bot round.
- `apps/loot-bot`'s `/changes` would switch from bot-recorded state to this feed, becoming complete rather than visibly partial; `apps/account-hub` and `apps/inventory-web` could adopt it too.

## Not in scope

- A GM/admin-facing item history or full ownership provenance ledger — the "ledger of ownership" [docs/domain/client-views.md](../domain/client-views.md) records as a possible future direction is a superset of this and stays unscoped.
- Any implementation. Per [ADR 0070](../adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md), this gets no issue until it is decided.

## Resolution

Decided with the maintainer and recorded in [ADR 0099](../adr/0099-player-facing-change-feed.md): the actor is shown only when it is another player; a character's stuff is what it owns or carries; rows are kept 90 days; information changes are left out of the first slice; and the admin activity log stays separate. The context's claim that the activity log covers only seven mutation points is out of date since ADR 0084.
