# 0010 - User, tenant, and membership model

Status: accepted, refined by [RFC 0002](../rfcs/0002-campaign-player-character-model.md) (proposed)

## Context

A user can own a tenant (as the person running that world) and, independently, be a member of any number of other tenants (as a participant) — e.g. player "C" might play in GM X's tenant and GM Z's tenant simultaneously. [ADR 0002](0002-multi-tenancy-shared-schema-rls.md) originally assumed one tenant per user (a JWT carrying a single `tenant_id`), which doesn't hold once membership is many-to-many.

## Decision

Three entities, not two:

- **User** — global identity, not tenant-scoped. Holds only what's domain-relevant plus a link back to the identity provider's subject id (see [ADR 0009](0009-identity-provider-authgear.md)) — no passwords, no OAuth tokens, none of that lives here.
- **Tenant** — a world: the persistent shared setting a GM or team runs, the existing RLS boundary from ADR 0002. A tenant can host multiple campaigns — see [RFC 0002](../rfcs/0002-campaign-player-character-model.md), which defines campaign, player, and character as concepts nested *inside* a tenant, not synonymous with it.
- **Membership** — joins User to Tenant with a `role` column. Originally scoped as `owner`/`player`/`co-gm`/`spectator`; refined by RFC 0002 now that campaign is a distinct concept — tenant-level `role` means tenant-wide administrative access (`owner`, `orga`), while GMing or playing a specific campaign is its own campaign-scoped relation, not a tenant Membership role. Ownership is still a role value, not a separate `Tenant.owner_id` column: one table answers every "is this user allowed to administer this tenant" question, and ownership transfer is just changing which membership row has `role=owner`.

A request now needs to say which tenant it's acting *in*: a user picks/switches into a tenant (validated against their own memberships), and that becomes the session's `SET LOCAL app.tenant_id` — separate from "list every tenant this user belongs to," which is an unscoped query against `Membership` keyed by user, not tenant.

## Consequences

- Supersedes the one-tenant-per-user assumption in ADR 0002's original wording (now updated).
- A platform-admin flag on `User`, separate from tenant-scoped roles, is anticipated for future cross-tenant moderation/support access — not needed yet, deliberately not designed further now.
- Invitation flow (how a GM adds a player to their tenant) is a real open question, not decided here.
- Refined by [RFC 0002](../rfcs/0002-campaign-player-character-model.md): tenant is a world, not a campaign; campaign, player, and GM are new campaign-scoped concepts that don't live on this Membership table.
