# 0038 - Information, payload, and knowledge CRUD API

Status: accepted

## Context

GitHub milestone #1's own central claim - that the same item can mean something different to Alice, Bob, and the GM - had nothing behind it to actually author: `information`, its four `payload` kinds, and `knowledge` had a fully-built read side ([ADR 0028](0028-knowledge-and-group-membership.md), [ADR 0035](0035-campaign-scoped-gm-visibility.md)) but no write path at all. This ADR accepts [RFC 0011](../rfcs/0011-information-payload-knowledge-crud-api.md), which is deliberately unfinished - it sketches the shape but explicitly leaves "the actual authorization model" and "binary payload upload mechanics" undesigned. This ADR resolves both, scoped to exactly what the milestone needs, the same way [ADR 0037](0037-effective-stat-resolution.md) picked up RFC 0008's identically unfinished state.

## Decision

### Scope: description payloads only, nested creation

`POST /tenants/{tenant_id}/entities/{entity_id}/information` creates `Information` + one `Payload` + one `PayloadDescription` in a single transaction (`InformationCreate{title, type, is_public, content, locale}`). `payload_number`/`picture`/`document` creation stays out of scope - RFC 0011's own flagged "binary payload upload mechanics... not resolved here" gap; a JSON body has nowhere to put raw bytes without base64 or multipart, neither decided, and the milestone's three facts are all plain text.

### Authorization: self-or-managed, the same shape as RFC 0005/RFC 0008

Reuses `entity_access.can_self_manage_entity` + the owner's-campaign fallback + the tenant-wide ownerless fallback - the identical predicate `routers/entity_stats.py`'s `_authorize_entity_stat_write` already established for RFC 0008, now a third copy (`routers/entities.py`'s `authorize_entity_write`, exported for `routers/information.py` to reuse rather than keeping a fourth). **Deliberately not tiered further**: RFC 0011 names four visibility tiers in the domain (GM-only, everyone, a subset, player-authored) but explicitly doesn't say which callers may author which tier. This ADR doesn't resolve that either - anyone who can manage an entity can author information of *any* visibility on it, including a GM-only secret about their own gear. In practice a GM is the one who actually authors GM-only secrets, but nothing here enforces it structurally. Flagged as a real, deliberate narrowing, not an oversight - a finer per-tier model is real future work.

### Knowledge as a sub-resource, not its own top-level collection

`PUT`/`DELETE /tenants/{tenant_id}/information/{information_id}/knowers/{knower_entity_id}` - resolving RFC 0011's own "where exactly this lives - nested under the information resource? its own top-level collection? - isn't decided" by nesting it under `information`, mirroring `routers/characters.py`'s roster-link sub-resource shape for the identical "genuinely n:m, one link at a time" reasoning. Idempotent `PUT` (mirrors `grant_campaign_gm`/`set_item_instance_owner`); `DELETE` returns `200` + the parent `InformationOut`, not `204` (mirrors `remove_character_player`). Authorized against **the information's own `entity_id`** (the thing it describes), not the knower being granted - granting knowledge about entity X needs the same standing as authoring information about X, not standing over whichever character/group is receiving it. `knower_entity_id` is validated only as "a real entity in this tenant" - RFC 0001's own looseness between character/group knowers (disambiguated only by whether a `Being` row also exists). Player-knowers (`knower_player_id`) are out of scope - the milestone only needs a character knower (Alice).

**The GM-only case needs no `Knowledge` row at all** - `is_public=false` with zero knowers is already GM-default per [ADR 0028](0028-knowledge-and-group-membership.md); a campaign's GM sees it purely through [ADR 0035](0035-campaign-scoped-gm-visibility.md)'s reachability walk. Only the character-specific secret (Alice knowing "magical") needs an actual grant.

### A real gap found and fixed: `GET /entities/{id}` was Membership-gated

Not asked for by RFC 0011, but required by the milestone: `routers/entities.py`'s router-level dependency moved from `get_tenant_context` to `get_tenant_or_404` + an explicit `is_tenant_participant` check on the two pre-existing `GET` routes, mirroring `routers/item_instances.py`'s identical ADR 0032 revision. Neither Xavier/Yvonne (plain Players) nor Zorro (a `CampaignGm` with no tenant-wide Membership) could otherwise reach `GET /entities/{id}` at all, regardless of what `information_visibility` would have shown them.

**`GET /entities/{id}`, not `GET /item-instances/{id}`, is what actually proves the milestone's three-observer scenario.** `Information` carries `UniqueConstraint(entity_id, type)` - the public description, Alice's secret, and the GM's secret are three separate `Information` rows on the same entity, and that constraint forces each to have a *different* `type` string. `EntityViewMixin.descriptions()` (which backs `ItemOut`/`ItemInstanceOut`) only ever surfaces the single row typed exactly `"description"` - by design, unchanged here, since `title`/`description_id` in `v_item`/`v_item_instance` are meant to be one canonical headline, not every visible fact. `EntityDetailOut.information`, by contrast, already lists *every* `Information` row the caller's `information_visibility` allows, regardless of `type` - built that way since [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md), unmodified here. This ADR's own tests use `GET /entities/{id}` for exactly this reason, not because `ItemOut.descriptions` was broadened.

### A real, more consequential bug found and fixed: `get_tenant_or_404` lost RLS scoping under a genuine token

**This affects every already-merged router using `get_tenant_or_404` as a bare router-level dependency** - `item_instances.py`, `characters.py`, `entity_stats.py`, and (via `get_campaign_context`, which depends on it) `campaigns.py` - not just this ADR's own new code. `get_current_user` performs its own internal commit (the auto-provisioning upsert, [ADR 0023](0023-authgear-token-verification.md)), which ends whatever transaction was active. `get_tenant_or_404` didn't take `user` as a parameter, so FastAPI had no dependency-graph reason to resolve `get_current_user` (and let its commit land) *before* `get_tenant_or_404`'s own `set_tenant_rls_context` call - and it resolved it *after*, for every affected router, silently discarding `app.tenant_id` before the route body's first query. Every existing test using the `client` fixture's fake `get_current_user` (which never commits) was structurally incapable of catching this; it only surfaced building this ADR's own participant-gate fix, via a real-token (`raw_client`) test against `entities.py`.

Fixed at the root: `get_tenant_or_404` now takes `user: CurrentUser` too (unused in its own body, present purely to force resolution order) - `get_tenant_context` never had this problem, incidentally, since it already took `user` for its own membership check. A new regression test (`tests/test_auth.py`) proves the fix generalizes by exercising `item_instances.py` - a router this ADR never otherwise touches - with a genuine verified token.

## Not in scope

Everything RFC 0011 itself excludes: binary payload upload mechanics, editing/revoking `Knowledge` beyond the plain sub-resource delete now built, per-tier authorization finer than self-or-managed, and everything RFC 0008 already excludes (multi-game-system stats, the "facts"/campaign-relevance idea).

## Consequences

- No migration - `information`, `payload` (+ its four extensions), `knowledge`, `group_member` all already exist exactly as this needs them, per RFC 0011's own text.
- GitHub milestone #1's scenario is now fully authorable and provable end to end through the real API - the last remaining piece after [ADR 0032](0032-item-and-item-instance-crud-api.md)-[0037](0037-effective-stat-resolution.md).
- `dependencies.get_tenant_or_404`'s fix is a real, if narrow, behavior change for every router that uses it - re-verified via the full existing suite (unaffected) plus the new regression test above.
- `routers/entities.py.authorize_entity_write` is now the third copy of the self-or-managed-over-any-entity shape (after `item_instances.py`'s instance-specific version and `entity_stats.py`'s own). A shared `entity_access.can_manage_entity` is a reasonable follow-up once a fourth consumer shows up - not extracted speculatively here.
