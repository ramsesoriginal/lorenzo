# RFC: Attribution — `created_by`/`updated_by`

Status: proposed — cross-cutting schema addition, needed now that RFC 0005/0006/0007 introduce this codebase's first write paths; needs a migration

## Context

Checked directly while reviewing [RFC 0005](0005-item-and-item-instance-crud-api.md): no table anywhere in this schema has a `created_by`/`updated_by` column, and RFC 0005 itself explicitly waved this off as out of scope ("`created_by`/`updated_by` don't exist on any table today and nothing here adds them"). That was fine when nothing wrote anything — every table's `created_at`/`updated_at` pair already recorded *when*, and *who* was a non-question with no write API to ask it about. [RFC 0005](0005-item-and-item-instance-crud-api.md)/[RFC 0006](0006-campaign-crud-api.md)/[RFC 0007](0007-user-player-character-crud-api.md) change that: real users can now create and edit campaigns, items, memberships, players, and characters, and "who did this" becomes a real, worth-asking question the moment that's true, not before.

## Decision

### Which tables get the pair, and why

Only tables with an actual write path through RFC 0005/0006/0007 — matching how `created_at`/`updated_at` itself already follows "every table except pure join/extension tables," not the genuinely-no-exceptions rule `tenant_id`/RLS uses:

- **`entity`** — covers `item`/`item_instance`/`being` for free: none of the three ever exists independently of the `entity` row created alongside it in the same transaction ([RFC 0005](0005-item-and-item-instance-crud-api.md)'s instantiate flow, [RFC 0007](0007-user-player-character-crud-api.md)'s character-create flow), so their own creator/editor *is* the entity's — a separate column on each would just be a guaranteed-identical copy.
- **`campaign`** — written by [RFC 0006](0006-campaign-crud-api.md).
- **`membership`** — written by [RFC 0007](0007-user-player-character-crud-api.md); knowing who granted tenant-wide access is a real accountability question for exactly the kind of administrative action this table represents.
- **`player`** — written by [RFC 0007](0007-user-player-character-crud-api.md). Gets both columns despite that RFC having no `PATCH /players` at all (`updated_by` would just always equal `created_by` in practice) — matching how `player.updated_at` already exists today for the identical never-actually-updated reason; consistency with an established precedent, not a wasted column.
- **`character`** — **does not** piggyback on `entity`/`being` the way `item`/`item_instance` do, and needs its own pair. [RFC 0007](0007-user-player-character-crud-api.md)'s `PUT /characters/{id}` can attach a `character` row to a `being` that already existed, created earlier by a *different* user — the entity's own `created_by` would then record the wrong thing (who made the being exist at all, not who promoted it into a tracked character). This is the one genuine exception to the piggyback rule above, and worth calling out precisely rather than assuming every extension table behaves like `item`/`item_instance`.
- **`campaign_gm`/`tenant_admin_campaign_opt_out`** — both genuinely granted/revoked via `PUT`/`DELETE` in [RFC 0006](0006-campaign-crud-api.md) (caught only on a second pass writing this RFC's own follow-ups — an earlier draft wrongly lumped these into "no write path" below, which was never true). **`created_by` only, no `updated_by`** — a deliberate lighter touch than every other table above: neither row is ever updated in place, only created or deleted (a row's mere existence already *is* the grant/opt-out, per [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)'s own design), so there's nothing for `updated_by` to ever mean. Neither table has `created_at`/`updated_at` today either; this adds a bare `created_at` alongside `created_by` — the minimum needed to answer "who granted this, and when," not the full four-column set every table above gets.
- **`tenant`** — moved here from "explicitly not covered" once [RFC 0012](0012-tenant-creation-and-update-api.md) gave it an actual write path; gets the full pair, same shape as `campaign`/`membership`/`player`.

**Explicitly not covered, with reasons, not an oversight:**

- **`app_user`** — auto-provisioned by the auth pipeline itself ([ADR 0023](../adr/0023-authgear-token-verification.md)); "created by" would always just mean "themselves," a self-referential fact not worth a column.
- **`containment`/`ownership`** — both genuinely written by [RFC 0005](0005-item-and-item-instance-crud-api.md)'s move/transfer actions, deliberately excluded anyway: [docs/domain/client-views.md](../domain/client-views.md)'s own "future direction" section already names "a ledger of ownership — tracking ownership provenance over time, not just current possession" as a real, explicitly deferred idea. Neither table has `created_at`/`updated_at` today either; bolting on half of a provenance ledger (who, but not really a full history of when and how many times) here would pre-empt that fuller idea rather than build toward it. Revisit as part of that ledger, not piecemeal here.
- **`information`/`payload` (+ its four extensions)/`knowledge`** — [RFC 0011](0011-information-payload-knowledge-crud-api.md) proposes a write path but deliberately doesn't design it far enough to implement attribution against yet.
- **`stat_group`/`stat_definition`/`entity_stat`** — likewise, [RFC 0008](0008-effective-stat-resolution.md) names stat-writing as unfinished work, not a designed one.
- **`entity_prototype`/`entity_stat_group`/`character_player`/`group_member`** — no write path proposed anywhere yet. Add attribution to any of the tables in this list once — and only once — something actually designs and writes to it, matching this codebase's own discipline of not adding columns ahead of an actual need.

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

**Nullable, unlike `CreatedAt`/`UpdatedAt`** — a deliberate divergence, not an inconsistency: a timestamp can never become unknown, but an attribution can, the moment the attributed user deletes their own account ([RFC 0007](0007-user-player-character-crud-api.md)'s `DELETE /me`). `ON DELETE SET NULL` matches every other "the referenced actor is gone, the row survives" case already in this schema (`being`/`character.owner_player_id`, historically `item_instance.owner_entity_id`) — losing your account clears attribution on everything you ever touched, it doesn't delete any of it.

`updated_by` is set to the same value as `created_by` at creation time (mirroring how `updated_at` already starts equal to `created_at`), then reassigned on every subsequent write. **Set explicitly by each write route from `CurrentUser.id`, not by an ORM-level event listener or a session-scoped "current user" context** — matches this codebase's existing preference for explicit, debuggable resolution over implicit magic ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)'s own stated reasoning for `from_x` classmethods over validator-soup). A hook would save a handful of one-line assignments at the cost of a new, harder-to-trace mechanism — not a good trade at this scale.

**`entity.updated_by` is only touched by writes that modify the entity or its concrete-type row directly** (a rename via `PATCH /items/{id}`/`PATCH /item-instances/{id}`, say) — **not** by [RFC 0005](0005-item-and-item-instance-crud-api.md)'s move/transfer-ownership actions, which only ever touch `containment`/`ownership`, deliberately excluded above. Moving an item doesn't count as "updating" it in the sense this column tracks; conflating the two would blur exactly the distinction the containment/ownership exclusion above is trying to preserve.

No reverse "everything this user created" collections proposed on `User` (`User.created_campaigns` and four siblings) — nothing has asked for that view yet; easy to add later without touching anything decided here.

## Not in scope

**Exposing `created_by`/`updated_by` in REST responses** — that's each affected read schema's own job: [RFC 0003](0003-tenant-campaign-read-api.md)'s `CampaignOut`/`TenantOut`, [RFC 0004](0004-user-membership-player-character-gm-read-api.md)'s `PlayerOut`/`PlayerDetailOut`/`CharacterOut`/`MembershipRosterEntryOut`/`PlayerRosterEntryOut`/`GmRosterEntryOut` (the last one `created_by` only, per the create-only shape above), and [RFC 0005](0005-item-and-item-instance-crud-api.md)'s `ItemOut`/`ItemInstanceOut` all need a follow-up pass adding the fields (as bare `user_id`s — resolving one to a display name is a client concern; this API has never stored one, [ADR 0009](../adr/0009-identity-provider-authgear.md)). Flagged for each, not fixed here, to keep this RFC scoped to the schema addition itself.

**A full activity/audit log** (every historical change, not just the latest writer) — a genuinely bigger feature than two columns; `created_by`/`updated_by` answer "who's responsible for the current state," not "what happened, in order." Worth naming as the natural next step if that's ever actually wanted, not designed here.

## Open questions

**Should `character`'s `created_by` distinguish "who created the underlying `being`" from "who promoted it"?** As decided above, `character.created_by` records the *promoter* specifically (the only new fact this table's existence adds) — `entity.created_by` still separately records whoever made the `being` exist at all. Two different, both-meaningful facts, on two different tables; not collapsed into one.

## Consequences

- **Needs a migration**: `entity`, `campaign`, `membership`, `player`, `tenant` each gain `created_by`/`updated_by`; `character` gains the same pair, for its own distinct reason; `campaign_gm`/`tenant_admin_campaign_opt_out` each gain `created_by` **and** `created_at` only (no `updated_by`/`updated_at` — see above). All `created_by`/`updated_by` nullable, `ON DELETE SET NULL`, indexed.
- **`docs/architecture/diagrams/domain-model-er.md` needs an update** — eight tables gaining new columns, plus (for `character`) the reasoning for why it doesn't just inherit `entity`'s, and (for `campaign_gm`/`tenant_admin_campaign_opt_out`) why they get a lighter create-only pair instead of the full four columns.
- [RFC 0003](0003-tenant-campaign-read-api.md), [RFC 0004](0004-user-membership-player-character-gm-read-api.md), and [RFC 0005](0005-item-and-item-instance-crud-api.md) each need the read-schema follow-up named in Not in scope above; so does [RFC 0012](0012-tenant-creation-and-update-api.md)'s `TenantOut`, though that RFC already accounts for it directly rather than needing a separate retrofit.
- [RFC 0005](0005-item-and-item-instance-crud-api.md)'s create/rename endpoints and [RFC 0006](0006-campaign-crud-api.md)/[RFC 0007](0007-user-player-character-crud-api.md)'s create/update/promote/grant endpoints all need to actually set these fields — a small, mechanical addition to each write path, not a redesign of any of them.
- [RFC 0007](0007-user-player-character-crud-api.md)'s `DELETE /me` cascade description needs one more line: every `created_by`/`updated_by` this user ever left behind, across every table above, is also set `NULL` — the same `SET NULL` shape already described there for `Character.owner_player_id`, just one more column family affected by it.
- [RFC 0005](0005-item-and-item-instance-crud-api.md)'s own line ("`created_by`/`updated_by` don't exist... and nothing here adds them") is superseded by this RFC — fixed there directly, so a future reader doesn't take that sentence as still current.
