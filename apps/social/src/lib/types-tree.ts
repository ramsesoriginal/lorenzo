// The types of a library as a tree: pure, so the tests need no page.

export interface TypeNode {
  id: string;
  name: string;
  parent_ids: readonly string[];
}

/** Types hang under the types they are kinds of; a type with no visible parent is a root. A loop
 * in what a library authored is cut, so it can never hang the screen. */
export function typeTree<T extends TypeNode>(types: readonly T[]): { row: T; depth: number }[] {
  const byId = new Map(types.map((t) => [t.id, t]));
  const children = new Map<string | null, T[]>();
  for (const t of types) {
    const parent = t.parent_ids.find((p) => byId.has(p)) ?? null;
    children.set(parent, [...(children.get(parent) ?? []), t]);
  }
  const out: { row: T; depth: number }[] = [];
  const walk = (parent: string | null, depth: number, seen: Set<string>) => {
    for (const row of children.get(parent) ?? []) {
      if (seen.has(row.id)) continue;
      out.push({ row, depth });
      walk(row.id, depth + 1, new Set([...seen, row.id]));
    }
  };
  walk(null, 0, new Set());
  return out;
}
