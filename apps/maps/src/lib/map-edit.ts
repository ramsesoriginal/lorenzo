// Authoring a Map (ADR 0353): the toolbar, the tools the pointer belongs to while one is on, the
// panel for what is being drawn or what is selected, and every write. The renderer draws; this
// decides what a click means and asks the API. Nothing here is shown to those who may not write.
import {
  bezierPoints,
  type Cell,
  cellPolygon,
  type Geometry,
  type GridSpec,
  gridOf,
  inGrid,
  type MapModel,
  type MapViewController,
  type Overlay,
  ROLE_WORDS,
  ROLES,
  type Tool,
  type ToolEvent,
} from '@lorenzo/map-renderer';
import { client, LorenzoApiError, unwrap } from './api';
import { type CellFill, cellFill } from './cell-fill';
import {
  cellOfPoint,
  cellsGeometry,
  cellsOf,
  cellWords,
  MAX_CELLS_PER_PLACEMENT,
  snapCentre,
  snapCorner,
  toggleCell,
} from './cells-edit';
import { HELP, parseCommand } from './command-line';
import { button, el, field, groupTitle, message, select, statusLine } from './dom';
import {
  drawnCells,
  type ExampleMap,
  heldHere,
  mapNamed,
  sameGridKind,
  tilesOf,
} from './example-maps';
import { strokeLine, unitsPerPixel } from './freehand';
import {
  type Fit,
  fits,
  type Hints,
  nextSeed,
  type Region,
  regionOf,
  SEED_MOST,
  seedFrom,
  seedOf,
  stepName,
} from './generator';
import { GENERATORS } from './generators';
import {
  type Editable,
  editableOf,
  handlesOf,
  insertVertex,
  moveHandle,
  type Pt,
  placesInside,
  removeVertex,
  round2,
  toGeometry,
  translate,
} from './geometry-edit';
import { heightOf, rememberedHeight, rememberHeight, unitOf } from './height';
import {
  type BrushField,
  brushField,
  type EntryLine,
  entryLines,
  type Redraw,
  redraw,
  redrawWords,
  stepOf,
  strokeOf,
  withStroke,
} from './height-field';
import { type Change, createHistory, type Step, writeFor } from './history';
import { createKeyMap } from './keymap';
import {
  batchPlacements,
  type EntryChoice,
  findEntries,
  isPublicLocation,
  makeLocation,
  partsOf,
  putPlacement,
  type Row,
  readPlacements,
  removePlacement,
  rowState,
} from './map-api';
import {
  hasParts,
  isHeightLines,
  MAX_PARTS,
  movedPart,
  type PartRef,
  partAt,
  partNames,
  partShape,
  refAfterRemoval,
  withoutPart,
  withPart,
  withParts,
} from './parts-edit';
import { SPLINE_MAX_POINTS, splineCurve } from './spline';
import { splitPieces } from './split-entries';
import {
  BRUSH_ROLE,
  BRUSH_STEP,
  createOptionValues,
  TOOLS as DECLARED,
  EXAMPLE,
  FILL_FIRST,
  GROUP_NAMES,
  GROUPS,
  HEIGHT,
  numberFor,
  type OptionValue,
  optionsOf,
  RADIUS,
  ROLE,
  SEED,
  SNAP,
  STRENGTH,
  searchTools,
  TENSION,
  TOLERANCE,
  type ToolDecl,
  type ToolOption,
  toolById,
  toolsOf,
  UNIT,
  usable,
} from './tools';
import { moved, TRANSFORM_WORDS, type Transform } from './transform';

export type EditorContext = {
  tenant: string;
  mapId: string;
  /** Whether everyone in the library may see the Map: the default for a new Location. */
  mapIsPublic: boolean;
  /** The sheet the Map draws on, `[x0, y0, x1, y1]`. */
  extent: [number, number, number, number];
  /** The Map's grid, its system's own or its view's, when it has one (ADR 0356). */
  grid: () => GridSpec | null;
  /** A sphere: positions are longitudes and latitudes, and a circle and cells are not drawn (ADR 0359). */
  sphere?: boolean;
  view: () => MapViewController;
  rows: () => Row[];
  /** Replaces the placements the page shows. */
  setRows: (rows: Row[]) => void;
  select: (id: string | null) => void;
};

export type Editor = {
  /** The switch and the tools; always there for those who may write. */
  toolbar: HTMLElement;
  /** What is being drawn, or what is selected, with the controls for it. */
  panel: HTMLElement;
  /** What was done, each step by name, with a way back to any of them. */
  history: HTMLElement;
  /** Puts an entry on the Map as a pin at a point of the drawing. */
  placeEntry(entry: { id: string; name: string }, at: [number, number]): Promise<void>;
  /** The line under the Map that takes typed commands. */
  commandLine: HTMLElement;
  /** Whether the tools are on. */
  editing(): boolean;
  /** The page's selection changed. */
  selected(id: string | null): void;
  destroy(): void;
};

/** What the Cells tool says to change when a region is over a drawing's limits (ADR 0481). */
const CELL_HINTS: Hints = {
  vertices: 'Draw fewer cells, or the rest for another entry.',
  parts: 'Draw fewer cells, or the rest for another entry.',
  bytes: 'Draw fewer cells, or the rest for another entry.',
  shape: 'Draw the region again.',
};

/** What the Height brush says to change when its lines are over a limit (ADR 0480). */
const BRUSH_HINTS: Hints = {
  vertices: 'Use a larger Step, or brush a smaller place.',
  parts: 'Use a larger Step.',
  bytes: 'Use a larger Step, or brush a smaller place.',
  shape: 'Brush it again.',
};

type ToolName =
  | 'select'
  | 'pin'
  | 'circle'
  | 'line'
  | 'spline'
  | 'freehand'
  | 'area'
  | 'cells'
  | 'height-line'
  | 'height-brush'
  | 'cave-system'
  | 'marching-squares'
  | 'wave-function-collapse';

const TOOLS: [ToolName, string][] = [
  ['select', 'Select'],
  ['pin', 'Pin'],
  ['circle', 'Circle'],
  ['line', 'Line'],
  ['spline', 'Spline'],
  ['freehand', 'Freehand'],
  ['height-line', 'Height line'],
  ['height-brush', 'Height brush'],
  ['cave-system', 'Cave system'],
  ['marching-squares', 'Fill by marching squares'],
  ['wave-function-collapse', 'Fill by wave function collapse'],
  ['area', 'Area'],
  ['cells', 'Cells'],
];

const STROKES: [string, string][] = [
  ['', "The theme's own"],
  ['solid', 'Solid'],
  ['dashed', 'Dashed'],
  ['dotted', 'Dotted'],
  ['double', 'Double'],
  ['none', 'Hit only (draws no line)'],
];

const WEIGHTS: [string, string][] = [
  ['', "The theme's own"],
  ['hairline', 'Hairline'],
  ['thin', 'Thin'],
  ['regular', 'Regular'],
  ['thick', 'Thick'],
  ['heavy', 'Heavy'],
];

const ROLE_OPTIONS: [string, string][] = [
  ['', 'No role'],
  ...ROLES.map((role): [string, string] => [
    role,
    ROLE_WORDS[role].charAt(0).toUpperCase() + ROLE_WORDS[role].slice(1),
  ]),
];

const BATCH_MAX = 100;

/** How near a line or a pin a press chooses that part of a placement, in screen pixels. */
const PART_REACH = 8;

const same = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 0.01;
const asText = (error: unknown) =>
  error instanceof LorenzoApiError ? error.message : message(error);

export function createEditor(context: EditorContext): Editor {
  const history = createHistory();
  const toolbar = el('div', '', 'row map-edit-bar');
  toolbar.setAttribute('role', 'group');
  toolbar.setAttribute('aria-label', 'Edit this map');
  const panel = el('div', '', 'stack-tight map-edit-panel');
  const status = statusLine();

  let editing = false;
  let toolName: ToolName = 'select';
  let target: { id?: string; name: string; create?: { isPublic: boolean } } | null = null;
  let draft: Pt[] = [];
  // The cells chosen so far by the Cells tool, counted from 0.
  let cells: Cell[] = [];
  // What the tools' options are set to (ADR 0470), Snap to the grid among them (ADR 0356).
  const optionValues = createOptionValues();
  // The height and unit last drawn on this Map in this browser are offered again (ADR 0473).
  const keptHeight = rememberedHeight(context.mapId);
  if (keptHeight) {
    const heightLine = toolById('height-line') as ToolDecl;
    optionValues.set(heightLine, HEIGHT, keptHeight.value);
    optionValues.set(heightLine, UNIT, keptHeight.unit);
  }
  let rubber: Pt | null = null;
  // The samples of a freehand stroke while the pointer is held (ADR 0472).
  let stroke: Pt[] | null = null;
  let selectedId: string | null = null;
  // The selected shape while a handle or the shape is being dragged, drawn as an overlay.
  let working: Editable | null = null;
  let dragging: { handle: string | null; base: Editable; start: Pt; by: Pt } | null = null;
  // A generator (ADR 0475): the placement its region was taken from, whether the view is split to
  // compare, where, and the result last worked out with what it was worked out from.
  let regionId: string | null = null;
  let compare = false;
  let divide = 0.5;
  let made: {
    key: string;
    region: Region;
    geometry: Geometry | null;
    count: string;
    fit: Fit;
    /** For a fill of cells (ADR 0479): what each tile entry gains and has afterwards. */
    cells?: CellFill;
    /** For the Height brush (ADR 0480): which lines go and which are drawn. */
    brush?: Extract<Redraw, { ok: true }>;
  } | null = null;
  // The Height brush (ADR 0480): the field of the entry being brushed and what the strokes have
  // moved it by, in steps; the stroke under way; and where the pointer is.
  let brush: {
    key: string;
    flat: number;
    lines: EntryLine[];
    field: BrushField;
    raised: Float64Array;
    strokes: number;
  } | null = null;
  let brushStroke: { pts: Pt[]; lower: boolean } | null = null;
  let brushAt: Pt | null = null;
  let syncGenerator: () => void = () => {};
  // The Maps a fill of cells may learn from (ADR 0479), read once the tool is first chosen, and
  // the example Map read for it when it is not this one.
  let exampleMaps: ExampleMap[] | null = null;
  let exampleMapsRead: Promise<void> | null = null;
  let example: {
    id: string;
    name: string;
    grid: GridSpec;
    extent: [number, number, number, number];
    rows: Row[];
  } | null = null;
  let exampleProblem: string | null = null;
  // The part of the selected placement being changed, when it has several (ADR 0474).
  let selectedPart: PartRef | null = null;
  let busy = false;

  const say = (text: string, failed = false) => {
    status.textContent = text;
    status.classList.toggle('error-text', failed);
    status.setAttribute('role', failed ? 'alert' : 'status');
  };
  const gridNow = () => context.grid();
  /** The tools that take a point at a time and finish with Enter. */
  const pathTool = () =>
    toolName === 'line' ||
    toolName === 'spline' ||
    toolName === 'area' ||
    toolName === 'height-line';
  /** The declaration of the tool that is on. */
  const toolDecl = (): ToolDecl => toolById(toolName) as ToolDecl;
  const snapped = (kind: 'centre' | 'corner', p: Pt): Pt => {
    const grid = gridNow();
    if (!grid || !optionValues.get(toolDecl(), SNAP)) return p;
    return kind === 'centre'
      ? snapCentre(grid, context.extent, p)
      : snapCorner(grid, context.extent, p);
  };
  const snapHandle = (handle: string, p: Pt): Pt => {
    if (handle === 'r') return p;
    return snapped(handle === 'p' || handle === 'c' ? 'centre' : 'corner', p);
  };
  const rowOf = (id: string | null) =>
    id ? context.rows().find((row) => row.id === id) : undefined;
  const inSheet = (p: Pt) =>
    p[0] >= context.extent[0] &&
    p[0] <= context.extent[2] &&
    p[1] >= context.extent[1] &&
    p[1] <= context.extent[3];

  /** Whether a placement is a region of whole cells of this Map's grid: the Cells panel's own. */
  const isCellsRow = (row: Row) => {
    const grid = gridNow();
    return Boolean(grid && cellsOf(row.geometry as unknown as Geometry, grid, context.extent));
  };

  /**
   * What of a placement is being changed (ADR 0474): the whole of one simple part, or the chosen
   * part of several, with the geometry a changed shape makes of it.
   */
  function focusOf(row: Row): {
    shape: Editable | null;
    part: PartRef | null;
    write(shape: Editable): Geometry;
  } {
    const geometry = row.geometry as unknown as Geometry;
    // A drawing of cells of several parts is changed by its cells; one area along the grid's
    // lines, which reads as cells too (ADR 0481), keeps its points.
    if (isCellsRow(row) && hasParts(geometry)) {
      return { shape: null, part: null, write: () => geometry };
    }
    if (!hasParts(geometry)) return { shape: editableOf(geometry), part: null, write: toGeometry };
    const ref = selectedPart;
    return {
      shape: ref ? partShape(geometry, ref) : null,
      part: ref,
      write: (shape) => (ref ? withPart(geometry, ref, shape) : geometry),
    };
  }

  /** Whether the tool previews and applies (ADR 0475). */
  const generating = () => toolDecl().generator === true;
  /** Whether it is the Height brush, which previews from strokes rather than a seed (ADR 0480). */
  const brushing = () => toolDecl().brush === true;
  /** How far a stroke of the brush reaches, in drawing units. */
  const radiusNow = () =>
    ((optionValues.get(toolDecl(), RADIUS) ?? RADIUS.first ?? 5) / 100) *
    (context.extent[2] - context.extent[0]);

  /**
   * The field of the entry the brush is for, made again when the entry or its drawing changes; its
   * Step and Unit start from the entry's lines. Refused for an entry drawn as anything else.
   */
  function brushNow():
    | { ok: true; brush: NonNullable<typeof brush> }
    | { ok: false; why: string }
    | null {
    if (!target) return null;
    const row = target.id ? rowOf(target.id) : undefined;
    const geometry = row ? (row.geometry as unknown as Geometry) : null;
    const read = entryLines(target.name, geometry);
    if (!read.ok) return read;
    const decl = toolDecl();
    const flat = optionValues.get(decl, FILL_FIRST) ?? 0;
    const key = JSON.stringify([target.id ?? target.name, geometry]);
    if (brush?.key !== key) {
      const field = brushField(context.extent, read.lines, flat);
      brush = {
        key,
        flat,
        lines: read.lines,
        field,
        raised: new Float64Array(field.cols * field.rows),
        strokes: 0,
      };
      const step = stepOf(read.lines);
      if (step !== null) optionValues.set(decl, BRUSH_STEP, step);
      if (read.unit) optionValues.set(decl, UNIT, read.unit);
    } else if (read.lines.length === 0 && brush.flat !== flat) {
      // Flat ground at another first height: what the strokes moved stays.
      brush.field = brushField(context.extent, [], flat);
      brush.flat = flat;
    }
    return { ok: true, brush };
  }

  /** One stroke of the brush through some points: it raises, or lowers with Shift. */
  function brushStrokeAt(pts: readonly Pt[], lower: boolean): boolean {
    const now = brushNow();
    if (!now) {
      say('Choose the entry whose height lines you are changing first.', true);
      return false;
    }
    if (!now.ok) {
      say(now.why, true);
      return false;
    }
    const amount = (optionValues.get(toolDecl(), STRENGTH) ?? 1) * (lower ? -1 : 1);
    now.brush.raised = withStroke(
      now.brush.raised,
      strokeOf(now.brush.field, pts, radiusNow()),
      amount,
    );
    now.brush.strokes += 1;
    refresh();
    return true;
  }
  /** Whether it is the one that writes cells for the entries of an example (ADR 0479). */
  const fillsCells = () => toolDecl().cells === true;

  /** The generator that is the tool, when the tool is one. */
  const generator = () => (toolDecl().generator ? GENERATORS[toolName] : undefined);

  /** The seed of the tool that is on: the page draws the first, from the browser's randomness. */
  function seedNow(): number {
    const decl = toolDecl();
    const kept = optionValues.get(decl, SEED);
    if (kept !== null) return kept;
    const first = seedFrom(crypto.getRandomValues(new Uint32Array(1))[0] ?? 0);
    optionValues.set(decl, SEED, first);
    return first;
  }

  /**
   * What the generator that is on would draw, from the Map as it is and the options as they are
   * set (ADR 0475). Worked out again only when one of those has changed; never stored.
   */
  function generated() {
    if (!generating()) return null;
    const decl = toolDecl();
    if (brushing()) return brushed();
    const from = rowOf(regionId);
    const seed = seedNow();
    if (fillsCells()) {
      const grid = gridNow();
      if (!grid) return null;
      const region = regionOf(
        from ? { name: from.name, geometry: from.geometry as unknown as Geometry } : null,
        context.extent,
      );
      const chosen = optionValues.get(decl, EXAMPLE);
      const waiting = (why: string) => {
        const key = JSON.stringify([toolName, 'waiting', chosen, why, from?.id ?? null]);
        if (made?.key !== key) {
          made = { key, region, geometry: null, count: '', fit: { ok: false, why } };
        }
        return made;
      };
      // The example: this Map, or the Map chosen once it has been read.
      const source =
        chosen === ''
          ? { name: 'this Map', grid, extent: context.extent, rows: context.rows() }
          : example?.id === chosen
            ? example
            : null;
      if (!source) return waiting(exampleProblem ?? 'Reading the example Map.');
      // The area the fill works in is its frame, never one of its tiles.
      const drawn = drawnCells(
        chosen === '' && region.kind !== 'sheet'
          ? source.rows.filter((row) => row.id !== from?.id)
          : source.rows,
        source.grid,
        source.extent,
      );
      const here =
        chosen === '' ? [] : context.rows().map((row) => [row.id, row.geometry] as const);
      const key = JSON.stringify([
        toolName,
        seed,
        chosen,
        from?.id ?? null,
        from?.geometry ?? null,
        grid,
        drawn.map(({ row, cells }) => [row.id, cells]),
        here,
      ]);
      if (made?.key === key) return made;
      const tiles = tilesOf(drawn);
      if (chosen !== '' && !tiles.some((tile) => tile.cells.length > 0)) {
        return waiting(
          `${source.name} has no entries drawn as cells, and the fill learns from them. Choose another example.`,
        );
      }
      // On this Map the example is what each entry holds; from another, what this Map holds of it.
      const held =
        chosen === ''
          ? { ok: true as const, held: new Map(tiles.map((tile) => [tile.id, tile.cells])) }
          : heldHere(tiles, context.rows(), grid, context.extent);
      if (!held.ok) return waiting(held.why);
      const plan = cellFill(grid, context.extent, tiles, held.held, region, seed);
      made = {
        key,
        region,
        geometry: null,
        count: plan.ok ? plan.count : '',
        fit: plan.ok ? { ok: true } : { ok: false, why: plan.why },
        cells: plan,
      };
      return made;
    }
    const def = generator();
    if (!def) return null;
    // Every option but the role, which changes what is written and not what is drawn.
    const set = (decl.options ?? []).map((option) =>
      option.id === ROLE.id ? null : optionValues.get(decl, option),
    );
    const key = JSON.stringify([toolName, seed, set, from?.id ?? null, from?.geometry ?? null]);
    if (made?.key === key) return made;
    const region = regionOf(
      from ? { name: from.name, geometry: from.geometry as unknown as Geometry } : null,
      context.extent,
    );
    const result = def.run(region, seed, {
      number: (option) => optionValues.get(decl, option),
      text: (option) => optionValues.get(decl, option),
    });
    made = {
      key,
      region,
      geometry: result.geometry,
      count: result.count,
      // What a person must still give comes before any limit: it is theirs to answer first.
      fit:
        result.needs && result.geometry
          ? { ok: false, why: result.needs }
          : fits(result.geometry, def.hints),
    };
    return made;
  }

  /** What the Height brush would draw (ADR 0480): the entry's lines, some kept, some drawn anew. */
  function brushed() {
    const decl = toolDecl();
    const region = regionOf(null, context.extent);
    const refused = (why: string) => {
      const key = JSON.stringify(['brush', 'refused', why]);
      if (made?.key !== key)
        made = { key, region, geometry: null, count: '', fit: { ok: false, why } };
      return made;
    };
    const now = brushNow();
    if (!now) return refused('Choose the entry whose height lines you are changing.');
    if (!now.ok) return refused(now.why);
    const b = now.brush;
    const step = optionValues.get(decl, BRUSH_STEP);
    const unit = optionValues.get(decl, UNIT);
    const first = optionValues.get(decl, FILL_FIRST);
    const missing = [
      ...(step === null ? ['the Step'] : []),
      ...(unit === '' ? ['the Unit'] : []),
      ...(b.lines.length === 0 && first === null ? ['the First height'] : []),
    ];
    if (missing.length > 0) {
      const words =
        missing.length === 1
          ? missing[0]
          : `${missing.slice(0, -1).join(', ')} and ${missing[missing.length - 1]}`;
      return refused(`Give ${words} first: they are never assumed.`);
    }
    if (b.strokes === 0) {
      return refused('Drag on the Map to raise the land, with Shift held to lower it.');
    }
    const key = JSON.stringify(['brush', b.key, b.strokes, step, unit, first]);
    if (made?.key === key) return made;
    const result = redraw(b.field, b.lines, b.raised, step as number, first ?? 0, context.extent);
    if (!result.ok) return refused(result.why);
    const row = target?.id ? rowOf(target.id) : undefined;
    const before = row ? (row.geometry as unknown as Geometry) : null;
    const parts = [
      ...result.keep.map((part) => before?.parts[part]).filter((part) => part !== undefined),
      // Each line a smooth curve through its points (ADR 0491).
      ...result.add.map((line) => ({ ...line.curve, value: line.value, unit })),
    ];
    if (parts.length === 0) {
      return refused(
        `This would leave ${target?.name ?? 'the entry'} with no line. Remove from this map takes it off the Map.`,
      );
    }
    const geometry: Geometry = { format: 'lorenzo.geometry/1', parts };
    made = {
      key,
      region,
      geometry,
      count: redrawWords(result),
      fit:
        result.redrawn + result.fresh + result.gone === 0
          ? { ok: false, why: 'The strokes change no line yet. Go on, or use a larger Strength.' }
          : fits(geometry, BRUSH_HINTS),
      brush: result,
    };
    return made;
  }

  // --- what is drawn over the map -------------------------------------------------------------

  function shapeOverlay(shape: Editable, id: string, handles: boolean, active?: string): Overlay {
    const out: Overlay[number][] = [];
    if (shape.kind === 'circle') out.push({ id, kind: 'disc', at: shape.at, r: shape.r });
    else if (shape.kind === 'line' || shape.kind === 'area') {
      out.push({ id, kind: 'line', pts: shape.pts, closed: shape.kind === 'area' });
    } else if (shape.kind === 'spline') {
      out.push({ id, kind: 'line', pts: splineCurve(shape.pts, shape.tension) });
    }
    if (handles) {
      for (const handle of handlesOf(shape)) {
        out.push({ id: handle.id, kind: 'handle', at: handle.at, active: handle.id === active });
      }
    }
    return out;
  }

  function overlay(): Overlay {
    if (!editing) return [];
    if (toolName === 'cells') {
      const grid = gridNow();
      if (!grid) return [];
      return cells.map((cell) => ({
        id: `c${cell[0]}_${cell[1]}`,
        kind: 'line' as const,
        pts: cellPolygon(grid, context.extent, cell),
        closed: true,
      }));
    }
    if (toolName === 'freehand') {
      return stroke && stroke.length > 1 ? [{ id: 'stroke', kind: 'line', pts: stroke }] : [];
    }
    if (fillsCells()) {
      // The preview of a fill of cells: each tile's cells as one shape, in the tile's tone.
      const grid = gridNow();
      if (!grid) return [];
      return (generated()?.cells?.tiles ?? []).flatMap((tile): Overlay[number][] =>
        tile.gained.length === 0
          ? []
          : [
              {
                id: `tile${tile.id}`,
                kind: 'area',
                rings: tile.gained.map((cell) => cellPolygon(grid, context.extent, cell)),
                tone: tile.tone,
                clipped: true,
              },
            ],
      );
    }
    if (brushing()) {
      // The lines that would go, dashed; those that would be drawn; the stroke; the brush itself.
      const out: Overlay[number][] = [];
      const now = generated();
      for (const part of now?.brush?.drop ?? []) {
        const line = brush?.lines.find((one) => one.part === part);
        if (line)
          out.push({
            id: `gone${part}`,
            kind: 'line',
            pts: line.pts,
            preview: true,
            clipped: true,
          });
      }
      (now?.brush?.add ?? []).forEach((line, i) => {
        out.push({ id: `new${i}`, kind: 'line', pts: bezierPoints(line.curve), clipped: true });
      });
      if (brushStroke && brushStroke.pts.length > 1) {
        out.push({ id: 'stroke', kind: 'line', pts: brushStroke.pts, preview: true });
      }
      if (brushAt)
        out.push({ id: 'brush', kind: 'disc', at: brushAt, r: radiusNow(), preview: true });
      return out;
    }
    if (generating()) {
      // The preview: what Apply would write, drawn over the Map and never stored.
      return (generated()?.geometry?.parts ?? []).flatMap((part, i): Overlay[number][] =>
        part.shape === 'polygon'
          ? [{ id: `made${i}`, kind: 'area', rings: part.rings, clipped: true }]
          : part.shape === 'polyline'
            ? [{ id: `made${i}`, kind: 'line', pts: part.pts, clipped: true }]
            : [],
      );
    }
    if (toolName !== 'select') {
      if (draft.length === 0) return [];
      const last = draft[draft.length - 1] as Pt;
      const out: Overlay[number][] = [];
      if (toolName === 'circle') {
        const r = rubber ? Math.hypot(rubber[0] - last[0], rubber[1] - last[1]) : 0;
        if (r > 0) out.push({ id: 'draft', kind: 'disc', at: last, r });
      } else if (toolName === 'spline') {
        // The curve so far, and the curve it would be with the pointer as its next point.
        const tension = optionValues.get(toolDecl(), TENSION) ?? 0.5;
        out.push({ id: 'draft', kind: 'line', pts: splineCurve(draft, tension) });
        if (rubber) {
          out.push({
            id: 'band',
            kind: 'line',
            pts: splineCurve([...draft, rubber], tension),
            preview: true,
          });
        }
      } else {
        out.push({ id: 'draft', kind: 'line', pts: draft });
        if (rubber) out.push({ id: 'band', kind: 'line', pts: [last, rubber], preview: true });
      }
      for (const [i, at] of draft.entries()) out.push({ id: `d${i}`, kind: 'handle', at });
      return out;
    }
    const row = rowOf(selectedId);
    const shape = working ?? (row ? focusOf(row).shape : null);
    return shape ? shapeOverlay(shape, 'shape', true, dragging?.handle ?? undefined) : [];
  }

  const refresh = () => {
    context.view().setOverlay(overlay());
    syncGenerator();
  };

  // --- writing --------------------------------------------------------------------------------

  const upsert = (row: Row) => {
    const rows = context.rows();
    return rows.some((r) => r.id === row.id)
      ? rows.map((r) => (r.id === row.id ? row : r))
      : [...rows, row];
  };

  // The write on its way, so a command typed meanwhile waits for it rather than being dropped.
  let writing: Promise<void> = Promise.resolve();

  async function guarded(action: () => Promise<void>) {
    if (busy) return;
    busy = true;
    let done: () => void = () => {};
    writing = new Promise((resolve) => {
      done = resolve;
    });
    // While a write is on its way the panel takes no press: one made then would be dropped, and
    // would have been made against a drawing that is about to change.
    panel.inert = true;
    panel.setAttribute('aria-busy', 'true');
    try {
      await action();
    } catch (error) {
      say(asText(error), true);
    } finally {
      busy = false;
      done();
      panel.inert = false;
      panel.removeAttribute('aria-busy');
      renderToolbar();
    }
  }

  async function reload() {
    context.setRows((await readPlacements(context.tenant, context.mapId)).rows);
  }

  async function saveRow(row: Row, patch: Partial<ReturnType<typeof rowState>>) {
    await guarded(async () => {
      const before = rowState(row);
      const after = { ...before, ...patch };
      const saved = await putPlacement(context.tenant, context.mapId, row.id, after);
      history.record([{ entry: row.id, before, after: rowState(saved) }], `Changed ${row.name}`);
      context.setRows(upsert(saved));
      working = null;
      say('Saved.');
      render();
      refresh();
    });
  }

  async function removeRow(row: Row) {
    await guarded(async () => {
      await removePlacement(context.tenant, context.mapId, row.id);
      history.record(
        [{ entry: row.id, before: rowState(row), after: null }],
        `Removed ${row.name}`,
      );
      context.setRows(context.rows().filter((r) => r.id !== row.id));
      context.select(null);
      say(`${row.name} is no longer on this map.`);
    });
  }

  async function finish(geometry: Geometry, how: { role?: string | null; step?: string } = {}) {
    const chosen = target;
    if (!chosen) return;
    await guarded(async () => {
      let id = chosen.id;
      if (!id && chosen.create) {
        const made = await makeLocation(context.tenant, chosen.name, chosen.create.isPublic);
        id = made.id;
        // The Location exists now: a retry must not make another.
        target = { id, name: made.name };
      }
      if (!id) return;
      const before = rowOf(id);
      // The two roles a tool chooses: a pin is a site (ADR 0353), a height line an isoline (ADR 0473).
      const role =
        how.role !== undefined
          ? how.role
          : toolName === 'pin'
            ? 'site'
            : toolName === 'height-line'
              ? 'isoline'
              : null;
      const saved = await putPlacement(context.tenant, context.mapId, id, {
        geometry,
        role,
        style: null,
        z: 0,
      });
      history.record(
        [{ entry: id, before: before ? rowState(before) : null, after: rowState(saved) }],
        how.step ?? `${before ? 'Redrew' : 'Drew'} ${saved.name}`,
      );
      context.setRows(upsert(saved));
      leaveGenerator();
      draft = [];
      cells = [];
      rubber = null;
      target = null;
      toolName = 'select';
      context.view().setTool(tool());
      context.select(id);
      say(`${saved.name} is on the map.`);
      render();
      refresh();
    });
  }

  async function applyStep(step: Step, direction: 'undo' | 'redo') {
    const put: NonNullable<Parameters<typeof batchPlacements>[2]['put']> = [];
    const remove: string[] = [];
    for (const change of step) {
      const write = writeFor(change, direction);
      if ('put' in write) {
        put.push({
          entry_id: write.put.entry_id,
          geometry: write.put.geometry,
          role: write.put.role,
          style: write.put.style,
          z: write.put.z,
        });
      } else remove.push(write.remove);
    }
    await batchPlacements(context.tenant, context.mapId, { put, remove });
    await reload();
    if (selectedId && !rowOf(selectedId)) context.select(null);
    say(direction === 'undo' ? 'Undone.' : 'Done again.');
    render();
    refresh();
  }

  const undo = () =>
    guarded(async () => {
      const step = history.undo();
      if (!step) return;
      try {
        await applyStep(step, 'undo');
      } catch (error) {
        history.redo();
        throw error;
      }
    });
  const redo = () =>
    guarded(async () => {
      const step = history.redo();
      if (!step) return;
      try {
        await applyStep(step, 'redo');
      } catch (error) {
        history.undo();
        throw error;
      }
    });

  /** Puts an entry on the Map as a pin at a point (dropped from the outliner, or its Place button). */
  async function placeEntry(entry: { id: string; name: string }, at: Pt) {
    await guarded(async () => {
      const before = rowOf(entry.id);
      const saved = await putPlacement(context.tenant, context.mapId, entry.id, {
        geometry: toGeometry({ kind: 'point', at }) as unknown as Record<string, unknown>,
        role: before?.role ?? 'site',
        style: null,
        z: 0,
      });
      history.record(
        [{ entry: entry.id, before: before ? rowState(before) : null, after: rowState(saved) }],
        `${before ? 'Moved' : 'Placed'} ${saved.name}`,
      );
      context.setRows(upsert(saved));
      context.select(entry.id);
      say(`${saved.name} is on the map.`);
      render();
      refresh();
    });
  }

  // The command line (MP6): a typed twin of the pointer, one answer per line.
  const commandLine = el('form', '', 'map-command row-tight');
  commandLine.setAttribute('aria-label', 'Command line');
  const commandInput = el('input', '', 'text-input grow');
  commandInput.type = 'text';
  commandInput.autocomplete = 'off';
  commandInput.spellcheck = false;
  commandInput.placeholder = 'Tool or command; HELP lists them';
  commandInput.setAttribute('aria-label', 'Command');
  const commandAnswer = el('p', '', 'status-text map-command-answer');
  commandAnswer.setAttribute('role', 'status');
  commandLine.append(commandInput, commandAnswer);
  const answer = (text: string, failed = false) => {
    commandAnswer.textContent = text;
    commandAnswer.dataset.failed = String(failed);
  };
  commandLine.addEventListener('submit', (event) => {
    event.preventDefault();
    const line = commandInput.value;
    commandInput.value = '';
    void runCommand(line);
  });
  commandInput.addEventListener('keydown', (event) => {
    event.stopPropagation();
    if (event.key === 'Escape') commandInput.blur();
  });
  /** What the line asks for next, in the tool's own words. */
  function nextPrompt(): string {
    if (!target && toolName !== 'cells') return 'Choose what you are drawing first.';
    switch (toolName) {
      case 'pin':
        return 'Type the point, x,y.';
      case 'circle':
        return draft.length === 0 ? 'Type the centre, x,y.' : 'Type a point on the edge, x,y.';
      case 'freehand':
        return 'Drag on the map to draw. The Line tool takes typed points.';
      case 'height-brush':
        return 'Drag on the map, or type RAISE x,y or LOWER x,y; then APPLY or DISCARD.';
      case 'cave-system':
      case 'marching-squares':
      case 'wave-function-collapse':
        return 'Set the options, then APPLY or DISCARD.';
      case 'line':
      case 'height-line':
      case 'spline':
      case 'area':
        return `${draft.length} point${draft.length === 1 ? '' : 's'}. Type the next point, x,y, or DONE.`;
      default:
        return 'Click a cell, then DONE.';
    }
  }

  async function runCommand(line: string) {
    // A command typed while a change is being written is carried out once it is written.
    await writing;
    const command = parseCommand(line, DECLARED, {
      ...here(),
      tool: editing ? toolDecl() : undefined,
    });
    if (!command) return;
    switch (command.kind) {
      case 'error':
        answer(command.message, true);
        return;
      case 'help':
        answer(HELP);
        return;
      case 'option':
        if (command.option.type === 'map') {
          await readExampleMaps();
          const id = mapNamed(exampleMaps ?? [], String(command.value));
          if (id === null) {
            answer(
              `No Map of the library with a grid of this kind is called ${command.value}.`,
              true,
            );
            return;
          }
          setOption(command.option, id);
          await readExample(id);
          answer(`Example is ${exampleName()}.`);
          return;
        }
        setOption(command.option, command.value);
        answer(
          typeof command.value !== 'boolean'
            ? `${command.option.name} is ${command.value}.`
            : `${command.option.name} is ${command.value ? 'on' : 'off'}.`,
        );
        return;
      case 'roll':
      case 'apply':
      case 'discard':
      case 'compare':
        // A generator's own commands (ADR 0475): they mean something only while one is the tool.
        if (!editing || !generating()) {
          answer('That is a command of a generator, and no generator is the tool.', true);
          return;
        }
        if (command.kind === 'roll' && !optionsOf(toolDecl(), here()).includes(SEED)) {
          answer(`${toolDecl().name} has no seed to roll.`, true);
          return;
        }
        if (command.kind === 'roll') {
          setOption(SEED, nextSeed(seedNow()));
          answer(`Seed ${seedNow()}: ${generatedWords()}`);
        } else if (command.kind === 'compare') {
          setCompare(command.on);
          answer(
            command.on ? 'The view is split: the Map as it is on the left.' : 'The view is whole.',
          );
        } else if (command.kind === 'discard') {
          discardGenerator();
          answer('Nothing was drawn.');
        } else {
          answer(await applyGenerator());
        }
        return;
      case 'transform':
      case 'copy': {
        const row = editing ? rowOf(selectedId) : undefined;
        if (!row) {
          answer('Select a drawing first.', true);
          return;
        }
        if (context.sphere) {
          answer('A drawing on a sphere is not mirrored, turned or copied here.', true);
          return;
        }
        if (command.kind === 'transform') {
          const said = await moveRow(row, command.how);
          answer(said, status.classList.contains('error-text'));
          return;
        }
        // A name one entry has exactly is that entry; any other is a new Location.
        const found = (await findEntries(context.tenant, command.name)).filter(
          (entry) => entry.name.toLowerCase() === command.name.toLowerCase(),
        );
        if (found.length > 1) {
          answer(`Several entries are called ${command.name}; choose one in the panel.`, true);
          return;
        }
        const one = found[0];
        const said = await copyRow(
          row,
          command.how,
          one ? { id: one.id, name: one.name } : { name: command.name },
        );
        answer(said, status.classList.contains('error-text'));
        return;
      }
      case 'brush':
        if (!editing || !brushing()) {
          answer('RAISE and LOWER are commands of the Height brush, and it is not the tool.', true);
          return;
        }
        if (brushStrokeAt([command.at], command.lower)) answer(generatedWords());
        else answer(status.textContent ?? '', true);
        return;
      case 'planned':
      case 'unavailable':
        answer(unavailable(command.tool), true);
        return;
      case 'tool':
        setTool(command.tool.id as ToolName);
        answer(`${command.tool.name} is the tool.`);
        return;
      case 'point': {
        if (!editing || toolName === 'select') {
          answer('Choose a drawing tool first, for example Line.', true);
          return;
        }
        drawTool.click?.({
          point: command.at,
          hit: null,
          handle: null,
          shift: false,
          detail: 0,
        });
        answer(nextPrompt());
        return;
      }
      case 'done': {
        if (!editing || toolName === 'select' || toolName === 'pin') {
          answer('Nothing is being drawn to finish.', true);
          return;
        }
        if (toolName === 'cells') finishCells();
        else if (pathTool()) finishDraft();
        else if (toolName === 'freehand') answer('A stroke finishes when you let go.', true);
        else if (generating()) answer('APPLY draws what is previewed.', true);
        else answer('A circle finishes with its second point.', true);
        return;
      }
      case 'undo':
        await undo();
        answer('Undone.');
        return;
      case 'redo':
        await redo();
        answer('Done again.');
        return;
      case 'fit':
        context.view().fit();
        answer('The whole sheet is in view.');
        return;
      case 'select': {
        const wanted = command.name.toLowerCase();
        const row = context.rows().find((r) => r.name.toLowerCase() === wanted);
        if (!row) {
          answer(`Nothing named “${command.name}” is on this Map.`, true);
          return;
        }
        context.select(row.id);
        answer(`${row.name} is selected.`);
        return;
      }
      case 'place': {
        try {
          const wanted = command.name.toLowerCase();
          const found = (await findEntries(context.tenant, command.name, 50)).find(
            (place) => place.name.toLowerCase() === wanted,
          );
          if (!found) {
            answer(`Nothing named “${command.name}” in this library.`, true);
            return;
          }
          await placeEntry(found, command.at);
          answer(`${found.name} is on the map at ${command.at[0]},${command.at[1]}.`);
        } catch (error) {
          answer(asText(error), true);
        }
        return;
      }
    }
  }

  /** Steps back, or forward, to any point in what was done. */
  const goTo = (index: number) =>
    guarded(async () => {
      while (history.position() > index) {
        const step = history.undo();
        if (!step) break;
        try {
          await applyStep(step, 'undo');
        } catch (error) {
          history.redo();
          throw error;
        }
      }
      while (history.position() < index) {
        const step = history.redo();
        if (!step) break;
        try {
          await applyStep(step, 'redo');
        } catch (error) {
          history.undo();
          throw error;
        }
      }
    });

  // The list of what was done (MP6): each step by its name, a step back to any of them, the undone
  // ones still listed until something new is done.
  const historyPanel = el('div', '', 'stack-tight map-history');
  function renderHistory() {
    const list = el('ol', '', 'list map-history-list');
    const start = el('li');
    const startButton = el('button', 'Before any change', 'btn btn-secondary');
    startButton.type = 'button';
    startButton.setAttribute('aria-current', String(history.position() === 0));
    startButton.disabled = busy;
    startButton.addEventListener('click', () => void goTo(0));
    start.append(startButton);
    list.append(start);
    history.entries().forEach((entry, index) => {
      const item = el('li');
      const node = el('button', entry.name, 'btn btn-secondary');
      node.type = 'button';
      node.disabled = busy;
      node.dataset.state = entry.done ? 'done' : 'undone';
      if (!entry.done) node.append(el('span', 'undone', 'chip'));
      node.setAttribute('aria-current', String(history.position() === index + 1));
      node.addEventListener('click', () => void goTo(index + 1));
      item.append(node);
      list.append(item);
    });
    historyPanel.replaceChildren(
      history.entries().length
        ? list
        : el('p', 'Nothing has been done on this Map yet.', 'status-text'),
    );
  }

  async function placeChildren(
    row: Row,
    shape: Editable,
    children: { id: string; name: string }[],
  ) {
    await guarded(async () => {
      const chosen = children.slice(0, BATCH_MAX);
      const spots = placesInside(shape, chosen.length);
      if (spots.length < chosen.length) {
        say('There is no room inside this shape for that many places.', true);
        return;
      }
      const put = chosen.map((child, i) => ({
        entry_id: child.id,
        geometry: toGeometry({ kind: 'point', at: spots[i] as Pt }) as unknown as Record<
          string,
          unknown
        >,
        role: 'site' as string | null,
        style: null,
        z: 0,
      }));
      await batchPlacements(context.tenant, context.mapId, { put });
      const step: Change[] = put.map((item) => ({
        entry: item.entry_id,
        before: null,
        after: { geometry: item.geometry, role: item.role, style: null, z: 0 },
      }));
      history.record(step, `Placed ${chosen.length} places inside ${row.name}`);
      await reload();
      say(
        children.length > chosen.length
          ? `Placed ${chosen.length} places inside ${row.name}; ${children.length - chosen.length} more remain.`
          : `Placed ${chosen.length} places inside ${row.name}.`,
      );
      render();
      refresh();
    });
  }

  // --- the tools ------------------------------------------------------------------------------

  const finishDraft = () => {
    if (toolName === 'height-line' && draft.length >= 2) {
      const decl = toolDecl();
      const value = optionValues.get(decl, HEIGHT);
      const unit = unitOf(optionValues.get(decl, UNIT));
      if (value === null || unit === null) {
        // Neither is ever assumed: the draft is kept until both are given.
        say('A height line needs a height and a unit. Give both in the Options tab.', true);
        return;
      }
      rememberHeight(context.mapId, { value, unit });
      const line = toGeometry({ kind: 'line', pts: draft, value, unit });
      // An entry already drawn as height lines takes this one as one more of them (ADR 0473).
      const was = rowOf(target?.id ?? null)?.geometry as unknown as Geometry | undefined;
      if (was && isHeightLines(was)) {
        if (was.parts.length >= MAX_PARTS) {
          say(`A drawing has at most ${MAX_PARTS} parts: this one is full.`, true);
          return;
        }
        void finish(withParts(was, line));
      } else void finish(line);
    } else if (toolName === 'line' && draft.length >= 2) {
      void finish(toGeometry({ kind: 'line', pts: draft }));
    } else if (toolName === 'spline' && draft.length >= 2) {
      void finish(
        toGeometry({
          kind: 'spline',
          pts: draft,
          tension: optionValues.get(toolDecl(), TENSION) ?? 0.5,
        }),
      );
    } else if (toolName === 'area' && draft.length >= 3) {
      void finish(toGeometry({ kind: 'area', pts: draft }));
    } else {
      say(
        toolName === 'area'
          ? 'An area needs three points.'
          : toolName === 'spline'
            ? 'A spline needs two points.'
            : 'A line needs two points.',
        true,
      );
    }
  };

  const finishCells = () => {
    const grid = gridNow();
    if (!grid) return;
    if (cells.length === 0) say('Choose at least one cell.', true);
    else {
      // Drawing an entry's cells again keeps the value a cell already had.
      const was = rowOf(target?.id ?? null)?.geometry as unknown as Geometry | undefined;
      const geometry = cellsGeometry(grid, context.extent, cells, was);
      // The cells are written as outlines (ADR 0481); what is over a drawing's limits is said.
      const fit = fits(geometry, CELL_HINTS);
      if (!fit.ok) say(fit.why, true);
      else void finish(geometry);
    }
  };

  const selectTool: Tool = {
    down(event: ToolEvent) {
      const row = rowOf(selectedId);
      if (!row) return false;
      const geometry = row.geometry as unknown as Geometry;
      // A press on another part of the selected placement chooses that part.
      if (!event.handle && event.hit === row.id && hasParts(geometry) && !isCellsRow(row)) {
        const view = context.view();
        const reach =
          PART_REACH *
          unitsPerPixel(context.extent, view.svg.getBoundingClientRect(), view.getView().zoom);
        const under = partAt(geometry, [event.point[0], event.point[1]], reach);
        if (under && under.part !== selectedPart?.part) {
          selectedPart = under;
          render();
        }
      }
      const base = focusOf(row).shape;
      if (!base) return false;
      if (event.handle || event.hit === row.id) {
        dragging = { handle: event.handle, base, start: event.point, by: [0, 0] };
        working = base;
        return true;
      }
      return false;
    },
    drag(event: ToolEvent) {
      if (!dragging) return;
      const { handle, base, start } = dragging;
      dragging.by = [event.point[0] - start[0], event.point[1] - start[1]];
      working = handle
        ? moveHandle(base, handle, snapHandle(handle, event.point))
        : translate(base, event.point[0] - start[0], event.point[1] - start[1]);
      refresh();
    },
    up() {
      const drag = dragging;
      const shape = working;
      dragging = null;
      const row = rowOf(selectedId);
      if (!drag || !shape || !row || JSON.stringify(shape) === JSON.stringify(drag.base)) {
        working = null;
        refresh();
        return;
      }
      const focus = focusOf(row);
      // The body of an area dragged moves the area with its holes; a handle moves one point.
      const geometry =
        !drag.handle && focus.part && focus.part.ring === 0
          ? movedPart(row.geometry as unknown as Geometry, focus.part.part, drag.by[0], drag.by[1])
          : focus.write(shape);
      void saveRow(row, { geometry });
    },
  };

  /** The stroke ends: its line is simplified as the Tolerance option says, and written. */
  const finishStroke = () => {
    const samples = stroke;
    stroke = null;
    refresh();
    if (!samples) return;
    const view = context.view();
    const box = view.svg.getBoundingClientRect();
    const tolerance =
      (optionValues.get(toolDecl(), TOLERANCE) ?? 2) *
      unitsPerPixel(context.extent, box, view.getView().zoom);
    const line = strokeLine(samples, tolerance);
    if (line.pts.length < 2) {
      say('The stroke went nowhere, so nothing was drawn. Press, drag and let go.', true);
      return;
    }
    void finish(toGeometry({ kind: 'line', pts: line.pts })).then(() => {
      if (line.coarser && !status.classList.contains('error-text')) {
        say(`${status.textContent} The line was made coarser to fit ${line.pts.length} points.`);
      }
    });
  };

  const drawTool: Tool = {
    cursor: 'crosshair',
    down(event: ToolEvent) {
      if (brushing()) {
        const p: Pt = [event.point[0], event.point[1]];
        brushStroke = { pts: inSheet(p) ? [p] : [], lower: event.shift };
        brushAt = p;
        refresh();
        return true;
      }
      if (toolName !== 'freehand') return false;
      if (!target) {
        say('Choose what you are drawing first.', true);
        return true;
      }
      const p: Pt = [event.point[0], event.point[1]];
      stroke = inSheet(p) ? [p] : [];
      return true;
    },
    drag(event: ToolEvent) {
      if (brushStroke) {
        const p: Pt = [event.point[0], event.point[1]];
        brushAt = p;
        if (inSheet(p)) brushStroke.pts.push(p);
        refresh();
        return;
      }
      if (!stroke) return;
      const p: Pt = [event.point[0], event.point[1]];
      // A stroke that leaves the sheet goes on where it comes back.
      if (inSheet(p)) stroke.push(p);
      refresh();
    },
    up() {
      if (brushStroke) {
        const done = brushStroke;
        brushStroke = null;
        if (done.pts.length > 0) brushStrokeAt(done.pts, done.lower);
        else refresh();
        return;
      }
      if (toolName === 'freehand') finishStroke();
    },
    click(event: ToolEvent) {
      if (!target) {
        say('Choose what you are drawing first.', true);
        return true;
      }
      if (toolName === 'freehand') {
        say('Freehand is drawn by dragging. The Line tool takes points one by one.', true);
        return true;
      }
      // A generator takes no point: its region was chosen before it, and it draws on Apply.
      if (generating()) return true;
      if (toolName === 'cells') {
        const grid = gridNow();
        const cell = grid ? cellOfPoint(grid, context.extent, event.point) : null;
        if (!cell) return true;
        const next = toggleCell(cells, cell);
        if (
          next.length === cells.length &&
          !cells.some((c) => c[0] === cell[0] && c[1] === cell[1])
        ) {
          say(`The Cells tool takes at most ${MAX_CELLS_PER_PLACEMENT} cells at once.`, true);
        }
        cells = next;
        refresh();
        render();
        return true;
      }
      const raw: Pt = [round2(event.point[0]), round2(event.point[1])];
      if (!inSheet(raw)) return true;
      const p =
        toolName === 'pin' || (toolName === 'circle' && draft.length === 0)
          ? snapped('centre', raw)
          : toolName === 'circle'
            ? raw
            : snapped('corner', raw);
      if (toolName === 'pin') {
        void finish(toGeometry({ kind: 'point', at: p }));
      } else if (toolName === 'circle') {
        const centre = draft[0];
        if (!centre) draft = [p];
        else if (!same(centre, p)) {
          void finish(
            toGeometry({
              kind: 'circle',
              at: centre,
              r: Math.hypot(p[0] - centre[0], p[1] - centre[1]),
            }),
          );
        }
      } else {
        const last = draft[draft.length - 1];
        if (toolName === 'spline' && draft.length >= SPLINE_MAX_POINTS) {
          say(`A spline has at most ${SPLINE_MAX_POINTS} points. Press Enter to finish it.`, true);
          return true;
        }
        if (!last || !same(last, p)) draft = [...draft, p];
        // Longitude does not wrap: a segment over half a turn goes the long way round (ADR 0357).
        if (context.sphere && last && Math.abs(p[0] - last[0]) > 180) {
          say(
            'That segment goes more than half way round the world. A line or an area over the antimeridian is two parts.',
          );
        }
      }
      refresh();
      render();
      return true;
    },
    dblclick() {
      if (pathTool()) finishDraft();
      return true;
    },
    move(event: ToolEvent) {
      if (brushing()) {
        brushAt = [event.point[0], event.point[1]];
        refresh();
        return;
      }
      if (draft.length === 0) return;
      rubber = event.point;
      refresh();
    },
    key(event: KeyboardEvent) {
      if (brushStroke && event.key === 'Escape') {
        brushStroke = null;
        refresh();
        say('The stroke was dropped.');
        return true;
      }
      if (toolName === 'freehand' && stroke && event.key === 'Escape') {
        stroke = null;
        refresh();
        say('The stroke was dropped.');
        return true;
      }
      if (toolName === 'cells') {
        if (event.key === 'Enter') {
          finishCells();
          return true;
        }
        if (event.key === 'Backspace' && cells.length > 0) {
          cells = cells.slice(0, -1);
          refresh();
          render();
          return true;
        }
        if (event.key === 'Escape') {
          if (cells.length > 0) cells = [];
          else setTool('select');
          refresh();
          render();
          return true;
        }
        return false;
      }
      if (event.key === 'Enter' && pathTool()) {
        finishDraft();
        return true;
      }
      if (event.key === 'Backspace' && draft.length > 0) {
        draft = draft.slice(0, -1);
        refresh();
        render();
        return true;
      }
      if (event.key === 'Escape') {
        if (draft.length > 0) draft = [];
        else setTool('select');
        rubber = null;
        refresh();
        render();
        return true;
      }
      return false;
    },
  };

  const tool = (): Tool | null => (!editing ? null : toolName === 'select' ? selectTool : drawTool);

  function setTool(next: ToolName) {
    leaveGenerator();
    // A generator works in the placement that is selected when it is chosen (ADR 0475).
    regionId = toolById(next)?.generator ? selectedId : null;
    toolName = next;
    if (next === 'height-brush') {
      // The brush is for the entry that is selected when it is height lines (ADR 0480).
      const chosen = rowOf(selectedId);
      if (chosen && isHeightLines(chosen.geometry as unknown as Geometry)) {
        target = { id: chosen.id, name: chosen.name };
      }
    }
    draft = [];
    cells = [];
    rubber = null;
    stroke = null;
    working = null;
    dragging = null;
    if (next === 'select') target = null;
    context.view().setTool(tool());
    renderToolbar();
    render();
    refresh();
    if (fillsCells()) void readExampleMaps();
  }

  // --- a generator: preview, compare, apply, discard (ADR 0475) --------------------------------

  /**
   * The Maps of the library a fill of cells may learn from (ADR 0479): those with a grid of the
   * kind this Map has, read once. One that cannot be read is left out.
   */
  function readExampleMaps(): Promise<void> {
    exampleMapsRead ??= (async () => {
      const grid = gridNow();
      if (!grid) return;
      const found: ExampleMap[] = [];
      for (let page = 1; ; page += 1) {
        const list = await unwrap(
          await client.GET('/tenants/{tenant_id}/maps', {
            params: { path: { tenant_id: context.tenant }, query: { page, size: 100 } },
          }),
        );
        const others = list.items.filter((item) => item.id !== context.mapId);
        const kinds = await Promise.all(
          others.map(async (item) => {
            try {
              return gridOfMap(await readHeader(item.id));
            } catch {
              return null;
            }
          }),
        );
        others.forEach((item, i) => {
          const other = kinds[i];
          if (other && sameGridKind(grid, other.grid)) found.push({ id: item.id, name: item.name });
        });
        if (page * 100 >= list.total || list.items.length === 0) break;
      }
      exampleMaps = found;
      if (fillsCells()) {
        render();
        refresh();
      }
    })().catch(() => {
      exampleMaps = [];
      exampleProblem = 'The Maps of the library could not be read. Try again.';
      exampleMapsRead = null;
    });
    return exampleMapsRead;
  }

  async function readHeader(id: string) {
    return unwrap(
      await client.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { tenant_id: context.tenant, map_id: id } },
        cache: 'no-cache',
      }),
    );
  }

  /** A Map's grid and sheet from its header; null for a Map without a grid, or a sphere. */
  function gridOfMap(header: { system: unknown; view?: unknown }) {
    const system = header.system as { kind: string; extent?: [number, number, number, number] };
    if (system.kind === 'sphere' || !system.extent) return null;
    const grid = gridOf({
      system: header.system,
      placements: [],
      overlay: (header.view as { grid?: GridSpec } | null)?.grid ?? null,
    } as unknown as MapModel);
    return grid ? { grid, extent: system.extent } : null;
  }

  /** Reads the Map chosen as the example, and draws the preview again once it is read. */
  async function readExample(id: string) {
    example = null;
    exampleProblem = null;
    if (id === '') return;
    try {
      const header = await readHeader(id);
      const kind = gridOfMap(header);
      const grid = gridNow();
      if (!kind || !grid || !sameGridKind(grid, kind.grid)) {
        exampleProblem = `${header.name} has no grid of the kind this Map has. Choose another example.`;
      } else {
        const { rows } = await readPlacements(context.tenant, id);
        if (optionValues.get(toolDecl(), EXAMPLE) !== id) return;
        example = { id, name: header.name, grid: kind.grid, extent: kind.extent, rows };
      }
    } catch {
      exampleProblem = 'The example Map could not be read. Choose it again.';
    }
    if (fillsCells()) {
      render();
      refresh();
    }
  }

  /** The view is whole again and nothing of a preview is kept. */
  function leaveGenerator() {
    made = null;
    brush = null;
    brushStroke = null;
    brushAt = null;
    syncGenerator = () => {};
    if (compare) {
      compare = false;
      context.view().setOverlayDivide(null);
    }
  }

  function setCompare(on: boolean) {
    compare = on;
    context.view().setOverlayDivide(on ? divide : null);
    render();
  }

  /** What the preview is, in words: how much in where, or why it cannot be applied. */
  function generatedWords(): string {
    const now = generated();
    if (!now) return '';
    if (!now.fit.ok) return now.fit.why;
    return brushing()
      ? `${now.count} on ${target?.name ?? 'the entry'}.`
      : `${now.count} in ${now.region.words}.`;
  }

  function discardGenerator() {
    setTool('select');
    say('Nothing was drawn.');
  }

  /** Writes what is previewed as one placement and one history step; answers what happened. */
  async function applyGenerator(): Promise<string> {
    if (fillsCells()) return applyCells();
    if (brushing()) return applyBrush();
    const def = generator();
    const now = generated();
    if (!def || !now) return '';
    if (!now.fit.ok || !now.geometry) {
      say(now.fit.ok ? 'There is nothing to draw.' : now.fit.why, true);
      return status.textContent ?? '';
    }
    if (!target) {
      say('Choose what you are drawing first.', true);
      return status.textContent ?? '';
    }
    const step = stepName(def.what, seedNow(), now.count, now.region);
    await finish(now.geometry, { role: optionValues.get(toolDecl(), ROLE) || null, step });
    return status.textContent ?? '';
  }

  /**
   * Writes a fill of cells (ADR 0479): one placement of cells for each tile entry that changes, in
   * one batch and one history step. An entry left with no cell is taken off the Map.
   */
  async function applyCells(): Promise<string> {
    const now = generated();
    const plan = now?.cells;
    const grid = gridNow();
    if (!now || !plan || !grid) return '';
    if (!plan.ok) {
      say(plan.why, true);
      return plan.why;
    }
    const put: NonNullable<Parameters<typeof batchPlacements>[2]['put']> = [];
    const remove: string[] = [];
    const step: Step = [];
    const chosen = optionValues.get(toolDecl(), EXAMPLE);
    for (const tile of plan.tiles) {
      const row = rowOf(tile.id);
      if (!tile.changed) continue;
      if (!row) {
        // An entry of another example, new to this Map: placed with the role, line and drawing
        // order it has there (ADR 0479).
        const there = chosen === '' ? undefined : example?.rows.find((one) => one.id === tile.id);
        if (!there || tile.cells.length === 0) continue;
        const how = rowState(there);
        const geometry = cellsGeometry(grid, context.extent, tile.cells);
        put.push({ entry_id: tile.id, geometry, role: how.role, style: how.style, z: how.z });
        step.push({ entry: tile.id, before: null, after: { ...how, geometry } });
        continue;
      }
      const before = rowState(row);
      if (tile.cells.length === 0) {
        remove.push(row.id);
        step.push({ entry: row.id, before, after: null });
        continue;
      }
      // A cell that carried a value keeps it (ADR 0337).
      const geometry = cellsGeometry(
        grid,
        context.extent,
        tile.cells,
        row.geometry as unknown as Geometry,
      );
      put.push({ entry_id: row.id, geometry, role: before.role, style: before.style, z: before.z });
      step.push({ entry: row.id, before, after: { ...before, geometry } });
    }
    if (step.length === 0) {
      say('This fill changes nothing: every cell would be what it is. Roll another seed.', true);
      return status.textContent ?? '';
    }
    const name = `Filled by wave function collapse, seed ${seedNow()}: ${plan.count} in ${now.region.words}`;
    await guarded(async () => {
      await batchPlacements(context.tenant, context.mapId, { put, remove });
      await reload();
      history.record(step, name);
      setTool('select');
      say(`${plan.count} drawn in ${now.region.words}.`);
    });
    return status.textContent ?? '';
  }

  /** What the example of a fill of cells is called: this Map, or the Map chosen. */
  function exampleName(): string {
    const chosen = optionValues.get(toolDecl(), EXAMPLE);
    if (chosen === '') return 'this Map';
    return (
      exampleMaps?.find((map) => map.id === chosen)?.name ?? example?.name ?? 'the example Map'
    );
  }

  /**
   * Writes the brushed lines as the entry's one placement and one history step (ADR 0480): a
   * placement already here keeps its role, line and drawing order; a new one takes the Role option.
   */
  async function applyBrush(): Promise<string> {
    const now = generated();
    const chosen = target;
    if (!now || !chosen) return '';
    if (!now.fit.ok || !now.geometry) {
      say(now.fit.ok ? 'There is nothing to draw.' : now.fit.why, true);
      return status.textContent ?? '';
    }
    const geometry = now.geometry;
    const count = now.count;
    await guarded(async () => {
      let id = chosen.id;
      if (!id && chosen.create) {
        const created = await makeLocation(context.tenant, chosen.name, chosen.create.isPublic);
        id = created.id;
        // The Location exists now: a retry must not make another.
        target = { id, name: created.name };
      }
      if (!id) return;
      const row = rowOf(id);
      const before = row ? rowState(row) : null;
      const saved = await putPlacement(
        context.tenant,
        context.mapId,
        id,
        before
          ? { ...before, geometry }
          : {
              geometry,
              role: optionValues.get(toolDecl(), BRUSH_ROLE) || null,
              style: null,
              z: 0,
            },
      );
      history.record(
        [{ entry: id, before, after: rowState(saved) }],
        `Height brush on ${saved.name}: ${count}`,
      );
      context.setRows(upsert(saved));
      setTool('select');
      context.select(id);
      say(`${saved.name}: ${count}.`);
    });
    return status.textContent ?? '';
  }

  /** The preview's line, Compare with its divider, and Apply and Discard. */
  function generatorControls(): HTMLElement {
    const box = el('div', '', 'stack-tight map-generator');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Preview');
    const line = el('p', '', 'status-text map-generator-result');
    line.setAttribute('role', 'status');
    const split = field('Compare with the Map as it is', '', 'checkbox');
    split.input.checked = compare;
    split.input.addEventListener('change', () => setCompare(split.input.checked));
    box.append(line);
    // A fill of cells names its tiles, each with its tone and what it would get: the tone is
    // never the only way to tell them apart (ADR 0479).
    const tiles = el('ul', '', 'list map-generator-tiles');
    tiles.setAttribute('aria-label', 'Tiles, the lightest tone first');
    if (fillsCells()) {
      box.append(
        el(
          'p',
          `It learns from the cells already drawn on ${exampleName()}: which entry lies beside which. Each entry gets the cells the fill gives it; nothing is drawn until you apply it.`,
          'status-text',
        ),
        tiles,
      );
    }
    box.append(split.label);
    if (compare) {
      const slider = field('Divider', String(Math.round(divide * 100)), 'range');
      slider.input.min = '0';
      slider.input.max = '100';
      slider.input.step = '5';
      slider.input.addEventListener('input', () => {
        divide = Number(slider.input.value) / 100;
        context.view().setOverlayDivide(divide);
      });
      box.append(slider.label);
    }
    const apply = button('Apply', async () => {
      await applyGenerator();
    });
    const discard = button('Discard', async () => discardGenerator(), { variant: 'secondary' });
    const actions = el('div', '', 'row-tight');
    actions.append(apply, discard);
    box.append(actions);
    syncGenerator = () => {
      const now = generated();
      line.textContent = generatedWords();
      line.classList.toggle('error-text', now ? !now.fit.ok : false);
      apply.disabled = !now?.fit.ok || (!fillsCells() && !target);
      tiles.replaceChildren(
        ...(now?.cells?.tiles ?? []).map((tile) => {
          const item = el('li', '', 'row-tight');
          const swatch = el('span', '', 'map-tone');
          swatch.dataset.tone = String(tile.tone);
          swatch.setAttribute('aria-hidden', 'true');
          item.append(
            swatch,
            el(
              'span',
              `${tile.name}: ${tile.gained.length} ${tile.gained.length === 1 ? 'cell' : 'cells'}`,
            ),
          );
          return item;
        }),
      );
    };
    syncGenerator();
    return box;
  }

  // --- the toolbar ----------------------------------------------------------------------------

  const here = () => ({ grid: Boolean(gridNow()), sphere: context.sphere === true });

  /** What saying a tool that cannot be used yet looks like: it names the tool and why. */
  function unavailable(decl: ToolDecl): string {
    return decl.state === 'planned'
      ? `${decl.name} is planned. ${decl.reason ?? ''}`.trim()
      : `${decl.name} is not available on this Map.`;
  }

  // The Shortcuts dialog (MP6): every tool's key, each to be changed or put back. The keys are the
  // person's alone, kept in this browser, and single keys can still be turned off for good.
  // The dialog lives on the page, not in the toolbar, which is drawn again when a key changes.
  const shortcutsDialog = (() => {
    const dialog = el('dialog', '', 'card map-shortcuts');
    dialog.setAttribute('aria-labelledby', 'map-shortcuts-title');
    const title = groupTitle('h2', 'Shortcuts');
    title.id = 'map-shortcuts-title';
    const note = el(
      'p',
      'One key per tool, while the drawing has the focus. Choose Change, then press the key you want. Your keys are yours alone, kept in this browser. / goes to the command line.',
      'status-text',
    );
    const result = statusLine();
    const tell = (text: string, failed = false) => {
      result.textContent = text;
      result.dataset.failed = String(failed);
    };
    const list = el('ul', '', 'list map-shortcut-list');
    let waiting: ToolDecl | null = null;
    const draw = () => {
      list.replaceChildren(
        ...DECLARED.map((decl) => {
          const item = el('li', '', 'row-tight');
          const change = el(
            'button',
            waiting === decl ? 'Press a key' : 'Change',
            'btn btn-secondary',
          );
          change.type = 'button';
          change.setAttribute('aria-label', `Change the key of ${decl.name}`);
          change.addEventListener('click', () => {
            waiting = decl;
            tell(`Press the new key for ${decl.name}, or Escape to cancel.`);
            draw();
            (list.querySelectorAll('button')[DECLARED.indexOf(decl)] as HTMLElement)?.focus();
          });
          item.append(
            el('span', decl.name, 'grow'),
            el('kbd', keys.keyOf(decl).toUpperCase(), 'chip'),
            ...(decl.state === 'planned' ? [el('span', 'planned', 'chip')] : []),
            change,
          );
          return item;
        }),
      );
    };
    dialog.addEventListener('keydown', (event) => {
      if (!waiting) return;
      if (event.key === 'Shift' || event.key === 'Control' || event.key === 'Alt') return;
      event.preventDefault();
      event.stopPropagation();
      const decl = waiting;
      waiting = null;
      if (event.key === 'Escape') tell('Nothing changed.');
      else {
        const refused = keys.set(decl, event.key);
        tell(refused ?? `${decl.name} is now ${keys.keyOf(decl).toUpperCase()}.`, refused !== null);
      }
      draw();
      renderToolbar();
    });
    const reset = el('button', 'Put every key back', 'btn btn-secondary');
    reset.type = 'button';
    reset.addEventListener('click', () => {
      keys.reset();
      tell('Every key is back to its own.');
      draw();
      renderToolbar();
    });
    const close = el('button', 'Close', 'btn btn-primary');
    close.type = 'button';
    close.addEventListener('click', () => dialog.close());
    dialog.append(title, note, result, list, el('div', '', 'row-tight'));
    (dialog.lastElementChild as HTMLElement).append(reset, close);
    document.body.append(dialog);
    return {
      dialog,
      show() {
        waiting = null;
        tell('');
        draw();
        dialog.showModal();
      },
    };
  })();

  function shortcuts(): HTMLElement {
    const open = el('button', 'Shortcuts', 'btn btn-secondary');
    open.type = 'button';
    open.addEventListener('click', () => shortcutsDialog.show());
    return open;
  }

  /** Every tool, found by name, group or key; a planned one is listed with its reason and does nothing. */
  function allTools(): HTMLElement {
    const wrap = el('div', '', 'map-all-tools-wrap');
    const open = el('button', 'All tools', 'btn btn-secondary');
    open.type = 'button';
    open.setAttribute('aria-expanded', 'false');
    const panel = el('div', '', 'stack-tight map-all-tools');
    panel.hidden = true;
    const search = field('Find a tool');
    search.input.type = 'search';
    const list = el('ul', '', 'list map-all-tools-list');
    const draw = () => {
      list.replaceChildren(
        ...searchTools(search.input.value).map((decl) => {
          const item = el('li', '', 'row-tight');
          const node = el('button', decl.name, 'btn btn-secondary');
          node.type = 'button';
          const ready = usable(decl, here());
          node.setAttribute('aria-disabled', String(!ready));
          node.addEventListener('click', () => {
            if (!ready) {
              say(unavailable(decl));
              return;
            }
            panel.hidden = true;
            open.setAttribute('aria-expanded', 'false');
            setTool(decl.id as ToolName);
          });
          item.append(
            node,
            el(
              'span',
              `${GROUP_NAMES[decl.group]} · ${keys.keyOf(decl).toUpperCase()}`,
              'status-text',
            ),
          );
          if (decl.state === 'planned') item.append(el('span', 'planned', 'chip'));
          return item;
        }),
      );
    };
    search.input.addEventListener('input', draw);
    draw();
    open.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      open.setAttribute('aria-expanded', String(!panel.hidden));
      if (!panel.hidden) search.input.focus();
    });
    panel.append(search.label, list);
    wrap.append(open, panel);
    return wrap;
  }

  // One key a tool, while the drawing has the focus. The page's own single keys (G then a letter) do not
  // see these: the editor takes the key first, and a person who has turned single keys off keeps them off.
  const keys = createKeyMap(
    (() => {
      try {
        return window.localStorage;
      } catch {
        return null;
      }
    })(),
  );
  const singleKeysOn = () => {
    try {
      return window.localStorage.getItem('lorenzo:single-keys') !== 'off';
    } catch {
      return true;
    }
  };
  const onToolKey = (event: KeyboardEvent) => {
    if (!editing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (event.key.length !== 1 || !singleKeysOn()) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
    const active = document.activeElement;
    if (active && active !== document.body && !active.closest('.map-workspace')) return;
    if (event.key === '/') {
      event.preventDefault();
      event.stopImmediatePropagation();
      commandInput.focus();
      return;
    }
    const decl = keys.toolFor(event.key);
    if (!decl) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!usable(decl, here())) {
      say(unavailable(decl));
      return;
    }
    setTool(decl.id as ToolName);
  };
  document.addEventListener('keydown', onToolKey, true);

  function renderToolbar() {
    toolbar.replaceChildren();
    renderHistory();
    commandLine.hidden = !editing;
    const toggle = el('button', editing ? 'Stop editing' : 'Edit this map', 'btn btn-secondary');
    toggle.type = 'button';
    toggle.setAttribute('aria-pressed', String(editing));
    toggle.addEventListener('click', () => {
      editing = !editing;
      if (!editing) {
        toolName = 'select';
        draft = [];
        target = null;
        working = null;
      }
      context.view().setTool(tool());
      renderToolbar();
      render();
      refresh();
    });
    toolbar.append(toggle);
    if (!editing) return;
    const tools = el('div', '', 'row-tight map-tools');
    tools.setAttribute('role', 'group');
    tools.setAttribute('aria-label', 'Tool');
    // The tools of the registry (MP6), in their groups; the ones that are planned are in All tools.
    // Every group of the registry; one with no tool this Map can use yet is not drawn.
    for (const group of GROUPS) {
      const cluster = el('div', '', 'row-tight map-tool-group');
      cluster.setAttribute('role', 'group');
      cluster.setAttribute('aria-label', GROUP_NAMES[group]);
      for (const decl of toolsOf(group)) {
        if (!usable(decl, here())) continue;
        const node = el('button', decl.name, 'btn btn-secondary');
        node.type = 'button';
        node.title = `${decl.name} (${keys.keyOf(decl).toUpperCase()})`;
        node.setAttribute('aria-keyshortcuts', keys.keyOf(decl).toUpperCase());
        node.setAttribute('aria-pressed', String(toolName === decl.id));
        node.addEventListener('click', () => setTool(decl.id as ToolName));
        cluster.append(node);
      }
      if (cluster.childElementCount) tools.append(cluster);
    }
    tools.append(allTools(), shortcuts());
    const undoButton = el('button', 'Undo', 'btn btn-secondary');
    undoButton.type = 'button';
    undoButton.disabled = busy || !history.canUndo();
    undoButton.addEventListener('click', () => void undo());
    const redoButton = el('button', 'Redo', 'btn btn-secondary');
    redoButton.type = 'button';
    redoButton.disabled = busy || !history.canRedo();
    redoButton.addEventListener('click', () => void redo());
    toolbar.append(tools);
    toolbar.append(undoButton, redoButton, status);
  }

  // --- the panel ------------------------------------------------------------------------------

  function chooser(): HTMLElement {
    const box = el('div', '', 'stack-tight');
    const label = TOOLS.find(([name]) => name === toolName)?.[1] ?? '';
    box.append(groupTitle('h2', `Draw: ${label.toLowerCase()}`));
    if (target) {
      const placed = target.id ? rowOf(target.id) : undefined;
      box.append(
        el('p', target.create ? `A new Location, ${target.name}` : target.name, 'status-text'),
      );
      if (placed) {
        box.append(
          el(
            'p',
            brushing()
              ? 'Its height lines are what the brush changes; a line no stroke reaches stays as it is.'
              : toolName === 'height-line' && isHeightLines(placed.geometry as unknown as Geometry)
                ? 'It is already on this Map as height lines; this line is added to them.'
                : 'It is already on this Map; drawing it again replaces its drawing.',
            'status-text',
          ),
        );
      }
      box.append(
        el(
          'p',
          toolName === 'pin'
            ? 'Click the map to place it.'
            : brushing()
              ? 'Drag on the map to raise the land, with Shift held to lower it, or type RAISE x,y or LOWER x,y. The preview shows the lines that would be drawn, and dashed those that would go; nothing is drawn until you apply it.'
              : generating()
                ? 'The preview on the Map is what Apply will draw for it; nothing is drawn until then.'
                : toolName === 'height-line'
                  ? 'Give the height and its unit above, then click each point. Press Enter or double-click to finish, Backspace to take back a point, Escape to start again.'
                  : toolName === 'freehand'
                    ? 'Press and drag on the map, and let go to finish. Escape while dragging drops the stroke. The Line tool draws the same thing point by point, from the keyboard.'
                    : toolName === 'circle'
                      ? 'Click the centre, then the edge.'
                      : toolName === 'cells'
                        ? 'Click a cell to add it and click it again to take it away. Press Enter to finish, Backspace to take back a cell, Escape to start again.'
                        : 'Click each point. Press Enter or double-click to finish, Backspace to take back a point, Escape to start again.',
          'status-text',
        ),
      );
      box.append(
        button('Choose another', () => {
          target = null;
          draft = [];
          cells = [];
          refresh();
          render();
        }),
      );
      return box;
    }
    const search = field('Find an entry by name');
    search.input.type = 'search';
    const results = el('ul', '', 'list');
    let sequence = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    search.input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const mine = ++sequence;
        const query = search.input.value.trim();
        if (!query) {
          results.replaceChildren();
          return;
        }
        void findEntries(context.tenant, query)
          .then((found: EntryChoice[]) => {
            if (mine !== sequence) return;
            results.replaceChildren(
              ...(found.length
                ? found.map((entry) => {
                    const item = el('li');
                    const pick = el('button', entry.name, 'place-toggle map-place');
                    pick.type = 'button';
                    pick.addEventListener('click', () => {
                      target = { id: entry.id, name: entry.name };
                      // A region already of whole cells opens with its cells chosen.
                      const grid = gridNow();
                      const placed = rowOf(entry.id);
                      if (toolName === 'cells' && grid && placed) {
                        cells =
                          cellsOf(placed.geometry as unknown as Geometry, grid, context.extent) ??
                          [];
                      }
                      refresh();
                      render();
                    });
                    if (entry.kinds.length) {
                      pick.append(el('span', entry.kinds.join(', ').replaceAll('_', ' '), 'chip'));
                    }
                    item.append(pick);
                    return item;
                  })
                : [el('li', 'No entry has that name.', 'status-text')]),
            );
          })
          .catch((error) => say(asText(error), true));
      }, 250);
    });
    box.append(search.label, results);
    const fresh = el('form', '', 'stack-tight');
    const name = field('Or make a new Location, named');
    name.input.required = true;
    const open = field('Open it to the library', '', 'checkbox');
    open.input.checked = context.mapIsPublic;
    const use = el('button', 'Draw a new Location', 'btn btn-secondary');
    use.type = 'submit';
    fresh.append(name.label, open.label, use);
    fresh.addEventListener('submit', (event) => {
      event.preventDefault();
      const text = name.input.value.trim();
      if (!text) return;
      target = { name: text, create: { isPublic: open.input.checked } };
      render();
    });
    box.append(fresh);
    return box;
  }

  function pointFields(
    row: Row,
    shape: Editable,
    write: (shape: Editable) => Geometry = toGeometry,
  ): HTMLElement {
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h3', 'Points'));
    const inputs: HTMLInputElement[][] = [];
    const commit = () => {
      const number = (input: HTMLInputElement | undefined) => Number(input?.value ?? Number.NaN);
      const values = inputs.map((pair) => pair.map(number));
      if (values.some((pair) => pair.some((n) => !Number.isFinite(n)))) {
        say('Every point needs two numbers.', true);
        return;
      }
      const at = (i: number): Pt => [values[i]?.[0] ?? 0, values[i]?.[1] ?? 0];
      let next: Editable;
      // The shape itself is spread, so a value and its unit stay with it (ADR 0337).
      if (shape.kind === 'point') next = { ...shape, at: at(0) };
      else if (shape.kind === 'circle')
        next = { ...shape, at: at(0), r: values[1]?.[0] ?? shape.r };
      else next = { ...shape, pts: values.map((_, i) => at(i)) };
      void saveRow(row, { geometry: write(next) });
    };
    // One point is one group of its own: a legend and two short fields, so a screen reader says
    // "Point 2, x" and the fields stay narrow beside their buttons.
    const pair = (label: string, x: number, y: number | null, index: number) => {
      const line = el('fieldset', '', 'map-point');
      line.append(el('legend', label, 'map-point-name'));
      const first = field(
        y === null ? 'Value' : context.sphere ? 'Longitude' : 'x',
        String(x),
        'number',
      );
      first.input.step = 'any';
      if (context.sphere && y !== null) {
        first.input.min = '-180';
        first.input.max = '180';
      }
      first.input.addEventListener('change', commit);
      const group: HTMLInputElement[] = [first.input];
      line.append(first.label);
      if (y !== null) {
        const second = field(context.sphere ? 'Latitude' : 'y', String(y), 'number');
        second.input.step = 'any';
        if (context.sphere) {
          second.input.min = '-90';
          second.input.max = '90';
        }
        second.input.addEventListener('change', commit);
        group.push(second.input);
        line.append(second.label);
      }
      inputs[index] = group;
      return line;
    };
    // A small button whose visible word is part of the longer name a screen reader says.
    const small = (word: string, name: string, action: () => Promise<void>) => {
      const node = button(word, action, { variant: 'secondary' });
      node.setAttribute('aria-label', name);
      node.classList.add('map-point-button');
      return node;
    };
    if (shape.kind === 'spline') {
      // A curve through its points (ADR 0471): how round it is can be changed after it is drawn.
      const tension = field(
        'Tension (0 the roundest, 1 straight)',
        String(shape.tension),
        'number',
      );
      tension.input.min = String(TENSION.least);
      tension.input.max = String(TENSION.most);
      tension.input.step = String(TENSION.step);
      tension.input.addEventListener('change', () => {
        const typed = numberFor(TENSION, Number(tension.input.value));
        if (tension.input.value.trim() === '' || typed === null) {
          say(`Tension is a number from ${TENSION.least} to ${TENSION.most}.`, true);
          return;
        }
        void saveRow(row, { geometry: write({ ...shape, tension: typed }) });
      });
      box.append(tension.label);
    }
    if (shape.kind === 'point') box.append(pair('Point', shape.at[0], shape.at[1], 0));
    else if (shape.kind === 'circle') {
      box.append(pair('Centre', shape.at[0], shape.at[1], 0), pair('Radius', shape.r, null, 1));
    } else {
      for (const [i, at] of shape.pts.entries()) {
        const line = pair(`Point ${i + 1}`, at[0], at[1], i);
        const after = insertVertex(shape, i);
        line.append(
          small('Add', `Add a point after point ${i + 1}`, () =>
            saveRow(row, { geometry: write(after) }),
          ),
        );
        const without = removeVertex(shape, i);
        if (without) {
          line.append(
            small('Remove', `Remove point ${i + 1}`, () =>
              saveRow(row, { geometry: write(without) }),
            ),
          );
        }
        box.append(line);
      }
    }
    return box;
  }

  /**
   * The height a line or a curve carries, and its unit (ADR 0473): both, or neither. Emptying both
   * takes the value away; one without the other is not written, as the API would refuse it.
   */
  function heightFields(
    row: Row,
    shape: Editable,
    write: (shape: Editable) => Geometry = toGeometry,
  ): HTMLElement | null {
    if (shape.kind !== 'line' && shape.kind !== 'spline') return null;
    const box = el('fieldset', '', 'map-point');
    box.append(el('legend', 'Height', 'map-point-name'));
    const value = field('Height', shape.value === undefined ? '' : String(shape.value), 'number');
    value.input.step = 'any';
    const unit = field('Unit', shape.unit ?? '');
    unit.input.maxLength = 32;
    unit.input.autocomplete = 'off';
    const commit = () => {
      const typedValue = value.input.value.trim();
      const typedUnit = unit.input.value.trim();
      if (typedValue === '' && typedUnit === '') {
        if (shape.value === undefined) return;
        void saveRow(row, {
          geometry: write({ ...shape, value: undefined, unit: undefined }),
        });
        return;
      }
      if (typedValue === '' || typedUnit === '') {
        say('A height and its unit go together: give the other too.');
        return;
      }
      const nextValue = heightOf(typedValue);
      const nextUnit = unitOf(typedUnit);
      if (nextValue === null || nextUnit === null) {
        say(
          nextValue === null ? 'The height is a number.' : 'The unit is 1 to 32 characters.',
          true,
        );
        return;
      }
      if (nextValue === shape.value && nextUnit === shape.unit) return;
      void saveRow(row, { geometry: write({ ...shape, value: nextValue, unit: nextUnit }) });
    };
    value.input.addEventListener('change', commit);
    unit.input.addEventListener('change', commit);
    box.append(value.label, unit.label);
    return box;
  }

  /**
   * The parts of a placement that has several, or holes (ADR 0474): each is chosen to be changed,
   * and can be removed, but for the last part, which is the drawing itself.
   */
  function partsList(row: Row, geometry: Geometry): HTMLElement {
    const box = el('div', '', 'stack-tight map-parts');
    box.append(groupTitle('h3', 'Parts'));
    const list = el('ul', '', 'list');
    for (const part of partNames(geometry)) {
      const item = el('li', '', 'row-tight');
      const chosen = selectedPart?.part === part.ref.part && selectedPart.ring === part.ref.ring;
      const pick = el('button', part.name, 'place-toggle map-place grow');
      pick.type = 'button';
      pick.setAttribute('aria-pressed', String(chosen));
      pick.addEventListener('click', () => {
        selectedPart = chosen ? null : part.ref;
        working = null;
        render();
        refresh();
      });
      item.append(pick);
      const without = withoutPart(geometry, part.ref);
      if (without) {
        const remove = button(
          'Remove',
          async () => {
            selectedPart = refAfterRemoval(selectedPart, part.ref);
            await saveRow(row, { geometry: without });
          },
          { variant: 'secondary' },
        );
        remove.setAttribute('aria-label', `Remove ${part.name}`);
        remove.classList.add('map-point-button');
        item.append(remove);
      }
      list.append(item);
    }
    box.append(list);
    if (row.kinds.includes('location') && geometry.parts.length >= 2) {
      box.append(splitControl(row, geometry));
    }
    return box;
  }

  /** Split into entries (ADR 0482): a base name, and the action. */
  function splitControl(row: Row, geometry: Geometry): HTMLElement {
    const box = el('div', '', 'stack-tight map-split');
    const base = field('Name the new places from', row.name);
    base.input.maxLength = 180;
    box.append(
      el(
        'p',
        `Each of the ${geometry.parts.length} parts becomes a place of its own inside ${row.name}, drawn here as that part.`,
        'status-text',
      ),
      base.label,
      button('Split into entries', () => splitInto(row, geometry, base.input.value), {
        variant: 'secondary',
      }),
    );
    return box;
  }

  /**
   * Makes a new Location of each part, inside the original, and places them on this Map in its
   * stead as one batch and one history step (ADR 0482).
   */
  async function splitInto(row: Row, geometry: Geometry, base: string) {
    const plan = splitPieces(geometry, base);
    if (!plan.ok) {
      say(plan.why, true);
      return;
    }
    const pieces = plan.pieces;
    await guarded(async () => {
      const isPublic = await isPublicLocation(context.tenant, row.id);
      const made: { id: string; name: string }[] = [];
      try {
        for (const piece of pieces) {
          made.push(await makeLocation(context.tenant, piece.name, isPublic, row.id));
        }
      } catch (error) {
        say(
          `${made.length} of ${pieces.length} new places were made, and stay in the library; nothing was placed. ${asText(error)}`,
          true,
        );
        return;
      }
      const how = rowState(row);
      const put = made.map((location, i) => ({
        entry_id: location.id,
        geometry: (pieces[i] as (typeof pieces)[number]).geometry as unknown as Record<
          string,
          unknown
        >,
        role: how.role,
        style: how.style,
        z: how.z,
      }));
      await batchPlacements(context.tenant, context.mapId, { put, remove: [row.id] });
      await reload();
      history.record(
        [
          { entry: row.id, before: how, after: null },
          ...made.map((location, i) => ({
            entry: location.id,
            before: null,
            after: { ...how, geometry: put[i]?.geometry ?? how.geometry },
          })),
        ],
        `Split ${row.name} into ${made.length} entries`,
      );
      selectedPart = null;
      context.select(null);
      say(`${row.name} is now ${made.length} places, each on the map and inside ${row.name}.`);
    });
  }

  function childrenControl(row: Row, shape: Editable): HTMLElement | null {
    if (!row.kinds.includes('location') || (shape.kind !== 'area' && shape.kind !== 'circle')) {
      return null;
    }
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h3', 'Places inside'));
    const line = el('p', 'Looking for what is inside…', 'status-text');
    box.append(line);
    void partsOf(context.tenant, row.id)
      .then((parts) => {
        const placed = new Set(context.rows().map((r) => r.id));
        const missing = parts.filter((part) => !placed.has(part.id));
        if (missing.length === 0) {
          line.textContent = parts.length
            ? 'Everything inside it is on this map.'
            : 'Nothing is inside it yet.';
          return;
        }
        line.textContent = `${missing.length} of the places inside ${row.name} are not on this map.`;
        line.after(
          button(
            `Place ${Math.min(missing.length, BATCH_MAX)} inside it`,
            () => placeChildren(row, shape, missing),
            { variant: 'secondary' },
          ),
        );
      })
      .catch((error) => {
        line.textContent = asText(error);
        line.classList.add('error-text');
      });
    return box;
  }

  function cellsPanel(row: Row, grid: GridSpec, current: Cell[]): HTMLElement {
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h3', 'Cells'));
    const write = (next: Cell[]) =>
      saveRow(row, {
        geometry: cellsGeometry(grid, context.extent, next, row.geometry as unknown as Geometry),
      });
    for (const cell of current) {
      const line = el('div', '', 'row-tight');
      line.append(el('span', cellWords(cell), 'grow'));
      if (current.length > 1) {
        const remove = button(
          'Remove',
          () => write(current.filter((c) => c[0] !== cell[0] || c[1] !== cell[1])),
          { variant: 'secondary' },
        );
        remove.setAttribute('aria-label', `Remove ${cellWords(cell)}`);
        line.append(remove);
      }
      box.append(line);
    }
    const form = el('div', '', 'row-tight');
    const col = field('Column', '', 'number');
    const rowField = field('Row', '', 'number');
    for (const f of [col, rowField]) {
      f.input.min = '1';
      f.input.step = '1';
    }
    form.append(
      col.label,
      rowField.label,
      button(
        'Add cell',
        async () => {
          const cell: Cell = [Number(col.input.value) - 1, Number(rowField.input.value) - 1];
          if (!Number.isInteger(cell[0]) || !Number.isInteger(cell[1]) || !inGridCell(grid, cell)) {
            throw new Error('That cell is not on this Map.');
          }
          if (current.some((c) => c[0] === cell[0] && c[1] === cell[1])) return;
          await write(toggleCell(current, cell));
        },
        { variant: 'secondary' },
      ),
    );
    box.append(form);
    return box;
  }

  const inGridCell = (grid: GridSpec, cell: Cell) => inGrid(grid, context.extent, cell);

  function editPanel(row: Row): HTMLElement {
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h2', `Change ${row.name}`));
    const role = select('Role', ROLE_OPTIONS, row.role ?? '');
    role.input.addEventListener(
      'change',
      () => void saveRow(row, { role: role.input.value || null }),
    );
    const stroke = select('Line', STROKES, (row.style as { stroke?: string } | null)?.stroke ?? '');
    const weight = select(
      'Weight',
      WEIGHTS,
      (row.style as { weight?: string } | null)?.weight ?? '',
    );
    const saveStyle = () => {
      const style: Record<string, string> = {};
      if (stroke.input.value) style.stroke = stroke.input.value;
      if (weight.input.value) style.weight = weight.input.value;
      void saveRow(row, { style: Object.keys(style).length ? style : null });
    };
    stroke.input.addEventListener('change', saveStyle);
    weight.input.addEventListener('change', saveStyle);
    const order = field('Drawing order (−100 to 100)', String(row.z), 'number');
    order.input.min = '-100';
    order.input.max = '100';
    order.input.step = '1';
    order.input.addEventListener('change', () => {
      const z = Number(order.input.value);
      if (!Number.isInteger(z) || z < -100 || z > 100) {
        say('The drawing order is a whole number from −100 to 100.', true);
        return;
      }
      void saveRow(row, { z });
    });
    box.append(role.label, stroke.label, weight.label, order.label);
    const grid = gridNow();
    const regionCells = grid
      ? cellsOf(row.geometry as unknown as Geometry, grid, context.extent)
      : null;
    const geometry = row.geometry as unknown as Geometry;
    const shape = regionCells && hasParts(geometry) ? null : editableOf(geometry);
    if (regionCells && grid) {
      box.append(cellsPanel(row, grid, regionCells));
      // One area along the grid's lines is cells and an area both (ADR 0481): its points stay.
      if (shape) {
        box.append(pointFields(row, shape));
        const children = childrenControl(row, shape);
        if (children) box.append(children);
      }
    } else if (hasParts(geometry)) {
      box.append(partsList(row, geometry));
      const focus = focusOf(row);
      const chosen = focus.part;
      const name = chosen
        ? partNames(geometry).find((p) => p.ref.part === chosen.part && p.ref.ring === chosen.ring)
        : undefined;
      if (focus.shape && name) {
        box.append(groupTitle('h3', name.name));
        box.append(pointFields(row, focus.shape, focus.write));
        const height = heightFields(row, focus.shape, focus.write);
        if (height) box.append(height);
      } else if (name) {
        box.append(
          el(
            'p',
            `${name.name} is a curve drawn with the API: it is shown and kept, and its points are not changed here.`,
            'status-text',
          ),
        );
      } else {
        box.append(el('p', 'Choose a part to change its points.', 'status-text'));
      }
    } else if (shape) {
      box.append(pointFields(row, shape));
      const height = heightFields(row, shape);
      if (height) box.append(height);
      const children = childrenControl(row, shape);
      if (children) box.append(children);
    } else {
      box.append(
        el(
          'p',
          'This drawing is a curve drawn with the API: it is shown and kept, and its points are not changed here.',
          'status-text',
        ),
      );
    }
    const moves = moveControls(row);
    if (moves) box.append(moves);
    box.append(button('Remove from this map', () => removeRow(row), { variant: 'danger' }));
    return box;
  }

  /** The words of a drawing moved in place: "Mirrored Ruin across", "Turned Ruin 180°". */
  const movedName = (name: string, how: Transform) =>
    how === 'turn' ? `Turned ${name} 180°` : `Mirrored ${name} ${how}`;

  /** Mirrors or turns a drawing about the sheet's middle, in place, as one step (ADR 0490). */
  async function moveRow(row: Row, how: Transform): Promise<string> {
    const result = moved(how, context.extent, row.geometry as unknown as Geometry, gridNow());
    if (!result.ok) {
      say(result.why, true);
      return result.why;
    }
    await guarded(async () => {
      const before = rowState(row);
      const saved = await putPlacement(context.tenant, context.mapId, row.id, {
        ...before,
        geometry: result.geometry as unknown as Record<string, unknown>,
      });
      history.record([{ entry: row.id, before, after: rowState(saved) }], movedName(row.name, how));
      context.setRows(upsert(saved));
      say(`${movedName(row.name, how)}.`);
      render();
      refresh();
    });
    return status.textContent ?? '';
  }

  /**
   * Copies a drawing, as it is or moved, to an entry not on this Map or to a new Location, with the
   * original's role, line and drawing order, as one step (ADR 0490).
   */
  async function copyRow(
    row: Row,
    how: Transform | null,
    to: { id?: string; name: string },
  ): Promise<string> {
    if (to.id && rowOf(to.id)) {
      const why = `${to.name} is already on this Map, and a Map holds one drawing for an entry. Choose another, or a new Location.`;
      say(why, true);
      return why;
    }
    const geometry = row.geometry as unknown as Geometry;
    const result = how
      ? moved(how, context.extent, geometry, gridNow())
      : { ok: true as const, geometry };
    if (!result.ok) {
      say(result.why, true);
      return result.why;
    }
    await guarded(async () => {
      const id = to.id ?? (await makeLocation(context.tenant, to.name, context.mapIsPublic)).id;
      const saved = await putPlacement(context.tenant, context.mapId, id, {
        ...rowState(row),
        geometry: result.geometry as unknown as Record<string, unknown>,
      });
      const name = `Copied ${row.name} to ${saved.name}${how ? `, ${TRANSFORM_WORDS[how]}` : ''}`;
      history.record([{ entry: id, before: null, after: rowState(saved) }], name);
      context.setRows(upsert(saved));
      say(`${name}.`);
      render();
      refresh();
    });
    return status.textContent ?? '';
  }

  /** Mirror, turn and copy for the selected drawing (ADR 0490); not on a sphere. */
  function moveControls(row: Row): HTMLElement | null {
    if (context.sphere) return null;
    const box = el('div', '', 'stack-tight map-move');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Mirror and copy');
    box.append(groupTitle('h3', 'Mirror and copy'));
    const actions = el('div', '', 'row-tight');
    actions.append(
      button(
        'Mirror across',
        async () => {
          await moveRow(row, 'across');
        },
        { variant: 'secondary' },
      ),
      button(
        'Mirror down',
        async () => {
          await moveRow(row, 'down');
        },
        { variant: 'secondary' },
      ),
      button(
        'Turn 180°',
        async () => {
          await moveRow(row, 'turn');
        },
        { variant: 'secondary' },
      ),
    );
    const how = select('Copy it', [
      ['', 'As it is'],
      ['across', 'Mirrored across'],
      ['down', 'Mirrored down'],
      ['turn', 'Turned 180°'],
    ]);
    const to = field('Copy to, by name');
    to.input.autocomplete = 'off';
    const results = el('ul', '', 'list map-copy-results');
    const chosenHow = () => (how.input.value || null) as Transform | null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let sequence = 0;
    to.input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const mine = ++sequence;
        const query = to.input.value.trim();
        if (!query) {
          results.replaceChildren();
          return;
        }
        void findEntries(context.tenant, query).then((found) => {
          if (mine !== sequence) return;
          const offers = found
            .filter((entry) => entry.id !== row.id)
            .map((entry) => {
              const item = el('li');
              item.append(
                button(
                  `Copy to ${entry.name}`,
                  async () =>
                    void (await copyRow(row, chosenHow(), { id: entry.id, name: entry.name })),
                  { variant: 'secondary' },
                ),
              );
              return item;
            });
          const fresh = el('li');
          fresh.append(
            button(
              `Copy to a new Location named ${query}`,
              async () => void (await copyRow(row, chosenHow(), { name: query })),
              { variant: 'secondary' },
            ),
          );
          results.replaceChildren(...offers, fresh);
        });
      }, 200);
    });
    box.append(actions, how.label, to.label, results);
    return box;
  }

  /** The options of the tool that is on, each a named field that takes effect as it is set (ADR 0470). */
  function optionFields(): HTMLElement | null {
    const decl = toolDecl();
    const offered = optionsOf(decl, here());
    if (offered.length === 0) return null;
    const box = el('div', '', 'stack-tight map-tool-options');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', `Options of ${decl.name}`);
    for (const option of offered) {
      if (option.type === 'number') {
        const now = optionValues.get(decl, option);
        const line = field(option.name, now === null ? '' : String(now), 'number');
        const wide = option.most - option.least > 1e9;
        if (!wide) {
          line.input.min = String(option.least);
          line.input.max = String(option.most);
        }
        line.input.step = wide ? 'any' : String(option.step);
        line.input.required = option.first === null;
        // As it is typed, not on leaving the field: a click on the Map must find the value set.
        line.input.addEventListener('input', () => {
          const empty = line.input.value.trim() === '';
          const typed = empty ? null : numberFor(option, Number(line.input.value));
          const unset = empty && option.first === null;
          line.input.setCustomValidity(
            typed !== null || unset
              ? ''
              : wide
                ? 'A number.'
                : `A number from ${option.least} to ${option.most}.`,
          );
          if (typed === null && !unset) return;
          optionValues.set(decl, option, typed);
          refresh();
        });
        box.append(line.label);
        continue;
      }
      if (option.type === 'seed') {
        // The first seed is the page's to draw, from the browser's own randomness; from then on
        // it is typed, or rolled to the next (ADR 0475).
        const line = field(option.name, String(seedNow()), 'number');
        line.input.min = '0';
        line.input.max = String(SEED_MOST);
        line.input.step = '1';
        line.input.addEventListener('input', () => {
          const typed = seedOf(line.input.value);
          line.input.setCustomValidity(
            typed === null ? `A whole number from 0 to ${SEED_MOST}.` : '',
          );
          if (typed === null) return;
          optionValues.set(decl, option, typed);
          refresh();
        });
        const roll = button(
          'Roll',
          async () => {
            setOption(option, nextSeed(seedNow()));
          },
          { variant: 'secondary' },
        );
        roll.setAttribute('aria-label', 'Roll another seed');
        box.append(line.label, roll);
        continue;
      }
      if (option.type === 'choice') {
        const line = select(
          option.name,
          option.choices.map(([value, title]): [string, string] => [value, title]),
          optionValues.get(decl, option),
        );
        line.input.addEventListener('change', () => {
          optionValues.set(decl, option, line.input.value);
        });
        box.append(line.label);
        continue;
      }
      if (option.type === 'map') {
        // This Map first, then the Maps of the library with a grid of the same kind, once read.
        const now = optionValues.get(decl, option);
        const line = select(
          option.name,
          [
            ['', 'This Map'],
            ...(exampleMaps ?? []).map((map): [string, string] => [map.id, map.name]),
          ],
          now,
        );
        line.input.addEventListener('change', () => {
          const id = line.input.value;
          setOption(option, id);
          void readExample(id);
        });
        box.append(line.label);
        if (exampleMaps === null)
          box.append(el('p', 'Reading the Maps of the library.', 'status-text'));
        continue;
      }
      if (option.type === 'text') {
        const line = field(option.name, optionValues.get(decl, option));
        line.input.maxLength = option.longest;
        line.input.required = option.first === '';
        line.input.autocomplete = 'off';
        line.input.addEventListener('input', () => {
          optionValues.set(decl, option, line.input.value);
        });
        box.append(line.label);
        continue;
      }
      const line = field(option.name, '', 'checkbox');
      line.input.checked = optionValues.get(decl, option);
      line.input.addEventListener('change', () => {
        optionValues.set(decl, option, line.input.checked);
      });
      box.append(line.label);
    }
    return box;
  }

  function setOption(option: ToolOption, value: OptionValue) {
    optionValues.set(toolDecl(), option, value);
    render();
    refresh();
  }

  function render() {
    panel.replaceChildren();
    panel.hidden = !editing;
    if (!editing) return;
    if (brushing()) brushNow();
    const options = optionFields();
    if (options) panel.append(options);
    if (toolName !== 'select') {
      // A fill of cells draws for the entries of its example: there is no entry to choose.
      if (!fillsCells()) panel.append(chooser());
      if (generating()) panel.append(generatorControls());
      return;
    }
    const row = rowOf(selectedId);
    if (row) panel.append(editPanel(row));
    else {
      panel.append(
        el(
          'p',
          'Select a place on the map or in the list to change it, or choose a tool to draw.',
          'status-text',
        ),
      );
    }
  }

  // Undo and redo from the keyboard, unless a field has the keys.
  const onKey = (event: KeyboardEvent) => {
    if (!editing || !(event.ctrlKey || event.metaKey) || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('input, textarea, select')) return;
    const key = event.key.toLowerCase();
    if (key === 'z' && !event.shiftKey) {
      event.preventDefault();
      void undo();
    } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
      event.preventDefault();
      void redo();
    }
  };
  document.addEventListener('keydown', onKey);

  renderToolbar();
  render();

  return {
    toolbar,
    panel,
    history: historyPanel,
    commandLine,
    placeEntry,
    editing: () => editing,
    selected(id) {
      if (id !== selectedId) selectedPart = null;
      selectedId = id;
      working = null;
      if (editing && toolName === 'select') {
        render();
        refresh();
      }
    },
    destroy() {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('keydown', onToolKey, true);
      shortcutsDialog.dialog.remove();
      context.view().setTool(null);
      context.view().setOverlay([]);
    },
  };
}
