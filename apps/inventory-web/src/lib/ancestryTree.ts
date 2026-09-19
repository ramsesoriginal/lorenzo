import { getCatalogItem, getItemAncestry } from './items';

// Builds a nested <ul> from entity_id -> {name, parentIds}, starting at
// rootId and recursing into each direct parent. Prototype graphs are DAGs,
// not always clean chains (ADR 0073) - an item reachable via two different
// parents (diamond inheritance) genuinely appears twice, once per real
// path, rather than being silently deduplicated into a single misleading
// line. `seenOnPath` guards against rendering a cycle infinitely; the
// API's insert-time trigger (ADR 0015) already prevents real ones, this is
// just defensive.
function buildAncestryTree(
  rootId: string,
  nodes: Map<string, { name: string; parentIds: string[] }>,
  seenOnPath: ReadonlySet<string> = new Set(),
): HTMLUListElement {
  const list = document.createElement('ul');
  const node = nodes.get(rootId);
  if (!node || seenOnPath.has(rootId)) return list;
  const path = new Set(seenOnPath).add(rootId);
  for (const parentId of node.parentIds) {
    const parent = nodes.get(parentId);
    if (!parent) continue;
    const li = document.createElement('li');
    li.textContent = parent.name;
    const children = buildAncestryTree(parentId, nodes, path);
    if (children.children.length > 0) li.append(children);
    list.append(li);
  }
  return list;
}

// The full transitive ancestry (ADR 0073) is scoped to catalog Items, not
// instances - callers pass the *direct* prototype id (an instance's own
// entity id doesn't work here; resolve its ItemInstanceOut.prototype_ids[0]
// first). Returns the root <li> (directPrototypeId's own name, with a
// nested <ul> of its ancestors if it has any) - mount it into whatever
// <ul> container the caller already has.
export async function fetchAncestryTree(
  tenantId: string,
  directPrototypeId: string,
): Promise<HTMLLIElement> {
  const [direct, ancestors] = await Promise.all([
    getCatalogItem(tenantId, directPrototypeId),
    getItemAncestry(tenantId, directPrototypeId),
  ]);

  const nodes = new Map<string, { name: string; parentIds: string[] }>();
  nodes.set(direct.entity_id, { name: direct.title, parentIds: direct.prototype_ids });
  for (const ancestor of ancestors) {
    nodes.set(ancestor.entity_id, { name: ancestor.name, parentIds: ancestor.prototype_ids });
  }

  const rootLi = document.createElement('li');
  rootLi.textContent = direct.title;
  const tree = buildAncestryTree(direct.entity_id, nodes);
  if (tree.children.length > 0) rootLi.append(tree);
  return rootLi;
}
