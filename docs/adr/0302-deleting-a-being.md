# 0302 - Deleting a being and settling its inventory

Status: accepted, decided with the maintainer on 2026-10-15.

## Context

Beings has no way to delete a being. Deleting a character through the existing character endpoint only demotes it (ADR 0036); deleting an entry does not settle its inventory. The maintainer asked for permanent deletion with explicit ownership and carrying rules.

## Decision

- Add `DELETE /tenants/{tenant_id}/beings/{entity_id}`. It removes the entry, not just its character or being kind. The entity cascade removes its stats, stat groups, information and payloads, slug, roster, knowledge and other references. The existing character demotion endpoint keeps its meaning.
- Use the destructive character guard: direct character control, or management of every campaign it belongs to. For a being with no campaign, use the existing NPC management rule, including `npcs_shared_with_gms` and authorship. Tenant participation, tenant-scoped lookups and RLS remain required. Accept `If-Match` and reject a stale value before writing.
- Compose the existing entry deletion guards for other kinds: a campaign entry, an inventory item, or a catalog prototype still used by instances refuses deletion. A character is allowed here because this endpoint deletes it deliberately.
- In one transaction, delete item instances both owned and carried by this being. Carrying includes nested containers, stopping at another being. Items only carried survive with their owners; items only owned survive with ownership cleared and become uncarried, even if someone else carried them. Preserve surviving containers and their contents; detach surviving items from deleted containers. When detaching a stack into no container, preserve its count by splitting it into single items as existing inventory operations do (ADR 0132).
- Record the deletion and affected inventory changes through the existing activity log and change feed. Remove only this tenant's data. There is no recursive deletion of another being and no deletion of copies in other libraries.
- In Beings, offer a danger-styled `Delete being` button in Edit mode to the usual editors. Confirmation names the being, describes the inventory consequences and says it cannot be undone. Disable repeat submission, show API refusals, and return to the library's beings list only after success. API authorization remains authoritative.

## Consequences

Deletion is permanent and atomic. The inventory rules are explicit instead of relying on ownership and containment foreign keys alone. No new tables or migration are needed. Tests cover permission boundaries, cleanup and surviving inventory, including nested containers and stack quantities, plus confirmation, cancellation and navigation in the real API browser suite.
