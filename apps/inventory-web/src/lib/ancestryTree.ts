import { getCatalogItem, getItemAncestry } from './items';

// An item and what it inherits from: its direct prototypes, each with theirs.
export type AncestryNode = { name: string; parents: AncestryNode[] };

type Nodes = Map<string, { name: string; parentIds: string[] }>;

// The parents of `rootId`, each with its own, from entity_id -> {name, parentIds}. Prototype
// graphs are DAGs, not always chains (ADR 0073): an item reachable through two parents
// (diamond inheritance) appears twice, once per real path, rather than being merged into one
// misleading line. `seenOnPath` stops a cycle recursing forever; the API's insert-time
// trigger (ADR 0015) already prevents real ones, so this is only defensive.
export function parentsOf(
  rootId: string,
  nodes: Nodes,
  seenOnPath: ReadonlySet<string> = new Set(),
): AncestryNode[] {
  const node = nodes.get(rootId);

  if (!node || seenOnPath.has(rootId)) return [];

  const path = new Set(seenOnPath).add(rootId);

  return node.parentIds.flatMap((parentId) => {
    const parent = nodes.get(parentId);

    return parent ? [{ name: parent.name, parents: parentsOf(parentId, nodes, path) }] : [];
  });
}

// The full transitive ancestry (ADR 0073) of a catalog item. An instance has none of its own:
// pass its direct prototype's id (ItemInstanceOut.prototype_ids[0]).
export async function fetchAncestry(tenantId: string, itemId: string): Promise<AncestryNode> {
  const [direct, ancestors] = await Promise.all([
    getCatalogItem(tenantId, itemId),
    getItemAncestry(tenantId, itemId),
  ]);

  const nodes: Nodes = new Map([
    [direct.entity_id, { name: direct.title, parentIds: direct.prototype_ids }],
  ]);

  for (const ancestor of ancestors) {
    nodes.set(ancestor.entity_id, { name: ancestor.name, parentIds: ancestor.prototype_ids });
  }

  return { name: direct.title, parents: parentsOf(direct.entity_id, nodes) };
}
