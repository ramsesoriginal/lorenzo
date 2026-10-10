// The compare grid's logic as plain data: which stats are its columns, where a value comes from,
// how a typed cell is read, what a selection covers, and the clipboard text. No DOM, so it is
// tested alone.

import type { EntryState, EntrySummary, StatDef, StatScalar, StatType } from '../core/transport';

/** How far a stat's − and + move it: whole numbers by 1, decimals by 0.1. Others do not step. */
export const stepOf = (type: StatType): number | null =>
  type === 'int' ? 1 : type === 'float' ? 0.1 : null;

/** `a + b` for a decimal without 0.1 + 0.2 showing as 0.30000000000000004. */
export const add = (value: number, by: number): number => Math.round((value + by) * 1e6) / 1e6;

/** The stats shown when nothing was chosen: the numeric ones, so a grid starts as a table of numbers. */
export function defaultColumns(defs: readonly StatDef[], limit = 4): string[] {
  return defs
    .filter((d) => d.type === 'int' || d.type === 'float')
    .slice(0, limit)
    .map((d) => d.id);
}

/** What was typed in a cell, as a value for its stat: `undefined` when it is not one. `''` is none. */
export function parseCell(type: StatType, text: string): StatScalar | null | undefined {
  const t = text.trim();
  if (t === '') return null;
  if (type === 'int') return /^-?\d+$/.test(t) ? Number(t) : undefined;
  if (type === 'float') {
    const n = t.replace(',', '.');
    return /^-?\d+(\.\d+)?$/.test(n) ? Number(n) : undefined;
  }
  if (type === 'bool') {
    const v = t.toLowerCase();
    if (['on', 'yes', 'true', '1'].includes(v)) return true;
    if (['off', 'no', 'false', '0'].includes(v)) return false;
    return undefined;
  }
  return t;
}

/** A value as a cell shows it. */
export function showCell(value: StatScalar | null | undefined): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'On' : 'Off';
  return String(value);
}

/** One entry's stats by stat id: its value, and whether it is the entry's own. */
export type Values = Map<string, { value: StatScalar | null; own: boolean }>;

export function valuesOf(entry: EntryState | null): Values {
  const out: Values = new Map();
  for (const s of entry?.stats ?? []) out.set(s.statId, { value: s.value, own: s.own });
  return out;
}

/**
 * Where a cell's value comes from: the entry itself (own), the nearest entry above it that has a
 * value of its own for the stat, or nowhere. Nearest first; the first parent first on a tie.
 */
export function valueSource(
  entries: readonly EntrySummary[],
  values: ReadonlyMap<string, Values>,
  id: string,
  stat: string,
): { kind: 'own' } | { kind: 'inherited'; from: string } | { kind: 'none' } {
  if (values.get(id)?.get(stat)?.own) return { kind: 'own' };
  const byId = new Map(entries.map((e) => [e.id, e]));
  const seen = new Set([id]);
  let level = byId.get(id)?.parentIds ?? [];
  while (level.length) {
    const next: string[] = [];
    for (const p of level) {
      if (seen.has(p)) continue;
      seen.add(p);
      if (values.get(p)?.get(stat)?.own) return { kind: 'inherited', from: p };
      next.push(...(byId.get(p)?.parentIds ?? []));
    }
    level = next;
  }
  return { kind: 'none' };
}

/** A rectangle of cells, by row and column number, whichever corner it was dragged from. */
export interface Range {
  r0: number;
  c0: number;
  r1: number;
  c1: number;
}
export const normalise = (r: Range): Range => ({
  r0: Math.min(r.r0, r.r1),
  r1: Math.max(r.r0, r.r1),
  c0: Math.min(r.c0, r.c1),
  c1: Math.max(r.c0, r.c1),
});
export const cellsOf = (range: Range): { row: number; col: number }[] => {
  const r = normalise(range);
  const out: { row: number; col: number }[] = [];
  for (let row = r.r0; row <= r.r1; row++)
    for (let col = r.c0; col <= r.c1; col++) out.push({ row, col });
  return out;
};
export const clamp = (n: number, max: number): number => Math.max(0, Math.min(max, n));

/** Rows of cells as clipboard text: tabs between columns, a line for each row. */
export const toTsv = (rows: readonly (readonly string[])[]): string =>
  rows.map((r) => r.join('\t')).join('\n');

/** Clipboard text as rows of cells. A trailing line break (a spreadsheet adds one) is not a row. */
export function fromTsv(text: string): string[][] {
  const lines = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
  return lines.map((l) => l.split('\t'));
}

/** The entries in the order a grid lists them: A to Z, or as a tree of what inherits from what. */
export function gridOrder(
  entries: readonly EntrySummary[],
  order: 'inherits' | 'name',
  filter: string,
): { entry: EntrySummary; depth: number }[] {
  const byName = (a: EntrySummary, b: EntrySummary) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }) || a.id.localeCompare(b.id);
  const q = filter.trim().toLowerCase();
  const keep = (e: EntrySummary) => !q || e.name.toLowerCase().includes(q);
  if (order === 'name' || q)
    return entries
      .filter(keep)
      .sort(byName)
      .map((entry) => ({ entry, depth: 0 }));
  const known = new Set(entries.map((e) => e.id));
  const kids = new Map<string, EntrySummary[]>();
  const roots: EntrySummary[] = [];
  for (const e of [...entries].sort(byName)) {
    const parents = e.parentIds.filter((p) => known.has(p));
    if (!parents.length) roots.push(e);
    for (const p of parents) kids.set(p, [...(kids.get(p) ?? []), e]);
  }
  const out: { entry: EntrySummary; depth: number }[] = [];
  const walk = (e: EntrySummary, depth: number, trail: Set<string>) => {
    out.push({ entry: e, depth });
    for (const c of kids.get(e.id) ?? [])
      if (!trail.has(c.id)) walk(c, depth + 1, new Set(trail).add(c.id));
  };
  for (const r of roots) walk(r, 0, new Set([r.id]));
  return out;
}
