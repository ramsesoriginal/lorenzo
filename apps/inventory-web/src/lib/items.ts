import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import type {
  BulkResultItem,
  CatalogItem,
  EntityDetail,
  ItemInstance,
  OwnedByResponse,
  PrototypeAncestor,
} from './types';

// Grouped by *direct* container only (ADR 0020's task brief) - a null
// group for items with no container, one group per occupied container.
// Not recursive: a container that's itself empty produces no group of its
// own, but still appears as a card inside whichever group holds it.
export async function getOwnedItemInstances(
  tenantId: string,
  ownerEntityId: string,
): Promise<OwnedByResponse> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}', {
      params: { path: { tenant_id: tenantId, owner_entity_id: ownerEntityId } },
    }),
  );
}

// GET /tenants/{t}/item-instances/unowned (ADR 0077) - item instances with
// no owner at all, grouped by direct container the same way owned-by/{id}
// is - the identical OwnedByResponse shape, so the board's rendering works
// unmodified for "browse unclaimed loot" too.
export async function getUnownedItemInstances(tenantId: string): Promise<OwnedByResponse> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/item-instances/unowned', {
      params: { path: { tenant_id: tenantId } },
    }),
  );
}

export async function setContainer(
  tenantId: string,
  entityId: string,
  containerEntityId: string,
): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/item-instances/{entity_id}/container', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { container_entity_id: containerEntityId },
    }),
  );
}

export async function clearContainer(tenantId: string, entityId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/item-instances/{entity_id}/container', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// PUT /item-instances/{id}/owner - "assign to a being" (ADR: owner as a
// singular sub-resource, not an RPC verb - replaces whoever owned it
// before, same shape whether this is a first assignment or a reassign).
export async function setOwner(
  tenantId: string,
  entityId: string,
  ownerCharacterId: string,
): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/item-instances/{entity_id}/owner', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { owner_character_id: ownerCharacterId },
    }),
  );
}

// DELETE /item-instances/{id}/owner - clears ownership; an instance
// doesn't have to have one (ItemInstanceCreate.owner_character_id is
// optional too - see createItemInstance below).
export async function unsetOwner(tenantId: string, entityId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/item-instances/{entity_id}/owner', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// The item catalog (prototypes), not instances - GET /tenants/{t}/items,
// with an optional server-side search (`q`) for the parent-item picker.
// Follows every page (fetchAllPages) rather than returning just the
// first - a tenant with more than one page's worth of catalog items (the
// API's own default page size is 50, ADR 0020) would otherwise silently
// vanish past whatever page happened to come back first.
export async function listCatalogItems(tenantId: string, query = ''): Promise<CatalogItem[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/items', {
        params: {
          path: { tenant_id: tenantId },
          query: { q: query || undefined, page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

// GET /tenants/{t}/items?prototype_id=&recursive= (ADR 0073) - the reverse
// lookup: "what's built on top of X." recursive=true (unlike this
// endpoint's own default) since this is the edit panel's "used as a
// prototype by" complement to the board's own exhaustive ancestry view -
// both show the full picture, not just the direct edge. Same
// every-page-not-just-the-first treatment as listCatalogItems above - a
// widely-reused prototype is exactly the case likeliest to exceed one page.
export async function listItemsUsingPrototype(
  tenantId: string,
  prototypeId: string,
): Promise<CatalogItem[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/items', {
        params: {
          path: { tenant_id: tenantId },
          query: { prototype_id: prototypeId, recursive: true, page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

// POST /tenants/{t}/items - creates a catalog item (prototype), with zero
// or more existing catalog items as its own prototypes (multi-parent
// inheritance - Entity + Item + one EntityPrototype row per parent, one
// transaction server-side).
export async function createCatalogItem(
  tenantId: string,
  name: string,
  prototypeIds: string[],
): Promise<CatalogItem> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: tenantId } },
      body: { name, prototype_ids: prototypeIds },
    }),
  );
}

// PATCH /tenants/{t}/items/{id} - only `name` is mutable through this
// endpoint (apps/api's own ItemUpdate docstring: "nothing else on a bare
// Item row exists to update"). Prototypes are a separate sub-resource
// (setItemPrototypes below, ADR 0072).
export async function updateCatalogItem(
  tenantId: string,
  entityId: string,
  name: string,
): Promise<CatalogItem> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { name },
    }),
  );
}

// PUT /tenants/{t}/items/{id}/prototypes (ADR 0072) - full replacement,
// same shape as ItemCreate.prototype_ids: the given list becomes the
// item's complete new set of direct prototypes.
export async function setItemPrototypes(
  tenantId: string,
  entityId: string,
  prototypeIds: string[],
): Promise<CatalogItem> {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/items/{entity_id}/prototypes', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { prototype_ids: prototypeIds },
    }),
  );
}

// GET /tenants/{t}/entities/{id} - what ItemOut doesn't carry: the entity's
// own `name` (ItemOut.title is its description's title, ADR 0019), its
// prototypes with names (ItemOut.prototype_ids is id-only), and its stats
// with whether each is its own (ADR 0111).
export async function getEntityDetail(tenantId: string, entityId: string): Promise<EntityDetail> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// DELETE /tenants/{t}/items/{id} - 204 No Content on success.
export async function deleteCatalogItem(tenantId: string, entityId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// DELETE /tenants/{t}/item-instances/{id} - 204 No Content on success.
export async function deleteItemInstance(tenantId: string, entityId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/item-instances/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// GET /tenants/{t}/items/{id} - a single catalog item by id, used to look
// up a display name for an item-instance's direct prototype (the board's
// ancestry view knows only the id, from ItemInstanceOut.prototype_ids).
export async function getCatalogItem(tenantId: string, entityId: string): Promise<CatalogItem> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// GET /tenants/{t}/item-instances/{id} - a single item instance by id, for
// the standalone shareable item page (which doesn't know in advance
// whether a given id is a catalog item or an instance).
export async function getItemInstance(tenantId: string, entityId: string): Promise<ItemInstance> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/item-instances/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

// GET /tenants/{t}/items/{id}/prototypes/ancestry (ADR 0073) - every
// transitive ancestor of a *catalog item*, not an instance (ancestry is
// scoped to Item entities - an ItemInstance's own direct prototype has to
// be resolved first, then this walks that catalog item's own chain).
export async function getItemAncestry(
  tenantId: string,
  itemEntityId: string,
): Promise<PrototypeAncestor[]> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/items/{entity_id}/prototypes/ancestry', {
      params: { path: { tenant_id: tenantId, entity_id: itemEntityId } },
    }),
  );
}

// POST /tenants/{t}/item-instances - instantiates a new item instance from
// a single catalog prototype (one prototype per instance, unlike catalog
// items themselves), optionally assigning it straight to a character in
// the same call (mirroring apps/loot-bot's /award) and/or giving it a
// slug (ADR 0043) - both optional, an instance doesn't have to have an
// owner, and slug can only be set here, at creation (ItemInstanceUpdate
// doesn't include it).
export async function createItemInstance(
  tenantId: string,
  prototypeId: string,
  ownerCharacterId?: string,
  slug?: string,
): Promise<ItemInstance> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/item-instances', {
      params: { path: { tenant_id: tenantId } },
      body: {
        prototype_id: prototypeId,
        ...(ownerCharacterId ? { owner_character_id: ownerCharacterId } : {}),
        ...(slug ? { slug } : {}),
      },
    }),
  );
}

// POST /item-instances/{id}/split (ADR 0041/0044) - splits `quantity`
// units *off* into a new sibling instance; the source must currently hold
// strictly more than that. ownerCharacterId is optional - given, the new
// split-off instance gets that owner instead of copying the source's
// current one (ADR 0044); omitted keeps ADR 0041's original behavior.
export async function splitItemInstance(
  tenantId: string,
  entityId: string,
  quantity: number,
  ownerCharacterId?: string,
): Promise<ItemInstance> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/item-instances/{entity_id}/split', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { quantity, ...(ownerCharacterId ? { owner_character_id: ownerCharacterId } : {}) },
    }),
  );
}

// POST /item-instances/{id}/merge (ADR 0044) - entityId is fully consumed
// into intoEntityId (the surviving stack) and then deleted.
export async function mergeItemInstance(
  tenantId: string,
  entityId: string,
  intoEntityId: string,
): Promise<ItemInstance> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/item-instances/{entity_id}/merge', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { into_entity_id: intoEntityId },
    }),
  );
}

// POST /item-instances/bulk-assign (ADR 0044) - never all-or-nothing, one
// BulkResultItem per input entry regardless of outcome. quantity given
// (per entry) delegates server-side to split-with-owner instead of
// reassigning the whole stack - lets a single call give part of one
// player's stack away while the rest stays put.
export async function bulkAssignItemInstances(
  tenantId: string,
  items: { entityId: string; ownerCharacterId: string; quantity?: number }[],
): Promise<BulkResultItem[]> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/item-instances/bulk-assign', {
      params: { path: { tenant_id: tenantId } },
      body: items.map((item) => ({
        entity_id: item.entityId,
        owner_character_id: item.ownerCharacterId,
        ...(item.quantity ? { quantity: item.quantity } : {}),
      })),
    }),
  );
}

// POST /item-instances/bulk-move (ADR 0065) - the `items` mode (move
// exactly this list), not the `from_container_entity_id` mode (move
// everything in a source container) - a multi-select drag-and-drop always
// knows exactly which items it's moving. Never all-or-nothing, same
// per-entry BulkResultItem shape as bulk-assign. No "move to no
// container" mode - to_container_entity_id is required server-side;
// clearing several items' containers at once still needs one
// clearContainer call per item.
export async function bulkMoveItemInstances(
  tenantId: string,
  toContainerEntityId: string,
  entityIds: string[],
): Promise<BulkResultItem[]> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/item-instances/bulk-move', {
      params: { path: { tenant_id: tenantId } },
      body: {
        to_container_entity_id: toContainerEntityId,
        items: entityIds.map((entityId) => ({ entity_id: entityId })),
      },
    }),
  );
}
