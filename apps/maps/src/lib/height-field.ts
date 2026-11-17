// The Height brush (ADR 0480): a field of heights over the sheet, built from an entry's height
// lines; strokes that raise and lower it; and which lines to keep and which to draw from it. The
// lines are the truth, and the field lives in the page only. Pure.
import { bezierPoints, type Geometry, type Part } from '@lorenzo/map-renderer';
import { decimalsFor, type Field } from './field';
import { heightLines } from './fill';
import { simplify } from './freehand';
import { isHeightLines } from './parts-edit';
import { closedSplinePart, splinePart } from './spline';

/** The tension of the curve a line is written as: the Spline tool's (ADR 0471, ADR 0491). */
export const LINE_TENSION = 0.5;

type Curve = Extract<Part, { shape: 'bezier' }>;

/**
 * A traced line as a smooth curve through its points (ADR 0491): one that closes on itself closes
 * smoothly, its first point also its last.
 */
export function smoothLine(pts: readonly Pt[], round: (n: number) => number): Curve {
  const first = pts[0] as Pt;
  const last = pts[pts.length - 1] as Pt;
  const closed = pts.length > 3 && first[0] === last[0] && first[1] === last[1];

  return closed
    ? closedSplinePart(pts.slice(0, -1), LINE_TENSION, round)
    : splinePart(pts, LINE_TENSION, round);
}

type Pt = readonly [number, number];
type Extent = readonly [number, number, number, number];

/** The samples of the field across the sheet. */
export const BRUSH_COLS = 128;
/** A sample this near a line, in samples, holds its height. */
const BAND = 0.75;
/** How far a place with no line in it rises (or falls) beyond its last line, in steps. */
export const DOME = 0.25;
/** A traced line this near an entry's line of its height, in samples, takes its place. */
const NEAR = 2;
/** The fewest rows a field has. */
const MIN_ROWS = 4;
/** At most this many heights are traced at once: a placement holds no more lines than that. */
export const MAX_LEVELS = 256;

/** One line of an entry: the part it is, its height and its points. */
export type EntryLine = { part: number; value: number; pts: Pt[] };

/**
 * The height lines of an entry, by part, and their one unit; no lines for an entry not on this Map.
 * Refused, by name, for an entry drawn here as anything else, or with lines in several units.
 */
export function entryLines(
  name: string,
  geometry: Geometry | null,
): { ok: true; lines: EntryLine[]; unit: string | null } | { ok: false; why: string } {
  if (!geometry) return { ok: true, lines: [], unit: null };
  if (!isHeightLines(geometry)) {
    return {
      ok: false,
      why: `${name} is drawn on this Map as something else than height lines, and the brush changes height lines only.`,
    };
  }
  const units = [...new Set(geometry.parts.map((part) => part.unit as string))];
  if (units.length > 1) {
    return {
      ok: false,
      why: `${name} has lines in more than one unit (${units.join(', ')}), and the brush works in one.`,
    };
  }
  const lines = geometry.parts.map((part, index): EntryLine => {
    const pts: Pt[] =
      part.shape === 'polyline'
        ? [...part.pts]
        : part.shape === 'bezier'
          ? bezierPoints(part).map((p): Pt => [p[0], p[1]])
          : [];

    return { part: index, value: part.value as number, pts };
  });

  return { ok: true, lines, unit: units[0] ?? null };
}

/** The smallest gap between two heights of the lines; null with fewer than two heights. */
export function stepOf(lines: readonly EntryLine[]): number | null {
  const heights = [...new Set(lines.map((line) => line.value))].sort((a, b) => a - b);
  let step: number | null = null;

  for (let k = 1; k < heights.length; k += 1) {
    const gap = (heights[k] as number) - (heights[k - 1] as number);
    if (step === null || gap < step) step = gap;
  }

  return step;
}

export type BrushField = {
  cols: number;
  rows: number;
  /** The side of a sample, in drawing units. */
  cell: number;
  /** The sheet's near corner: a sample's middle is half a sample in from it. */
  x0: number;
  y0: number;
  /** The smoothest heights between the lines, flat beyond the last of them. */
  relaxed: Float64Array;
  /** Where a place with no line in it rises (1) or falls (-1) beyond its last line, 0 elsewhere. */
  dome: Float64Array;
  /** For each line, the samples that hold its height. */
  bands: number[][];
};

/** The samples a segment passes within `reach` of, in drawing units. */
function samplesNear(
  field: Omit<BrushField, 'relaxed' | 'dome' | 'bands'>,
  a: Pt,
  b: Pt,
  reach: number,
): number[] {
  const { cols, rows, cell, x0, y0 } = field;
  const out: number[] = [];
  const i0 = Math.max(0, Math.floor((Math.min(a[0], b[0]) - reach - x0) / cell - 0.5));
  const i1 = Math.min(cols - 1, Math.ceil((Math.max(a[0], b[0]) + reach - x0) / cell - 0.5));
  const j0 = Math.max(0, Math.floor((Math.min(a[1], b[1]) - reach - y0) / cell - 0.5));
  const j1 = Math.min(rows - 1, Math.ceil((Math.max(a[1], b[1]) + reach - y0) / cell - 0.5));
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length2 = dx * dx + dy * dy;

  for (let j = j0; j <= j1; j += 1) {
    for (let i = i0; i <= i1; i += 1) {
      const px = x0 + (i + 0.5) * cell;
      const py = y0 + (j + 0.5) * cell;
      let t = length2 === 0 ? 0 : ((px - a[0]) * dx + (py - a[1]) * dy) / length2;
      t = Math.max(0, Math.min(1, t));
      if (Math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy)) <= reach) out.push(j * cols + i);
    }
  }

  return out;
}

/** The four neighbours of a sample that are on the field. */
function neighbours(cols: number, rows: number, s: number): number[] {
  const i = s % cols;
  const j = (s - i) / cols;
  const out: number[] = [];
  if (i > 0) out.push(s - 1);
  if (i < cols - 1) out.push(s + 1);
  if (j > 0) out.push(s - cols);
  if (j < rows - 1) out.push(s + cols);
  return out;
}

/**
 * The field of an entry's lines over the sheet (ADR 0480): a sample near a line holds its height,
 * every other the mean of its neighbours, worked out until it settles; flat at `flat` with no line.
 */
export function brushField(extent: Extent, lines: readonly EntryLine[], flat: number): BrushField {
  const [x0, y0, x1, y1] = extent;
  const cols = BRUSH_COLS;
  const cell = (x1 - x0) / cols;
  const rows = Math.max(MIN_ROWS, Math.ceil((y1 - y0) / cell));
  const count = cols * rows;
  const shape = { cols, rows, cell, x0, y0 };
  const relaxed = new Float64Array(count).fill(flat);
  const dome = new Float64Array(count);
  const owner = new Int32Array(count).fill(-1);

  lines.forEach((line, index) => {
    for (let k = 0; k + 1 < line.pts.length; k += 1) {
      for (const s of samplesNear(shape, line.pts[k] as Pt, line.pts[k + 1] as Pt, BAND * cell)) {
        owner[s] = index;
        relaxed[s] = line.value;
      }
    }
  });
  const bands: number[][] = lines.map(() => []);
  for (let s = 0; s < count; s += 1) {
    const index = owner[s] as number;
    if (index >= 0) (bands[index] as number[]).push(s);
  }
  if (!owner.some((index) => index >= 0)) return { ...shape, relaxed, dome, bands };

  // Every free sample starts at the height of the nearest line, so the means settle soon.
  const queue: number[] = [];
  const seen = new Uint8Array(count);
  for (let s = 0; s < count; s += 1) {
    if ((owner[s] as number) >= 0) {
      seen[s] = 1;
      queue.push(s);
    }
  }
  for (let head = 0; head < queue.length; head += 1) {
    const s = queue[head] as number;
    for (const n of neighbours(cols, rows, s)) {
      if (seen[n]) continue;
      seen[n] = 1;
      relaxed[n] = relaxed[s] as number;
      queue.push(n);
    }
  }

  const heights = lines.map((line) => line.value);
  const range = Math.max(1, Math.max(...heights) - Math.min(...heights));
  const settled = 1e-7 * range;
  for (let pass = 0; pass < 5000; pass += 1) {
    let moved = 0;
    for (let s = 0; s < count; s += 1) {
      if ((owner[s] as number) >= 0) continue;
      const around = neighbours(cols, rows, s);
      let sum = 0;
      for (const n of around) sum += relaxed[n] as number;
      const was = relaxed[s] as number;
      const next = was + 1.8 * (sum / around.length - was);
      relaxed[s] = next;
      moved = Math.max(moved, Math.abs(next - was));
    }
    if (moved < settled) break;
  }

  // A place with no line in it, bounded by lines of one height, is flat at that height: it rises
  // beyond the line where the land rises to it, falls where it falls, and is left flat where it
  // reaches the sheet's edge.
  const tie = 1e-6 * range;
  const part = new Int32Array(count).fill(-1);
  let parts = 0;
  for (let start = 0; start < count; start += 1) {
    if ((owner[start] as number) >= 0 || (part[start] as number) >= 0) continue;
    const id = parts;
    parts += 1;
    const members: number[] = [start];
    part[start] = id;
    for (let head = 0; head < members.length; head += 1) {
      for (const n of neighbours(cols, rows, members[head] as number)) {
        if ((owner[n] as number) >= 0 || (part[n] as number) >= 0) continue;
        part[n] = id;
        members.push(n);
      }
    }
    const rim = new Set<number>();
    let edge = false;
    for (const s of members) {
      const i = s % cols;
      const j = (s - i) / cols;
      if (i === 0 || j === 0 || i === cols - 1 || j === rows - 1) edge = true;
      for (const n of neighbours(cols, rows, s)) if ((owner[n] as number) >= 0) rim.add(n);
    }
    const rimHeights = new Set([...rim].map((s) => relaxed[s] as number));
    if (edge || rimHeights.size !== 1) continue;
    const h = [...rimHeights][0] as number;
    if (members.some((s) => Math.abs((relaxed[s] as number) - h) > tie)) continue;
    let lower = false;
    let higher = false;
    for (const r of rim) {
      for (const n of neighbours(cols, rows, r)) {
        if ((owner[n] as number) >= 0 || part[n] === id) continue;
        const v = relaxed[n] as number;
        if (v < h - tie) lower = true;
        if (v > h + tie) higher = true;
      }
    }
    const sign = lower ? 1 : higher ? -1 : 1;
    // How far in from the rim, in samples.
    const depth = new Map<number, number>();
    const walk: number[] = [];
    for (const s of members) {
      if (neighbours(cols, rows, s).some((n) => rim.has(n))) {
        depth.set(s, 1);
        walk.push(s);
      }
    }
    for (let head = 0; head < walk.length; head += 1) {
      const s = walk[head] as number;
      for (const n of neighbours(cols, rows, s)) {
        if (part[n] !== id || depth.has(n)) continue;
        depth.set(n, (depth.get(s) as number) + 1);
        walk.push(n);
      }
    }
    const deepest = Math.max(...depth.values());
    for (const [s, d] of depth) dome[s] = (sign * d) / deepest;
  }

  return { ...shape, relaxed, dome, bands };
}

/** How much each sample is moved by a stroke through `points`: 1 at a point, 0 from `radius` on. */
export function strokeOf(field: BrushField, points: readonly Pt[], radius: number): Float64Array {
  const { cols, rows, cell, x0, y0 } = field;
  const out = new Float64Array(cols * rows);
  if (!(radius > 0)) return out;
  for (const [px, py] of points) {
    const i0 = Math.max(0, Math.floor((px - radius - x0) / cell));
    const i1 = Math.min(cols - 1, Math.ceil((px + radius - x0) / cell));
    const j0 = Math.max(0, Math.floor((py - radius - y0) / cell));
    const j1 = Math.min(rows - 1, Math.ceil((py + radius - y0) / cell));
    for (let j = j0; j <= j1; j += 1) {
      for (let i = i0; i <= i1; i += 1) {
        const t = Math.hypot(x0 + (i + 0.5) * cell - px, y0 + (j + 0.5) * cell - py) / radius;
        if (t >= 1) continue;
        const s = j * cols + i;
        // A smooth bell: whole at the middle, nothing at the radius.
        out[s] = Math.max(out[s] as number, (1 + Math.cos(Math.PI * t)) / 2);
      }
    }
  }
  return out;
}

/** What the strokes have moved so far, in steps, with one more stroke of `amount` steps. */
export function withStroke(
  raised: Float64Array,
  stroke: Float64Array,
  amount: number,
): Float64Array {
  return raised.map((value, s) => value + amount * (stroke[s] as number));
}

/** The heights of the field now, for a step. */
export function heightsNow(field: BrushField, raised: Float64Array, step: number): Float64Array {
  return field.relaxed.map(
    (value, s) => value + step * (DOME * (field.dome[s] as number) + (raised[s] as number)),
  );
}

/** A set of samples and those within `by` of them. */
function grown(field: BrushField, samples: Iterable<number>, by: number): Uint8Array {
  const { cols, rows } = field;
  const out = new Uint8Array(cols * rows);
  for (const s of samples) {
    const i = s % cols;
    const j = (s - i) / cols;
    for (let dj = -by; dj <= by; dj += 1) {
      for (let di = -by; di <= by; di += 1) {
        const ni = i + di;
        const nj = j + dj;
        if (ni >= 0 && nj >= 0 && ni < cols && nj < rows) out[nj * cols + ni] = 1;
      }
    }
  }
  return out;
}

/** The sample a point on the sheet lies in. */
function sampleAt(field: BrushField, [x, y]: Pt): number {
  const i = Math.max(0, Math.min(field.cols - 1, Math.floor((x - field.x0) / field.cell)));
  const j = Math.max(0, Math.min(field.rows - 1, Math.floor((y - field.y0) / field.cell)));
  return j * field.cols + i;
}

export type Redraw =
  | {
      ok: true;
      /** The parts of the entry kept as they are, in order. */
      keep: number[];
      /** The parts dropped: redrawn, or gone. */
      drop: number[];
      /** The lines to add, each with its height: its traced points and the curve written. */
      add: { pts: Pt[]; curve: Curve; value: number }[];
      redrawn: number;
      fresh: number;
      gone: number;
    }
  | { ok: false; why: string };

const rounded = (n: number) => Math.round(n * 1e6) / 1e6;

/**
 * Which lines of the entry stay and which are drawn (ADR 0480): at the entry's heights and every
 * `step` from `lowest` the field reaches where it was changed, the field's lines that pass the
 * change, each in place of the entry's lines of its height it passes near; the rest stay as drawn.
 */
export function redraw(
  field: BrushField,
  lines: readonly EntryLine[],
  raised: Float64Array,
  step: number,
  lowest: number,
  extent: Extent,
): Redraw {
  const keepAll = (): Redraw => ({
    ok: true,
    keep: lines.map((line) => line.part),
    drop: [],
    add: [],
    redrawn: 0,
    fresh: 0,
    gone: 0,
  });
  const changedAt: number[] = [];
  raised.forEach((value, s) => {
    if (value !== 0) changedAt.push(s);
  });
  if (changedAt.length === 0 || !(step > 0)) return keepAll();

  const values = heightsNow(field, raised, step);
  const touched = grown(field, changedAt, 1);
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  touched.forEach((on, s) => {
    if (!on) return;
    lo = Math.min(lo, values[s] as number);
    hi = Math.max(hi, values[s] as number);
  });
  const base = lines.length > 0 ? Math.min(...lines.map((line) => line.value)) : lowest;
  // The heights of the lines in the range the change reaches, and of every line it passed over.
  const levels = new Set(
    lines
      .filter(
        (one, index) =>
          (one.value >= lo && one.value <= hi) ||
          (field.bands[index] ?? []).some((s) => touched[s]),
      )
      .map((one) => one.value),
  );
  const first = Math.ceil((lo - base) / step - 1e-9);
  const last = Math.floor((hi - base) / step + 1e-9);
  if (last - first + 1 > MAX_LEVELS) {
    return {
      ok: false,
      why: `The strokes reach ${last - first + 1} heights, and a drawing holds ${MAX_LEVELS} lines. Use a larger Step.`,
    };
  }
  for (let k = first; k <= last; k += 1) levels.add(rounded(base + k * step));

  // The field with a border lower than any height, so every line closes or ends at the sheet's edge.
  const { cols, rows, cell } = field;
  const pad = Math.min(lo, ...levels) - Math.abs(step) - 1;
  const padded = new Float64Array((cols + 2) * (rows + 2)).fill(pad);
  const wall = new Uint8Array((cols + 2) * (rows + 2)).fill(1);
  for (let j = 0; j < rows; j += 1) {
    for (let i = 0; i < cols; i += 1) {
      padded[(j + 1) * (cols + 2) + i + 1] = values[j * cols + i] as number;
      wall[(j + 1) * (cols + 2) + i + 1] = 0;
    }
  }
  const tracing: Field = {
    cols: cols + 2,
    rows: rows + 2,
    cell,
    x0: field.x0 - cell,
    y0: field.y0 - cell,
    wall,
  };
  const [ex0, ey0, ex1, ey1] = extent;
  const onSheet = (p: Pt): Pt => [
    Math.min(ex1, Math.max(ex0, p[0])),
    Math.min(ey1, Math.max(ey0, p[1])),
  ];

  const drop = new Set<number>();
  const add: { pts: Pt[]; curve: Curve; value: number }[] = [];
  // The curve is kept to the decimals the traced points are kept to.
  let scale = 1;
  for (let d = 0; d < decimalsFor(tracing, 16); d += 1) scale *= 10;
  const round = (n: number) => Math.round(n * scale) / scale || 0;
  let redrawn = 0;
  let fresh = 0;
  let gone = 0;
  const nearLine = new Map<number, Uint8Array>();
  const nearOf = (index: number) => {
    let near = nearLine.get(index);
    if (!near) {
      near = grown(field, field.bands[index] ?? [], NEAR);
      nearLine.set(index, near);
    }
    return near;
  };

  for (const level of [...levels].sort((a, b) => a - b)) {
    const traced = heightLines(tracing, padded, level, 0).map((path) => path.map(onSheet));
    const own = lines
      .map((line, index) => ({ line, index }))
      .filter(({ line }) => line.value === level);
    const seen = new Set<number>();
    for (const path of traced) {
      const samples = path.map((p) => sampleAt(field, p));
      own.forEach(({ index }) => {
        if (samples.some((s) => nearOf(index)[s])) seen.add(index);
      });
      if (!samples.some((s) => touched[s])) continue;
      const replaces = own.filter(({ index }) => samples.some((s) => nearOf(index)[s]));
      for (const { line } of replaces) drop.add(line.part);
      const pts = simplify(path, cell / 4);
      if (pts.length < 2) continue;
      add.push({ pts, curve: smoothLine(pts, round), value: level });
      if (replaces.length > 0) redrawn += 1;
      else fresh += 1;
    }
    // A line the strokes passed over whose height the land no longer has there is gone.
    for (const { line, index } of own) {
      if (drop.has(line.part) || seen.has(index)) continue;
      if ((field.bands[index] ?? []).some((s) => touched[s])) {
        drop.add(line.part);
        gone += 1;
      }
    }
  }

  return {
    ok: true,
    keep: lines.map((line) => line.part).filter((part) => !drop.has(part)),
    drop: [...drop],
    add,
    redrawn,
    fresh,
    gone,
  };
}

/** The words of what the brush would do: "2 lines redrawn, 1 new". */
export function redrawWords(result: { redrawn: number; fresh: number; gone: number }): string {
  const words: string[] = [];
  if (result.redrawn > 0)
    words.push(`${result.redrawn} ${result.redrawn === 1 ? 'line' : 'lines'} redrawn`);
  if (result.fresh > 0) words.push(`${result.fresh} new`);
  if (result.gone > 0) words.push(`${result.gone} gone`);
  return words.length > 0 ? words.join(', ') : 'no line changed';
}
