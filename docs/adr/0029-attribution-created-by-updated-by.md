# 0029 - Attribution: created_by/updated_by

Status: accepted

## Context

No table anywhere in this schema has a `created_by`/`updated_by` column. That was fine when nothing wrote anything - every table's `created_at`/`updated_at` pair already recorded *when*, and *who* was a non-question with no write API to ask it about. [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md)/[RFC 0006](../rfcs/0006-campaign-crud-api.md)/[RFC 0007](../rfcs/0007-user-player-character-crud-api.md)/[RFC 0012](../rfcs/0012-tenant-creation-and-update-api.md) change that: real users are about to be able to create and edit tenants, campaigns, items, memberships, players, and characters, and "who did this" becomes a real, worth-asking question the moment that's true, not before. [RFC 0010](../rfcs/0010-created-by-updated-by-attribution.md) is the proposal this ADR accepts, close to verbatim - see it for the full reasoning trail.

## Decision

### Which tables get the pair, and why

Only tables with an actual write path through the milestone's REST-surface work - matching how `created_at`/`updated_at` itself already follows "every table except pure join/extension tables," not the genuinely-no-exceptions rule `tenant_id`/RLS uses:

- **`entity`** - covers `item`/`item_instance`/`being` for free: none of the three ever exists independently of the `entity` row created alongside it in the same transaction, so their own creator/editor *is* the entity's - a separate column on each would just be a guaranteed-identical copy.
- **`campaign`** - written once campaign CRUD lands.
- **`membership`** - written once membership CRUD lands; knowing who granted tenant-wide access is a real accountability question for exactly the kind of administrative action this table represents.
- **`player`** - written once player CRUD lands. Gets both columns despite there being no `PATCH /players` at all (`updated_by` would just always equal `created_by` in practice) - matching how `player.updated_at` already exists today for the identical never-actually-updated reason; consistency with an established precedent, not a wasted column.
- **`character`** - **does not** piggyback on `entity`/`being` the way `item`/`item_instance` do, and needs its own pair. Character CRUD's promote action can attach a `character` row to a `being` that already existed, created earlier by a *different* user - the entity's own `created_by` would then record the wrong thing (who made the being exist at all, not who promoted it into a tracked character). This is the one genuine exception to the piggyback rule above, worth calling out precisely rather than assuming every extension table behaves like `item`/`item_instance`.
- **`campaign_gm`/`tenant_admin_campaign_opt_out`** - both genuinely granted/revoked via `PUT`/`DELETE` once campaign CRUD lands. **`created_by` only, no `updated_by`** - a deliberate lighter touch than every other table above: neither row is ever updated in place, only created or deleted (a row's mere existence already *is* the grant/opt-out, per [ADR 0026](0026-campaign-gm-orga-and-access-rule.md)'s own design), so there's nothing for `updated_by` to ever mean. Neither table has `created_at`/`updated_at` today either; this adds a bare `created_at` alongside `created_by` - the minimum needed to answer "who granted this, and when," not the full four-column set every table above gets.
- **`tenant`** - gets an actual write path once tenant creation lands; gets the full pair, same shape as `campaign`/`membership`/`player`.

**Explicitly not covered, with reasons, not an oversight:**

- **`app_user`** - auto-provisioned by the auth pipeline itself ([ADR 0023](0023-authgear-token-verification.md)); "created by" would always just mean "themselves," a self-referential fact not worth a column.
- **`containment`/`ownership`** - both will genuinely get write paths, deliberately excluded anyway: [docs/domain/client-views.md](../domain/client-views.md)'s own "future direction" section already names "a ledger of ownership - tracking ownership provenance over time, not just current possession" as a real, explicitly deferred idea. Neither table has `created_at`/`updated_at` today either; bolting on half of a provenance ledger (who, but not really a full history of when and how many times) here would pre-empt that fuller idea rather than build toward it. Revisit as part of that ledger, not piecemeal here.
- **`information`/`payload` (+ its four extensions)/`knowledge`** - a write path is coming, but [RFC 0011](../rfcs/0011-information-payload-knowledge-crud-api.md) is deliberately scoped down for this milestone (see [ADR 0038](0038-information-payload-knowledge-crud-api.md) once it lands) rather than designed far enough to implement attribution against yet.
- **`stat_group`/`stat_definition`/`entity_stat`** - likewise scoped down for this milestone (see [ADR 0037](0037-effective-stat-resolution.md) once it lands), not a designed attribution story yet.
- **`entity_prototype`/`character_player`** - both are pure composite-PK join tables with no data beyond the relationship itself ([ADR 0015](0015-entity-prototype.md)'s own words for `entity_prototype`), neither has `created_at`/`updated_at` today either, and bolting on half an attribution story ahead of a fuller "who changed this relationship, and when" mechanism would pre-empt that rather than build toward it - same reasoning as `containment`/`ownership` above, not "no write path" (both will have one).
- **`entity_stat_group`/`group_member`** - genuinely no write path proposed anywhere yet. Add attribution to either once - and only once - something actually designs and writes to it, matching this codebase's own discipline of not adding columns ahead of an actual need.

### Shape

`Annotated` column aliases in `db.py`, matching `UuidPk`/`TenantFk`/`CreatedAt`/`UpdatedAt`'s existing pattern:

```python
CreatedBy = Annotated[
    uuid.UUID | None, mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
]
UpdatedBy = Annotated[
    uuid.UUID | None, mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
]
```

**Nullable, unlike `CreatedAt`/`UpdatedAt`** - a deliberate divergence, not an inconsistency: a timestamp can never become unknown, but an attribution can, the moment the attributed user deletes their own account (`DELETE /me`, once user CRUD lands). `ON DELETE SET NULL` matches every other "the referenced actor is gone, the row survives" case already in this schema (`Being`/`Character.owner_player_id`, historically `item_instance.owner_entity_id`) - losing your account clears attribution on everything you ever touched, it doesn't delete any of it.

**No `relationship()` to `User` on the attributed side** - a deliberate omission, not an oversight. Nothing so far needs to navigate `entity.creator`/`.updater` as an object; every consumer that's actually been asked for wants a bare `user_id` back over REST (see Not in scope, below). Adding a relationship nobody traverses would just be another `lazy="raise_on_sql"` trap for every existing eager-load chain to remember, for zero benefit. Add one later if something concrete needs it.

`updated_by` is set to the same value as `created_by` at creation time (mirroring how `updated_at` already starts equal to `created_at`), then reassigned on every subsequent write. **Set explicitly by each write route from `CurrentUser.id`, not by an ORM-level event listener or a session-scoped "current user" context** - matches this codebase's existing preference for explicit, debuggable resolution over implicit magic ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)'s own stated reasoning for `from_x` classmethods over validator-soup). A hook would save a handful of one-line assignments at the cost of a new, harder-to-trace mechanism - not a good trade at this scale.

**`entity.updated_by` is only touched by writes that modify the entity or its concrete-type row directly** (a rename, say) - **not** by move/transfer-ownership actions, which only ever touch `containment`/`ownership`, deliberately excluded above. Moving an item doesn't count as "updating" it in the sense this column tracks; conflating the two would blur exactly the distinction the containment/ownership exclusion above is trying to preserve.

No reverse "everything this user created" collections proposed on `User` (`User.created_campaigns` and four siblings) - nothing has asked for that view yet; easy to add later without touching anything decided here.

### Phased implementation, not one migration

This ADR records the whole policy at once, but each table's columns land in the same migration that already touches that table for its own reason, not a single upfront sweep - adding `character.created_by` before `character` itself exists isn't possible anyway:

| Table(s) | Lands with |
| --- | --- |
| `entity` | This slice (standalone - nothing else needs to exist first) |
| `campaign` | Tenant/campaign read API ([ADR 0030](0030-tenant-campaign-read-api.md)) |
| `character` | Character table + read API ([ADR 0031](0031-character-table-and-read-api.md)) |
| `tenant` | Tenant creation/update API ([ADR 0033](0033-tenant-creation-and-update-api.md)) |
| `campaign_gm`, `tenant_admin_campaign_opt_out` | Campaign CRUD ([ADR 0034](0034-campaign-crud-api.md)) |
| `membership`, `player` | User/player/character CRUD ([ADR 0036](0036-user-player-character-crud-api.md)) |

## Not in scope

**Exposing `created_by`/`updated_by` in REST responses** - that's each affected read schema's own job, tackled as part of whichever ADR above actually introduces that schema. Bare `user_id`s only - resolving one to a display name is a client concern; this API has never stored one ([ADR 0009](0009-identity-provider-authgear.md)).

**A full activity/audit log** (every historical change, not just the latest writer) - a genuinely bigger feature than two columns; `created_by`/`updated_by` answer "who's responsible for the current state," not "what happened, in order." Worth naming as the natural next step if that's ever actually wanted, not designed here.

## Consequences

- `entity` gains `created_by`/`updated_by`: nullable, `ON DELETE SET NULL`, indexed (this slice). The remaining six tables gain theirs incrementally per the phased table above.
- `docs/architecture/diagrams/domain-model-er.md` needs an update per table, as each lands - not all at once.
- Every write path introduced by the milestone's remaining ADRs (0030-0038) needs to actually set these fields on create/update - a small, mechanical addition to each, not a redesign of any of them.
- `DELETE /me` (once it lands) needs to null every `created_by`/`updated_by` this user ever left behind, across every table above - the same `SET NULL` shape already established for `Being`/`Character.owner_player_id`, just one more column family affected by it.
