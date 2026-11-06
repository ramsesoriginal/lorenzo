// The matrix's logic, apart from the page (ADR 0408): one ordered pair of a web's members a cell,
// the cells a window of relationships fills, what an edit means, and the batches a save goes in.
// Pure, so the tests need no page.

import { defaultName } from './words';

/** At most this many rows and columns are read at once: the list reads take a hundred ids. */
export const WINDOW = 100;
/** A save goes in batches of at most this many operations (ADR 0400). */
export const BATCH = 100;

export interface Tie {
  id: string;
  name: string;
  endA: string;
  endB: string;
  oneWay: boolean;
}

export interface Standing {
  value: number | string | boolean;
  own: boolean;
}

export interface Cell {
  ties: Tie[];
  value: Standing | null;
}

export const cellKey = (row: string, col: string) => `${row}|${col}`;

/**
 * The cells a set of relationships fills. A one-way relationship fills its own cell; a two-way one
 * both cells of its pair. A relationship the reader may not see is not here, so its cell is empty,
 * indistinguishable from none. Two relationships for one cell make a conflict (`ties.length > 1`).
 */
export function buildCells(
  ties: readonly Tie[],
  values: ReadonlyMap<string, Standing>,
  rows: ReadonlySet<string>,
  cols: ReadonlySet<string>,
): Map<string, Cell> {
  const cells = new Map<string, Cell>();
  const put = (row: string, col: string, tie: Tie) => {
    if (!rows.has(row) || !cols.has(col)) return;
    const k = cellKey(row, col);
    const cell = cells.get(k) ?? { ties: [], value: null };
    if (!cell.ties.some((t) => t.id === tie.id)) cell.ties.push(tie);
    cell.value = cell.ties.length === 1 ? (values.get(tie.id) ?? null) : null;
    cells.set(k, cell);
  };
  for (const tie of ties) {
    put(tie.endA, tie.endB, tie);
    if (!tie.oneWay) put(tie.endB, tie.endA, tie);
  }
  return cells;
}

export const isConflict = (cell: Cell | undefined) => (cell?.ties.length ?? 0) > 1;

export interface StatLimits {
  valueType: string;
  min: number | null;
  max: number | null;
  name: string;
}

export type Parsed = { ok: true; value: number | null } | { ok: false; reason: string };

/** What a person typed into a cell: nothing clears the standing; a whole number inside the scale
 * sets it. Decimals are read, not written, here. */
export function parseInput(text: string, stat: StatLimits): Parsed {
  const typed = text.trim();
  if (typed === '') return { ok: true, value: null };
  if (stat.valueType !== 'int') {
    return { ok: false, reason: `${stat.name} is read here, not changed.` };
  }
  if (!/^-?\d+$/.test(typed)) return { ok: false, reason: 'Type a whole number.' };
  const value = Number(typed);
  if (stat.min !== null && value < stat.min) {
    return { ok: false, reason: `${value} is below the scale (from ${stat.min}).` };
  }
  if (stat.max !== null && value > stat.max) {
    return { ok: false, reason: `${value} is above the scale (up to ${stat.max}).` };
  }
  return { ok: true, value };
}

export interface Edit {
  row: string;
  col: string;
  /** What the cell held when it was read. */
  before: Cell | undefined;
  /** The standing wanted: a number, or null to clear it. */
  value: number | null;
}

export type Operation =
  | {
      op: 'create';
      name: string;
      end_a: string;
      end_b: string;
      one_way: boolean;
      prototypes: string[];
      is_public: false;
      stats: { stat_definition_id: string; value: number }[];
    }
  | {
      op: 'set';
      relationship_id: string;
      stat_definition_id: string;
      value: number;
      if_match: string;
    }
  | { op: 'clear'; relationship_id: string; stat_definition_id: string; if_match: string };

export interface Planned {
  /** The cells the operation answers for, so a refusal can be shown on them. */
  cells: string[];
  operation: Operation;
}

export interface PlanInput {
  edits: readonly Edit[];
  stat: string;
  /** The type a new relationship is of, and whether that type is directed. */
  type: { id: string; name: string } | null;
  directed: boolean;
  nameOf: (entry: string) => string;
  /** Each existing relationship's version, as it was read. */
  versions: ReadonlyMap<string, string>;
}

/** What a set of edits asks of the API: a standing set or cleared on a relationship that is there,
 * or a relationship made, restricted, with the standing set. A cell in conflict, and an empty cell
 * left empty, ask for nothing. Two cells of one two-way relationship are one operation. */
export function planOperations(input: PlanInput): { planned: Planned[]; skipped: string[] } {
  const planned: Planned[] = [];
  const skipped: string[] = [];
  const byTie = new Map<string, Planned>();
  for (const edit of input.edits) {
    const where = cellKey(edit.row, edit.col);
    const ties = edit.before?.ties ?? [];
    if (ties.length > 1) {
      skipped.push(where);
      continue;
    }
    const tie = ties[0];
    if (tie) {
      const known = byTie.get(tie.id);
      if (known) {
        known.cells.push(where);
        if (edit.value === null) {
          known.operation = {
            op: 'clear',
            relationship_id: tie.id,
            stat_definition_id: input.stat,
            if_match: input.versions.get(tie.id) ?? '',
          };
        } else {
          known.operation = {
            op: 'set',
            relationship_id: tie.id,
            stat_definition_id: input.stat,
            value: edit.value,
            if_match: input.versions.get(tie.id) ?? '',
          };
        }
        continue;
      }
      const item: Planned = {
        cells: [where],
        operation:
          edit.value === null
            ? {
                op: 'clear',
                relationship_id: tie.id,
                stat_definition_id: input.stat,
                if_match: input.versions.get(tie.id) ?? '',
              }
            : {
                op: 'set',
                relationship_id: tie.id,
                stat_definition_id: input.stat,
                value: edit.value,
                if_match: input.versions.get(tie.id) ?? '',
              },
      };
      byTie.set(tie.id, item);
      planned.push(item);
    } else if (edit.value !== null) {
      planned.push({
        cells: [where],
        operation: {
          op: 'create',
          name: defaultName(input.nameOf(edit.row), input.nameOf(edit.col), input.type?.name),
          end_a: edit.row,
          end_b: edit.col,
          one_way: input.directed,
          prototypes: input.type ? [input.type.id] : [],
          is_public: false,
          stats: [{ stat_definition_id: input.stat, value: edit.value }],
        },
      });
    }
  }
  return { planned, skipped };
}

export function batches<T>(items: readonly T[], size = BATCH): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

/** The slice of `count` fixed-size rows (or columns) that a scroll position shows, with a few
 * more on each side so scrolling does not show blanks. Half-open: `[from, to)`. */
export function visibleRange(
  scroll: number,
  viewport: number,
  size: number,
  count: number,
  overscan = 3,
): [number, number] {
  const from = Math.min(count, Math.max(0, Math.floor(scroll / size) - overscan));
  const to = Math.min(count, Math.ceil((scroll + viewport) / size) + overscan);
  return [from, Math.max(from, to)];
}

/** The windows a list of `count` members is read in: `[from, to)` ranges of at most `WINDOW`. */
export function windows(count: number, size = WINDOW): [number, number][] {
  const out: [number, number][] = [];
  for (let from = 0; from < count; from += size) out.push([from, Math.min(count, from + size)]);
  return out.length ? out : [[0, 0]];
}

/** The arrow-key and page-key moves of a grid: where the focus goes from a cell. */
export function moveFocus(
  at: { row: number; col: number },
  key: string,
  size: { rows: number; cols: number; page: number },
): { row: number; col: number } | null {
  const clamp = (n: number, max: number) => Math.min(Math.max(0, n), Math.max(0, max - 1));
  switch (key) {
    case 'ArrowUp':
      return { row: clamp(at.row - 1, size.rows), col: at.col };
    case 'ArrowDown':
      return { row: clamp(at.row + 1, size.rows), col: at.col };
    case 'ArrowLeft':
      return { row: at.row, col: clamp(at.col - 1, size.cols) };
    case 'ArrowRight':
      return { row: at.row, col: clamp(at.col + 1, size.cols) };
    case 'Home':
      return { row: at.row, col: 0 };
    case 'End':
      return { row: at.row, col: clamp(size.cols - 1, size.cols) };
    case 'PageUp':
      return { row: clamp(at.row - size.page, size.rows), col: at.col };
    case 'PageDown':
      return { row: clamp(at.row + size.page, size.rows), col: at.col };
    default:
      return null;
  }
}
