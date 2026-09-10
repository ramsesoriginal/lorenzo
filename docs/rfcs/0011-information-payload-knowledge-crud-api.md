# RFC: Information, payload, and knowledge CRUD API

Status: proposed — deliberately unfinished, the same way [RFC 0008](0008-effective-stat-resolution.md) is; sketches the gap and its shape, doesn't resolve it

## Context

[RFC 0005](0005-item-and-item-instance-crud-api.md) named this gap explicitly and pointed here: "Creating/editing `entity_stat`, `stat_definition`, `stat_group`, or `information`/`payload` rows is a generic entity-attribute concern, not item-specific... A future 'generic entity attribute CRUD' RFC is the right home for it." [RFC 0008](0008-effective-stat-resolution.md) picked up the `entity_stat`/`stat_definition`/`stat_group` half; this is the other half — `information`, its four `payload` kinds, and `knowledge` — none of which have any write path today either.

Checking [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1) against every proposed RFC is what surfaced this precisely: the milestone needs a public description ("An ornate sword...") authored on an entity, a GM-only secret ("cursed" — which per [ADR 0028](../adr/0028-knowledge-and-group-membership.md) needs no `Knowledge` row at all, just `is_public=false` and no knower — GM-only is the default), and a *character-specific* secret ("magical," known specifically to Alice) — which needs both an `Information` row and a `Knowledge` row linking Alice's character to it. Nothing creates any of the three today. This is the domain's own central payoff — [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md)'s "different observers know different things" — and it currently has no way to be authored at all, only read (and only once something else, by hand against the database, puts rows there).

## Decision (sketched, not designed)

**`Information`+`Payload` creation is nested under the entity it describes** — `/tenants/{tenant_id}/entities/{entity_id}/information`, matching how `Information` already has no existence independent of an `entity_id` ([ADR 0017](../adr/0017-information-and-payloads.md)). One call creates the `Information` row (`title`, `type`, `is_public`) plus exactly one typed `Payload` (`description`/`number`/`picture`/`document`) — mirroring [RFC 0005](0005-item-and-item-instance-crud-api.md)'s "one transaction, one coherent unit" precedent (instantiate creating `Entity`+`ItemInstance`+`EntityPrototype` together), not two separate calls that could leave an `Information` row with no `Payload` yet.

**`Knowledge` creation attaches a knower to an existing `Information` row** — a knower is a character, a group, or a player ([RFC 0001](0001-core-domain-data-model.md)'s three cases, `is_public` covering the fourth). Where exactly this lives (nested under the information resource? its own top-level collection?) isn't decided.

## Not in scope / not designed

**The actual authorization model** — the hard part, genuinely undesigned. [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md) names four text tiers (GM-only, everyone, a subset, **player-authored**) — the last one implies a player can author their own content (a journal entry about their own character), which doesn't obviously fit [RFC 0005](0005-item-and-item-instance-crud-api.md)'s self-or-managed shape the way item ownership does. Authoring a GM-only secret and authoring your own character's public journal entry are clearly different permissions; nothing here says where the line is.

**Binary payload upload mechanics.** `payload_picture`/`payload_document` store raw bytes directly ([ADR 0017](../adr/0017-information-and-payloads.md)) — every write convention so far ([RFC 0005](0005-item-and-item-instance-crud-api.md)) assumes a JSON body, which means base64-encoding binary content or switching to `multipart/form-data` for just these two payload kinds. Genuinely different from anything decided so far; not resolved here.

**Editing/revoking `Knowledge`** (a GM changing their mind about who knows what) and **whether granting knowledge needs the knower's own awareness or consent** (presumably not — it's data, not a notification — but not written down as a decision).

**Everything RFC 0008 already excludes** (multi-game-system stats, the "facts"/campaign-relevance idea from [RFC 0001](0001-core-domain-data-model.md)'s open question #4) — unaffected by this RFC either.

## Consequences

- No schema change — `information`, `payload` (+ its four extensions), `knowledge`, `group_member` all already exist exactly as this needs them.
- Until this is built, the milestone's central claim — that the same item can mean something different to Alice, Bob, and the GM — has nothing behind it to actually author; the read side ([ADR 0028](../adr/0028-knowledge-and-group-membership.md), [RFC 0009](0009-campaign-scoped-gm-visibility.md)) is ready for data that nothing can yet create.
- Depends on [RFC 0005](0005-item-and-item-instance-crud-api.md)'s write-API conventions (status codes, `If-Match`, typed problems) the same way [RFC 0006](0006-campaign-crud-api.md)/[RFC 0007](0007-user-player-character-crud-api.md) do — not re-litigated here, whenever this is actually picked up.
