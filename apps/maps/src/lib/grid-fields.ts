// The fields that describe a grid (ADR 0354, 0356): its cell, which way hexes sit, what a cell is in
// the world, and how a cell is divided. One block serves a grid system and a visual grid drawn over
// a plane or an outline. The API checks every value; this only asks for them and reads them back.
import { type BBox, cellCount, type GridKind, type GridSpec } from '@lorenzo/map-renderer';
import { el, field, select } from './dom';

export type GridDoc = {
  kind: GridKind;
  cell: { size?: number; width?: number; height?: number };
  orientation?: 'flat' | 'pointy';
  sub?: { cols?: number; rows?: number; aperture?: number };
  measure?: { per_cell: number; unit: string };
};

const ORIENTATIONS: [string, string][] = [
  ['', 'Choose…'],
  ['flat', 'Flat-topped, in columns'],
  ['pointy', 'Pointed-top, in rows'],
];

const APERTURES: [string, string][] = [
  ['', 'No sub-grid'],
  ['3', 'Aperture 3'],
  ['4', 'Aperture 4'],
  ['7', 'Aperture 7'],
];

const KIND_WORDS: Record<GridKind, string> = {
  square: 'A grid of squares',
  rect: 'A grid of rectangles',
  hex: 'A grid of hexes',
};

const number = (input: HTMLInputElement, what: string): number => {
  const n = Number(input.value);

  if (!(n > 0)) throw new Error(`${what} must be more than zero.`);

  return n;
};

/**
 * The block for one grid. `kinds` are the kinds it may be, `measured` whether a cell may be given a
 * size in the world, and `current` what to start from.
 */
export function gridBlock(options: {
  kinds: GridKind[];
  measured: boolean;
  current?: Partial<GridDoc> | null;
}) {
  const { current } = options;
  const root = el('div', '', 'grid');
  root.style.setProperty('--grid-min', '200px');
  const kind = select(
    'The grid is',
    options.kinds.map((k): [string, string] => [k, KIND_WORDS[k]]),
    current?.kind ?? options.kinds[0] ?? 'square',
  );
  const orientation = select('Hexes are', ORIENTATIONS, current?.orientation ?? '');
  const size = field('Cell size', String(current?.cell?.size ?? 50), 'number');
  const width = field('Cell width', String(current?.cell?.width ?? 60), 'number');
  const height = field('Cell height', String(current?.cell?.height ?? 40), 'number');
  for (const f of [size, width, height]) {
    f.input.min = '0';
    f.input.step = 'any';
  }
  const cols = field('Divide each cell into columns', String(current?.sub?.cols ?? 1), 'number');
  const rows = field('and rows', String(current?.sub?.rows ?? 1), 'number');
  for (const f of [cols, rows]) {
    f.input.min = '1';
    f.input.max = '16';
    f.input.step = '1';
  }
  const aperture = select(
    'Divide each hex',
    APERTURES,
    current?.sub?.aperture ? String(current.sub.aperture) : '',
  );
  const perCell = field('One cell is', String(current?.measure?.per_cell ?? ''), 'number');
  perCell.input.step = 'any';
  perCell.input.min = '0';
  const unit = field('of (a unit)', current?.measure?.unit ?? '');
  const count = el('p', '', 'status-text');
  const parts = {
    orientation: orientation.label,
    size: size.label,
    width: width.label,
    height: height.label,
    cols: cols.label,
    rows: rows.label,
    aperture: aperture.label,
    perCell: perCell.label,
    unit: unit.label,
  };
  // A visual grid measures nothing, so it has no measure fields to confuse anyone.
  const shownParts = options.measured
    ? Object.values(parts)
    : Object.values(parts).filter((label) => label !== parts.perCell && label !== parts.unit);
  root.append(kind.label, ...shownParts, count);

  const shown = () => kind.input.value as GridKind;
  const sync = () => {
    const k = shown();

    parts.orientation.hidden = k !== 'hex';
    parts.size.hidden = k === 'rect';
    parts.width.hidden = k !== 'rect';
    parts.height.hidden = k !== 'rect';
    parts.cols.hidden = k === 'hex';
    parts.rows.hidden = k === 'hex';
    parts.aperture.hidden = k !== 'hex';
  };
  sync();
  kind.input.addEventListener('change', sync);

  function read(): GridDoc {
    const k = shown();
    const doc: GridDoc = {
      kind: k,
      cell:
        k === 'rect'
          ? {
              width: number(width.input, 'The width of a cell'),
              height: number(height.input, 'The height of a cell'),
            }
          : { size: number(size.input, 'The size of a cell') },
    };

    if (k === 'hex') {
      if (!orientation.input.value)
        throw new Error('Say whether the hexes are flat-topped or pointed-top.');

      doc.orientation = orientation.input.value as 'flat' | 'pointy';

      if (aperture.input.value) doc.sub = { aperture: Number(aperture.input.value) };
    } else if (Number(cols.input.value) > 1 || Number(rows.input.value) > 1) {
      doc.sub = { cols: Number(cols.input.value), rows: Number(rows.input.value) };
    }

    if (options.measured && (perCell.input.value || unit.input.value.trim())) {
      if (!perCell.input.value || !unit.input.value.trim()) {
        throw new Error('Give both how much a cell is and the unit, or neither.');
      }

      doc.measure = {
        per_cell: number(perCell.input, 'What a cell is'),
        unit: unit.input.value.trim(),
      };
    }

    return doc;
  }

  /** A line saying how many cells the grid has over a sheet, or why it cannot be said yet. */
  function describe(extent: BBox): string {
    try {
      const doc = read();
      const n = cellCount(doc as unknown as GridSpec, extent);

      return `About ${n.toLocaleString('en')} cells${n > 250_000 ? ': too many, a grid has at most 250,000' : ''}.`;
    } catch {
      return '';
    }
  }

  return {
    root,
    kind,
    read,
    describe,
    note(extent: BBox) {
      count.textContent = describe(extent);
    },
    onChange(run: () => void) {
      root.addEventListener('input', run);
      root.addEventListener('change', run);
    },
    set hidden(value: boolean) {
      root.hidden = value;
    },
  };
}
