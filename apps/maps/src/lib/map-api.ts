// What the Map pages ask of the API (ADR 0338, 0351, 0353): reads of placements, and the writes of
// the editor. A write is never optimistic: the page changes with what the API gave back.
import { client, fetchAllPages, type Schema, unwrap } from './api';
import type { PlacementState } from './history';

export type Header = Schema<'MapOut'>;
export type Row = Schema<'PlacementOut'>;
export type Stub = Schema<'LocationStub'>;

export type EntryChoice = { id: string; name: string; kinds: string[] };

// The renderer lays out every placement it is given; a Map holds at most this many (ADR 0337) and
// the view says so when it cannot show them all.
export const VISIBLE_LIMIT = 5000;

/** The placements of a Map in pages until it is complete or the limit is reached. */
export async function readPlacements(tenant: string, id: string) {
  const rows: Row[] = [];
  let cursor: string | undefined;
  let more = false;
  do {
    const page = await unwrap(
      await client.GET('/tenants/{tenant_id}/maps/{map_id}/placements', {
        params: {
          path: { tenant_id: tenant, map_id: id },
          query: cursor ? { cursor } : {},
        },
        // Revalidated on every open: what a person may read is never decided by a freshness window.
        cache: 'no-cache',
      }),
    );
    rows.push(...page.items);
    cursor = page.next_cursor ?? undefined;
    if (cursor && rows.length >= VISIBLE_LIMIT) {
      more = true;
      break;
    }
  } while (cursor);
  return { rows, more };
}

export type PlacementBody = PlacementState & { geometry: Record<string, unknown> };

export async function putPlacement(
  tenant: string,
  map: string,
  entry: string,
  body: PlacementState,
) {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { tenant_id: tenant, map_id: map, entry_id: entry } },
      body: {
        geometry: body.geometry as Record<string, unknown>,
        role: body.role,
        style: (body.style ?? null) as Record<string, unknown> | null,
        z: body.z,
      },
    }),
  );
}

export async function removePlacement(tenant: string, map: string, entry: string) {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { tenant_id: tenant, map_id: map, entry_id: entry } },
    }),
  );
}

export type BatchWrite = {
  put?: ({ entry_id: string } & PlacementState)[];
  remove?: string[];
};

/** Writes and removals as one: all of them or none (ADR 0351). */
export async function batchPlacements(tenant: string, map: string, writes: BatchWrite) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/maps/{map_id}/placements/batch', {
      params: { path: { tenant_id: tenant, map_id: map } },
      body: {
        put: (writes.put ?? []).map((item) => ({
          entry_id: item.entry_id,
          geometry: item.geometry as Record<string, unknown>,
          role: item.role,
          style: (item.style ?? null) as Record<string, unknown> | null,
          z: item.z,
        })),
        remove: writes.remove ?? [],
      },
    }),
  );
}

export type LinkRow = Schema<'LinkOut'>;

/** What the places drawn on a Map lead to (ADR 0364); none when it cannot be read. */
export async function readLinks(tenant: string, map: string): Promise<LinkRow[]> {
  try {
    const body = await unwrap(
      await client.GET('/tenants/{tenant_id}/maps/{map_id}/links', {
        params: { path: { tenant_id: tenant, map_id: map } },
        cache: 'no-cache',
      }),
    );
    return body.items;
  } catch {
    return [];
  }
}

/** Entries the person may see, found by name. */
export async function findEntries(tenant: string, query: string): Promise<EntryChoice[]> {
  const page = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: tenant }, query: { q: query, size: 12 } },
      cache: 'no-cache',
    }),
  );
  return page.items.map((entry) => ({ id: entry.id, name: entry.name, kinds: entry.kinds }));
}

/** Locations the person may see, found by name. */
export async function findLocations(tenant: string, query: string) {
  const page = await unwrap(
    await client.GET('/tenants/{tenant_id}/locations', {
      params: { path: { tenant_id: tenant }, query: { q: query, size: 12 } },
      cache: 'no-cache',
    }),
  );
  return page.items;
}

export async function makeLocation(tenant: string, name: string, isPublic: boolean) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/locations', {
      params: { path: { tenant_id: tenant } },
      body: { id: crypto.randomUUID(), name, is_public: isPublic },
    }),
  );
}

/** The Locations the person sees directly inside one. */
export async function partsOf(tenant: string, id: string): Promise<Stub[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/locations/{location_id}/parts', {
        params: { path: { tenant_id: tenant, location_id: id }, query: { page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  );
}

export function rowState(row: Row): PlacementState {
  return { geometry: row.geometry, role: row.role ?? null, style: row.style ?? null, z: row.z };
}
