# 0185 - Player self-service: the two switches

Status: accepted, decided with the maintainer on 2026-10-05.

Slice 1 of [RFC 0034](../rfcs/0034-player-self-service.md). Adds the two switches and nothing that reads them: no route behaves differently yet. Enforcement is slice 2, its own ADR.

## Context

A player can already make an instance for their own character from any item, with no way for a GM to switch it ([RFC 0034](../rfcs/0034-player-self-service.md) Context). The RFC decides on a campaign-wide setting, default on, and a per-player override, default none. This ADR is where they are stored, set and shown. Keeping it apart from enforcement means the schema and its routes can ship, and be seen in clients, before any player is refused anything.

## Decision

### Storage

- **`campaign.player_self_service`**: `boolean NOT NULL DEFAULT true`. Every existing campaign gets `true`.
- **`player.self_service`**: `boolean NULL`, no default. `NULL` is no override; `true` allows and `false` forbids that player whatever the campaign says. Every existing player gets `NULL`.

One migration, two columns, **no new table**: nothing for RLS, for [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)'s same-tenant keys or for `repository_access`'s two lists. A repository tenant holds no campaigns ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), so it has nothing to set. A repository copy does not copy campaigns, so the defaults apply.

### Setting them

Both need `can_manage_campaign` (a GM of the campaign, or a tenant `OWNER`/`ORGA`) and nobody else, a player included: a player does not set their own.

- **`PATCH .../campaigns/{id}`** takes `player_self_service`, a boolean. It is not nullable, so an explicit `null` is a `422`. The route's `If-Match` and `exclude_unset` handling are unchanged.
- **`PATCH .../campaigns/{campaign_id}/players/{player_id}`** is new, with a `PlayerUpdate` body of `self_service`: a boolean sets the override, an explicit `null` clears it, and leaving it out changes nothing. It takes `If-Match` against the player's `updated_at`, as `DELETE` of a player already does. `404` for a player not in that campaign.

### Recording it

Both are in the activity log ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md): it changes who can do what). The campaign's goes through the existing `campaign.updated` entry, which already names fields and never values; a player's is a new `player.updated` entry with `fields=self_service`.

### Showing it

- `CampaignOut` gains `player_self_service`.
- `PlayerSummaryOut` (and so `PlayerOut`) gains `self_service` (the override, nullable) and `self_service_effective`: the player's own value if set, else the campaign's. A client does not repeat the rule. Both ride the gate that already admits the roster read, and carry nothing about anyone else.
- `GET /me`'s `players[]` gets its own `self_service_effective` in slice 2, since it is the caller's own seats that matter to a client there.

All additive: no existing field changes, and a client that ignores them sees what it saw.

## Not in scope

- Reading either switch anywhere. `POST .../item-instances` and `from-pack` are exactly as before until slice 2.
- Seats across a character's campaigns, public-item checks and the `self-service-disabled` problem type: slice 2.
- Any client. account-hub's toggles come after slice 2.

## Consequences

- A GM can set the switches now and see them in the roster, but they do nothing yet. The slice is safe to ship alone; the tracking issue says so.
- Defaults leave every table as it is: self-service on for everyone, which is what the API did before.
- The first `PATCH` on a player. A player's other fields stay unwritable, as before.
