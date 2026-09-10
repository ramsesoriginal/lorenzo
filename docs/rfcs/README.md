# RFCs

For proposals that aren't decided yet — bigger than an ADR captures, or genuinely open questions. An RFC becomes one or more ADRs once decided (or gets dropped).

To start one: copy an [ADR](../adr/0000-template.md)'s structure but title it "RFC: \<question\>" and leave Decision open until there's consensus.

- [0001 - Core domain data model (entity/component architecture)](0001-core-domain-data-model.md) — proposed, pending the knowledge/redaction and multi-game-system questions; tenancy-split resolved for every table the items slice uses, narrowed to just the not-yet-designed repository-reference mechanism
- [0002 - Campaign, player, and character model](0002-campaign-player-character-model.md) — accepted, landed in full across ADR 0021-0026; revises ADR 0010's tenant definition
- [0003 - Tenant and campaign read REST API](0003-tenant-campaign-read-api.md) — proposed, now needs a migration (slug/description on both, secret + an attached entity on campaign) and revises `can_access_campaign` to admit OWNER
- [0004 - User, membership, player, character, and GM read REST API](0004-user-membership-player-character-gm-read-api.md) — proposed, now needs a migration too: a new `character` table layered under `being` (plus a `v_character` view), `/me`'s players carry their characters, and the tenant roster is a discriminated union of owner/orga, players, and GMs
- [0005 - Item and item-instance CRUD API](0005-item-and-item-instance-crud-api.md) — proposed, the first write surface in this codebase; defines cross-cutting write-API conventions; instance authorization revised to self-or-managed (RFC 0007's pattern via RFC 0009's reachability walk), superseding the original `is_tenant_participant` draft; depends on RFC 0010 for `entity.created_by`/`updated_by`
- [0006 - Campaign CRUD API](0006-campaign-crud-api.md) — proposed, builds on RFC 0003/0005
- [0007 - User, player, and character CRUD API](0007-user-player-character-crud-api.md) — proposed, builds on RFC 0004/0005; resolves ADR 0010's invitation-flow question with a known limitation; `DELETE /characters/{id}` demotes rather than destroys, `PUT /characters/{id}` promotes an existing being the other way
- [0008 - Effective stat resolution over the prototype graph](0008-effective-stat-resolution.md) — proposed, deliberately short; schedules building RFC 0001's already-decided resolution rule, never implemented since ADR 0015 deferred it
- [0009 - Campaign-scoped GM visibility](0009-campaign-scoped-gm-visibility.md) — proposed, revises `information_visibility.py`'s ORGA-only bypass so a campaign's own GM sees GM-only secrets without needing tenant-wide Membership
- [0010 - Attribution — created_by/updated_by](0010-created-by-updated-by-attribution.md) — proposed, adds the pair to entity/campaign/membership/player/character (plus a lighter created_by-only version on campaign_gm/tenant_admin_campaign_opt_out) now that RFC 0005/0006/0007 introduce the first write paths
