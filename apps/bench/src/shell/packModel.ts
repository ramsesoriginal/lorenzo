// A pack's contents as the strict list in its description (ADR 0145, edited by ADR 0256). Pure
// functions on rows, so every move is tested without a screen.

export interface Row {
  /** 0 is at the top; a container's contents are one deeper. At most 2 (three levels). */
  depth: number;
  count: number;
  label: string;
  /** The entry's link name; null for plain text. */
  slug: string | null;
}

export const MAX_DEPTH = 2;

const ROW = /^( {2}){0,2}- (\d+) x (?:\[([^\]]+)\]\(([A-Za-z0-9][A-Za-z0-9_-]*)\)|(\S.*?))\s*$/;

/** A text split into what is before the list, the list, and what is after it. */
export interface Pack {
  before: string[];
  rows: Row[];
  after: string[];
  /** Other text sits between the list lines: editing rows could not keep it in place. */
  mixed: boolean;
}

export function parsePack(text: string): Pack {
  const lines = text.split('\n');
  const parsed = lines.map((l): Row | null => {
    const m = ROW.exec(l);
    if (!m) return null;
    const depth = (l.length - l.trimStart().length) / 2;
    const count = Number(m[2]);
    return m[4]
      ? { depth, count, label: m[3] as string, slug: m[4] }
      : { depth, count, label: m[5] as string, slug: null };
  });
  const first = parsed.findIndex((r) => r);
  if (first < 0) return { before: lines, rows: [], after: [], mixed: false };
  const last = parsed.length - 1 - [...parsed].reverse().findIndex((r) => r);
  const inside = parsed.slice(first, last + 1);
  const rows = inside.filter((r): r is Row => r !== null);
  return {
    before: lines.slice(0, first),
    rows: fixDepths(rows),
    after: lines.slice(last + 1),
    mixed: inside.some((r, i) => r === null && (lines[first + i] ?? '').trim() !== ''),
  };
}

export const rowText = (r: Row): string =>
  `${'  '.repeat(r.depth)}- ${r.count} x ${r.slug ? `[${r.label}](${r.slug})` : r.label}`;

export function writePack(p: Pack): string {
  return [...p.before, ...p.rows.map(rowText), ...p.after].join('\n');
}

/** A row is at most one deeper than the one before it, and the first is at the top. */
export function fixDepths(rows: readonly Row[]): Row[] {
  let prev = -1;
  return rows.map((r) => {
    const depth = Math.max(0, Math.min(r.depth, prev + 1, MAX_DEPTH));
    prev = depth;
    return { ...r, depth };
  });
}

/** How many rows follow row `i` that are inside it. */
export function subtreeSize(rows: readonly Row[], i: number): number {
  const at = rows[i];
  if (!at) return 0;
  let n = 1;
  while (rows[i + n] && (rows[i + n] as Row).depth > at.depth) n++;
  return n;
}

/** Moves the row, and what is inside it, past the neighbouring row of its own level. */
export function move(rows: readonly Row[], i: number, by: -1 | 1): { rows: Row[]; at: number } {
  const at = rows[i];
  if (!at) return { rows: [...rows], at: i };
  const size = subtreeSize(rows, i);
  let neighbour = -1;
  if (by === -1) {
    // The nearest row above at the same level, unless a shallower one comes first.
    for (let j = i - 1; j >= 0; j--) {
      const d = (rows[j] as Row).depth;
      if (d < at.depth) break;
      if (d === at.depth) {
        neighbour = j;
        break;
      }
    }
    if (neighbour < 0) return { rows: [...rows], at: i };
    const block = rows.slice(i, i + size);
    const rest = [
      ...rows.slice(0, neighbour),
      ...block,
      ...rows.slice(neighbour, i),
      ...rows.slice(i + size),
    ];
    return { rows: rest, at: neighbour };
  }
  const after = i + size;
  const next = rows[after];
  if (!next || next.depth !== at.depth) return { rows: [...rows], at: i };
  const nextSize = subtreeSize(rows, after);
  const out = [
    ...rows.slice(0, i),
    ...rows.slice(after, after + nextSize),
    ...rows.slice(i, i + size),
    ...rows.slice(after + nextSize),
  ];
  return { rows: out, at: i + nextSize };
}

/** Puts the row, and what is inside it, one level deeper: into the row above it. */
export function indent(rows: readonly Row[], i: number): Row[] {
  const at = rows[i];
  const above = rows[i - 1];
  if (!at || !above || at.depth > above.depth) return [...rows];
  const size = subtreeSize(rows, i);
  const deepest = Math.max(...rows.slice(i, i + size).map((r) => r.depth));
  if (deepest + 1 > MAX_DEPTH) return [...rows];
  return rows.map((r, j) => (j >= i && j < i + size ? { ...r, depth: r.depth + 1 } : r));
}

/** Takes the row, and what is inside it, one level out. */
export function outdent(rows: readonly Row[], i: number): Row[] {
  const at = rows[i];
  if (!at || at.depth === 0) return [...rows];
  const size = subtreeSize(rows, i);
  return rows.map((r, j) => (j >= i && j < i + size ? { ...r, depth: r.depth - 1 } : r));
}

/** Takes the row away; what was inside it moves up a level. */
export function remove(rows: readonly Row[], i: number): Row[] {
  const size = subtreeSize(rows, i);
  const inner = rows.slice(i + 1, i + size).map((r) => ({ ...r, depth: r.depth - 1 }));
  return fixDepths([...rows.slice(0, i), ...inner, ...rows.slice(i + size)]);
}

/** What the rows weigh together, with how many have a weight; a row counts as often as its containers. */
export function total(
  rows: readonly Row[],
  weightOf: (slug: string) => number | null | undefined,
): { weight: number; known: number; listed: number } {
  let weight = 0;
  let known = 0;
  const factors: number[] = [];
  for (const r of rows) {
    factors.length = r.depth;
    const outer = factors.reduce((a, b) => a * b, 1);
    factors[r.depth] = r.count;
    const w = r.slug ? weightOf(r.slug) : null;
    if (typeof w === 'number') {
      weight += w * r.count * outer;
      known++;
    }
  }
  return { weight: Math.round(weight * 1000) / 1000, known, listed: rows.length };
}
