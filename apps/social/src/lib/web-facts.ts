import type { GraphGroup } from '@lorenzo/graph-renderer';
import { client, fetchAllPages, unwrap } from './api';
import { readWindow } from './matrix-api';
import { listTypes } from './types-api';

/** The most entries one read of types can cover, and the most edges asked about one chain at a time. */
const WINDOW = 100;
const CHAINS = 60;

/**
 * What a web's lines need beyond the graph read: each relationship's type (its label says it, never a
 * line style of its own) and which hold through a chain (dashed). Both are conveniences read after the
 * drawing is possible; a web too big for them is drawn without, and a read that fails leaves it as is.
 */
export async function edgeFacts(
  tenant: string,
  members: readonly string[],
  edges: readonly { id: string }[],
): Promise<{ typeOf: Map<string, string>; through: Set<string> }> {
  const typeOf = new Map<string, string>();
  const through = new Set<string>();
  if (members.length > 0 && members.length <= WINDOW) {
    const types = await listTypes(tenant).catch(() => []);
    await Promise.all(
      types.map(async (type) => {
        const ties = await readWindow(tenant, members, members, type.id).catch(() => []);
        for (const tie of ties) typeOf.set(tie.id, type.name);
      }),
    );
  }
  if (edges.length <= CHAINS) {
    await Promise.all(
      edges.map(async (edge) => {
        const read = await client
          .GET('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
            params: { path: { tenant_id: tenant, relationship_id: edge.id } },
            cache: 'no-cache',
          })
          .catch(() => null);
        if (read?.response.ok && (read.data?.via.length ?? 0) > 0) through.add(edge.id);
      }),
    );
  }
  return { typeOf, through };
}

/** The groups with at least two members in the web: soft outlines round them, read when asked for. */
export async function loadGroups(tenant: string, inWeb: readonly string[]): Promise<GraphGroup[]> {
  const here = new Set(inWeb);
  const all = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/groups', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  ).catch(() => []);
  const found: GraphGroup[] = [];
  for (const group of all.slice(0, 40)) {
    const members = await client
      .GET('/tenants/{tenant_id}/groups/{group_entity_id}/members', {
        params: { path: { tenant_id: tenant, group_entity_id: group.id } },
        cache: 'no-cache',
      })
      .then((r) => (r.response.ok ? (r.data ?? []) : []))
      .catch(() => []);
    const ours = members.map((m) => m.id).filter((id) => here.has(id));
    if (ours.length >= 2) found.push({ id: group.id, name: group.name, members: ours });
  }
  return found;
}
