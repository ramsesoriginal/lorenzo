// One being (ADR 0271): finding it by slug or id, what its page shows about it, who plays it and
// what it carries. Each read is the API's own answer; who may see what is decided there.

import { isId } from './addresses';
import { client, LorenzoApiError, unwrap } from './api';
import { getEntityDetail } from './entities';
import { resolveSlugs } from './slugs';
import type { Character, EntityDetail, OwnedByResponse } from './types';

export type FoundBeing = { entityId: string };

const nowhere = () => new Error("There's no such being here, or it isn't one you can see.");

/** The being a link names, by slug or by id (ADR 0107, 0135). */
export async function findBeing(
  tenantId: string,
  address: { slug: string | null; id: string | null },
): Promise<FoundBeing> {
  if (address.slug) {
    const [found] = await resolveSlugs(tenantId, [address.slug]);

    if (found?.kinds.some((kind) => kind === 'character' || kind === 'being')) {
      return { entityId: found.entity_id };
    }

    throw nowhere();
  }

  const id = address.id;

  if (!id || !isId(id)) throw nowhere();

  // Read now so an id that is not a being, or not visible, fails here rather than half-drawn.
  const entity = await getEntityDetail(tenantId, id).catch((error: unknown) => {
    if (error instanceof LorenzoApiError && error.status === 404) throw nowhere();
    throw error;
  });

  if (!entity.kinds.some((kind) => kind === 'character' || kind === 'being')) throw nowhere();

  return { entityId: id };
}

/** The being's character row: who plays it. Null for a bare being, which has none (ADR 0031). */
export async function getCharacter(tenantId: string, entityId: string): Promise<Character | null> {
  try {
    return await unwrap(
      await client.GET('/tenants/{tenant_id}/characters/{character_id}', {
        params: { path: { tenant_id: tenantId, character_id: entityId } },
      }),
    );
  } catch (error) {
    if (error instanceof LorenzoApiError && error.status === 404) return null;
    throw error;
  }
}

/** Its own description's text, if the viewer may read one. */
export function descriptionOf(entity: Pick<EntityDetail, 'information'>): string {
  const info = entity.information.find((candidate) => candidate.type === 'description');
  const payload = info?.payloads.find((p) => p.kind === 'description');

  return payload?.kind === 'description' ? payload.content : '';
}

/** Its main picture's payload, if it has one the viewer may see (ADR 0237). */
export function pictureOf(entity: Pick<EntityDetail, 'information'>) {
  const info = entity.information.find((candidate) => candidate.type === 'main_picture');

  return info?.payloads.find((p) => p.kind === 'picture');
}

/** What the being owns, grouped by direct container (ADR 0020). */
export async function getOwned(tenantId: string, entityId: string): Promise<OwnedByResponse> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}', {
      params: { path: { tenant_id: tenantId, owner_entity_id: entityId } },
    }),
  );
}

export type InventorySummary = {
  /** Item instances, a stack counting once. */
  entries: number;
  /** Everything counted, a stack of five counting five. */
  pieces: number;
  /** The first few by name, with how many of each. */
  top: { name: string; quantity: number }[];
  /** How many entries `top` leaves out. */
  more: number;
};

/** A short account of an inventory for a being's page: counts and the first few names. */
export function summariseInventory(owned: OwnedByResponse, limit = 8): InventorySummary {
  const all = owned.groups.flatMap((group) => group.item_instances);
  const named = all
    .map((item) => ({ name: item.title, quantity: item.quantity ?? 1 }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return {
    entries: all.length,
    pieces: named.reduce((sum, item) => sum + item.quantity, 0),
    top: named.slice(0, limit),
    more: Math.max(0, named.length - limit),
  };
}
