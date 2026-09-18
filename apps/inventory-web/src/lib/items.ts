import { apiDelete, apiFetch, apiPost, apiPut } from './api';
import type { CatalogItem, ItemInstance, OwnedByResponse, Page } from './types';

// Grouped by *direct* container only (ADR 0020's task brief) - a null
// group for items with no container, one group per occupied container.
// Not recursive: a container that's itself empty produces no group of its
// own, but still appears as a card inside whichever group holds it.
export async function getOwnedItemInstances(
  tenantId: string,
  ownerEntityId: string,
): Promise<OwnedByResponse> {
  return apiFetch<OwnedByResponse>(`/tenants/${tenantId}/item-instances/owned-by/${ownerEntityId}`);
}

export async function setContainer(
  tenantId: string,
  entityId: string,
  containerEntityId: string,
): Promise<void> {
  await apiPut(`/tenants/${tenantId}/item-instances/${entityId}/container`, {
    container_entity_id: containerEntityId,
  });
}

export async function clearContainer(tenantId: string, entityId: string): Promise<void> {
  await apiDelete(`/tenants/${tenantId}/item-instances/${entityId}/container`);
}

// PUT /item-instances/{id}/owner - "assign to a being" (ADR: owner as a
// singular sub-resource, not an RPC verb - replaces whoever owned it
// before, same shape whether this is a first assignment or a reassign).
export async function setOwner(
  tenantId: string,
  entityId: string,
  ownerCharacterId: string,
): Promise<void> {
  await apiPut(`/tenants/${tenantId}/item-instances/${entityId}/owner`, {
    owner_character_id: ownerCharacterId,
  });
}

// The item catalog (prototypes), not instances - GET /tenants/{t}/items,
// with an optional server-side search (`q`) for the parent-item picker.
export async function listCatalogItems(tenantId: string, query = ''): Promise<Page<CatalogItem>> {
  const qs = query ? `?q=${encodeURIComponent(query)}` : '';
  return apiFetch<Page<CatalogItem>>(`/tenants/${tenantId}/items${qs}`);
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
  return apiPost<CatalogItem>(`/tenants/${tenantId}/items`, {
    name,
    prototype_ids: prototypeIds,
  });
}

// POST /tenants/{t}/item-instances - instantiates a new item instance from
// a single catalog prototype (one prototype per instance, unlike catalog
// items themselves) and assigns it straight to a character in the same
// call, mirroring apps/loot-bot's /award.
export async function createItemInstance(
  tenantId: string,
  prototypeId: string,
  ownerCharacterId: string,
): Promise<ItemInstance> {
  return apiPost<ItemInstance>(`/tenants/${tenantId}/item-instances`, {
    prototype_id: prototypeId,
    owner_character_id: ownerCharacterId,
  });
}
