import type { CatalogItem } from '../../lib/types';

// The prototypes the catalog filter leaves out: one that exists only to carry
// a system's half of a single item ("Longsword (D&D 5e)", attached to the
// Longsword by the importer's system pass, ADR 0182). It is never public and
// has exactly one child, a plain item with nothing built on it. Offering it as
// a filter would only repeat the item, once for every system.
//
// Matching still walks through it, so ticking "Martial weapon" finds the
// Longsword whether or not the prototype between them is shown.
export function perItemPrototypeIds(items: CatalogItem[]): Set<string> {
  const childrenOf = new Map<string, string[]>();

  for (const item of items) {
    for (const parentId of item.prototype_ids) {
      childrenOf.set(parentId, [...(childrenOf.get(parentId) ?? []), item.entity_id]);
    }
  }

  const hidden = new Set<string>();

  for (const item of items) {
    const children = childrenOf.get(item.entity_id) ?? [];
    const [onlyChild] = children;

    if (
      !item.in_public_catalog &&
      children.length === 1 &&
      onlyChild !== undefined &&
      !childrenOf.has(onlyChild)
    ) {
      hidden.add(item.entity_id);
    }
  }

  return hidden;
}
