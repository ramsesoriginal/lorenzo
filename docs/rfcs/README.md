# RFCs

For proposals that aren't decided yet — bigger than an ADR captures, or genuinely open questions. An RFC becomes one or more ADRs once decided (or gets dropped).

To start one: copy an [ADR](../adr/0000-template.md)'s structure but title it "RFC: \<question\>" and leave Decision open until there's consensus.

- [0001 - Core domain data model (entity/component architecture)](0001-core-domain-data-model.md) — proposed, pending the knowledge/redaction and multi-game-system questions; tenancy-split resolved for every table the items slice uses, narrowed to just the not-yet-designed repository-reference mechanism
- [0002 - Campaign, player, and character model](0002-campaign-player-character-model.md) — accepted, landed in full across ADR 0021-0026; revises ADR 0010's tenant definition
- [0003 - Tenant and campaign read REST API](0003-tenant-campaign-read-api.md) — proposed, introduces `get_campaign_context` to close the tenant-wide-Membership gap ADR 0022/0026 flagged
- [0004 - User, membership, player, character, and GM read REST API](0004-user-membership-player-character-gm-read-api.md) — proposed, builds on RFC 0003
- [0005 - Item and item-instance CRUD API](0005-item-and-item-instance-crud-api.md) — proposed, the first write surface in this codebase; defines cross-cutting write-API conventions
- [0006 - Campaign CRUD API](0006-campaign-crud-api.md) — proposed, builds on RFC 0003/0005
