import { LorenzoApiError } from './api';
import { getCatalogItem, getItemInstance } from './items';
import { resolveSlugs } from './slugs';
import type { ItemBase, ItemInstance } from './types';

export type FoundItem = { item: ItemBase | ItemInstance; instance: boolean };

const nowhere = () => new Error("There's no such item here, or it isn't one you can see.");

// The catalog item or instance a link names, by slug or by id (ADR 0107, 0116, 0135).
export async function findItem(
  tenantId: string,
  address: { slug: string | null; id: string | null },
): Promise<FoundItem> {
  if (address.slug) {
    // Any entity can hold a slug (ADR 0107); what it is says which endpoint shows it.
    const [found] = await resolveSlugs(tenantId, [address.slug]);

    if (found?.kinds.includes('item_instance')) {
      return { item: await getItemInstance(tenantId, found.entity_id), instance: true };
    }

    if (found?.kinds.includes('item')) {
      return { item: await getCatalogItem(tenantId, found.entity_id), instance: false };
    }

    throw nowhere();
  }

  // An id could be either: the catalog is tried first, and the instances only on a real 404, so
  // a network or auth error shows as itself.
  const id = address.id as string;

  try {
    return { item: await getCatalogItem(tenantId, id), instance: false };
  } catch (error) {
    if (!(error instanceof LorenzoApiError) || error.status !== 404) throw error;
  }

  try {
    return { item: await getItemInstance(tenantId, id), instance: true };
  } catch (error) {
    throw error instanceof LorenzoApiError && error.status === 404 ? nowhere() : error;
  }
}
