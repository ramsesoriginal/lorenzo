// The tools of the drawing view (MP6) as declarations, not as a layout: a tool states its name, its
// group, its icon, its key, what it takes as input, what it makes and whether it can be used yet. The
// toolbox, the list of all tools, the key map and the command line are drawn from this one list, so a
// new tool is one more entry. Pure, so it is tested without a browser.
//
// A tool that the data cannot hold yet, or that is not built yet, is `planned`: it is listed, says
// why, and does nothing. Each is built later, with its own ADR (ADR 0421).

import { ROLE_WORDS, ROLES } from '@lorenzo/map-renderer';

export type ToolGroup = 'select' | 'place' | 'draw' | 'terrain' | 'generate';

export const GROUP_NAMES: Record<ToolGroup, string> = {
  select: 'Select',
  place: 'Place',
  draw: 'Draw',
  terrain: 'Terrain',
  generate: 'Generate',
};

export const GROUPS: ToolGroup[] = ['select', 'place', 'draw', 'terrain', 'generate'];

/**
 * An option of a tool (ADR 0470): the Options tab draws it and the command line sets it by its word.
 * A type is built with the first tool that has one: `toggle` for snapping, `number` for a spline,
 * `text` for a height line's unit, `seed` and `choice` for the generators, and `map` for the example
 * of a fill of cells.
 */
export type ToolOption = {
  id: string;
  /** What the field is called. */
  name: string;
  /** What the command line calls it: one word. */
  word: string;
  /** One value for every tool that lists it. */
  shared?: boolean;
  /** Only on a Map with a grid. */
  needsGrid?: boolean;
} & (
  | {
      type: 'toggle';
      /** The value it starts with. */
      first: boolean;
    }
  | {
      type: 'number';
      /** Null when nothing may be assumed: the person gives it before the tool can finish. */
      first: number | null;
      least: number;
      most: number;
      /** A value is kept to a whole number of steps. */
      step: number;
    }
  | {
      /** A generator's seed (ADR 0475): a whole number the page draws first and a person may type. */
      type: 'seed';
    }
  | {
      /** One of a closed list, each a value and what it is called; the first is where it starts. */
      type: 'choice';
      first: string;
      choices: readonly (readonly [string, string])[];
    }
  | {
      /**
       * A Map of the library by its id, '' for this one (ADR 0479). The Maps it offers are read
       * when the tool is chosen, so the declaration names none.
       */
      type: 'map';
      first: '';
    }
  | {
      type: 'text';
      /** Empty when the person gives it before the tool can finish. */
      first: string;
      /** The most characters it takes. */
      longest: number;
    }
);

export type ToggleOption = Extract<ToolOption, { type: 'toggle' }>;
export type NumberOption = Extract<ToolOption, { type: 'number' }>;
export type TextOption = Extract<ToolOption, { type: 'text' }>;
export type SeedOption = Extract<ToolOption, { type: 'seed' }>;
export type MapOption = Extract<ToolOption, { type: 'map' }>;
export type ChoiceOption = Extract<ToolOption, { type: 'choice' }>;

export type OptionValue = boolean | number | string | null;

/** A number an option can hold: within its range and on its step; null when it is out of range. */
export function numberFor(option: NumberOption, value: number): number | null {
  if (!Number.isFinite(value) || value < option.least || value > option.most) return null;
  const stepped = Math.round(value / option.step) * option.step;

  return Math.max(option.least, Math.min(option.most, Math.round(stepped * 1e6) / 1e6));
}

/** How round a spline is (ADR 0471): 0 the roundest, 1 straight. */
export const TENSION: NumberOption = {
  id: 'tension',
  name: 'Tension',
  word: 'tension',
  type: 'number',
  first: 0.5,
  least: 0,
  most: 1,
  step: 0.05,
};

/** Snap to the grid (ADR 0356): the drawing tools and Select share it. */
export const SNAP: ToggleOption = {
  id: 'snap',
  name: 'Snap to the grid',
  word: 'snap',
  type: 'toggle',
  first: true,
  shared: true,
  needsGrid: true,
};

/** How much of a freehand stroke is smoothed away (ADR 0472), in screen pixels. */
export const TOLERANCE: NumberOption = {
  id: 'tolerance',
  name: 'Tolerance (pixels)',
  word: 'tolerance',
  type: 'number',
  first: 2,
  least: 0.5,
  most: 10,
  step: 0.5,
};

/** The seed of a generator (ADR 0475): each generator lists it, and each keeps its own. */
export const SEED: SeedOption = { id: 'seed', name: 'Seed', word: 'seed', type: 'seed' };

/**
 * The role of what a generator draws (ADR 0475): the person's to choose, and none at first. The
 * list is the renderer's closed list of roles (ADR 0337).
 */
/** The Map a fill of cells learns from (ADR 0479): this one at first. */
export const EXAMPLE: MapOption = {
  id: 'example',
  name: 'Example',
  word: 'example',
  type: 'map',
  first: '',
};

export const ROLE: ChoiceOption = {
  id: 'role',
  name: 'Role',
  word: 'role',
  type: 'choice',
  first: '',
  choices: [
    ['', 'None'],
    ...ROLES.map(
      (role) =>
        [role, ROLE_WORDS[role].charAt(0).toUpperCase() + ROLE_WORDS[role].slice(1)] as const,
    ),
  ],
};

/** The options of the Cave system (ADR 0476). */
export const CAVE_SIZE: NumberOption = {
  id: 'size',
  name: 'Size (cells across)',
  word: 'size',
  type: 'number',
  first: 48,
  least: 16,
  most: 96,
  step: 1,
};

export const CAVE_DENSITY: NumberOption = {
  id: 'density',
  name: 'Density',
  word: 'density',
  type: 'number',
  first: 0.46,
  least: 0.3,
  most: 0.6,
  step: 0.01,
};

export const CAVE_PASSES: NumberOption = {
  id: 'passes',
  name: 'Passes',
  word: 'passes',
  type: 'number',
  first: 4,
  least: 0,
  most: 8,
  step: 1,
};

export const CAVE_SMALLEST: NumberOption = {
  id: 'smallest',
  name: 'Smallest cave (cells)',
  word: 'smallest',
  type: 'number',
  first: 6,
  least: 1,
  most: 60,
  step: 1,
};

/** The options of the Fill by marching squares (ADR 0477). */
export const FILL_SCALE: NumberOption = {
  id: 'scale',
  name: 'Scale',
  word: 'scale',
  type: 'number',
  first: 8,
  least: 2,
  most: 20,
  step: 1,
};

export const FILL_LEVEL: NumberOption = {
  id: 'level',
  name: 'Level',
  word: 'level',
  type: 'number',
  first: 0.5,
  least: 0.2,
  most: 0.8,
  step: 0.01,
};

export const FILL_SMALLEST: NumberOption = {
  id: 'smallest',
  name: 'Smallest area (cells)',
  word: 'smallest',
  type: 'number',
  first: 4,
  least: 1,
  most: 60,
  step: 1,
};

export const FILL_LINES: NumberOption = {
  id: 'lines',
  name: 'Height lines',
  word: 'lines',
  type: 'number',
  first: 0,
  least: 0,
  most: 8,
  step: 1,
};

/** The height of the first line and of each next one more: never assumed (ADR 0473). */
export const FILL_FIRST: NumberOption = {
  id: 'first',
  name: 'First height',
  word: 'first',
  type: 'number',
  first: null,
  least: -1_000_000_000_000,
  most: 1_000_000_000_000,
  step: 0.000001,
};

export const FILL_STEP: NumberOption = {
  id: 'step',
  name: 'Step',
  word: 'step',
  type: 'number',
  first: null,
  least: -1_000_000_000_000,
  most: 1_000_000_000_000,
  step: 0.000001,
};

/** The height a height line carries (ADR 0473): never assumed, so it starts empty. */
export const HEIGHT: NumberOption = {
  id: 'height',
  name: 'Height',
  word: 'height',
  type: 'number',
  first: null,
  least: -1_000_000_000_000,
  most: 1_000_000_000_000,
  step: 0.000001,
};

/** The unit of that height, in the author's own words: never assumed either. */
export const UNIT: TextOption = {
  id: 'unit',
  name: 'Unit',
  word: 'unit',
  type: 'text',
  first: '',
  longest: 32,
};

export type ToolDecl = {
  id: string;
  name: string;
  group: ToolGroup;
  /** An atlas icon name. */
  icon: string;
  /** The one key, a letter. */
  key: string;
  /** What it takes: a click, a path, a region. */
  input: string;
  /** What it makes, in what the Map already holds. */
  output: string;
  state: 'ready' | 'planned';
  /** Why a planned tool is not built. */
  reason?: string;
  /** Only on a Map with a grid. */
  needsGrid?: boolean;
  /** Not on a sphere. */
  notOnSphere?: boolean;
  /** It previews and applies (ADR 0475): its behaviour is in `generators.ts`. */
  generator?: boolean;
  /**
   * A generator that writes cells for the entries of an example, not one entry's drawing
   * (ADR 0479): it has no entry to choose.
   */
  cells?: boolean;
  /** What a person can set for it (ADR 0470). */
  options?: ToolOption[];
};

export const TOOLS: ToolDecl[] = [
  {
    id: 'select',
    name: 'Select',
    options: [SNAP],
    group: 'select',
    icon: 'select',
    key: 'v',
    input: 'a click, or a drag for a box',
    output: 'nothing',
    state: 'ready',
  },
  {
    id: 'pin',
    name: 'Pin',
    options: [SNAP],
    group: 'place',
    icon: 'kind-location',
    key: 'p',
    input: 'a click',
    output: 'a point',
    state: 'ready',
  },
  {
    id: 'circle',
    name: 'Circle',
    options: [SNAP],
    group: 'place',
    icon: 'circle',
    key: 'c',
    input: 'two clicks',
    output: 'a circle',
    state: 'ready',
    notOnSphere: true,
  },
  {
    id: 'line',
    name: 'Line',
    options: [SNAP],
    group: 'draw',
    icon: 'connection',
    key: 'l',
    input: 'a path',
    output: 'a line',
    state: 'ready',
  },
  {
    id: 'spline',
    name: 'Spline',
    group: 'draw',
    icon: 'connection',
    key: 's',
    input: 'a path',
    output: 'a line (a smooth curve through the points)',
    state: 'ready',
    notOnSphere: true,
    options: [TENSION],
  },
  {
    id: 'freehand',
    name: 'Freehand',
    group: 'draw',
    icon: 'edit',
    key: 'f',
    input: 'a drag',
    output: 'a line (the stroke, simplified)',
    state: 'ready',
    notOnSphere: true,
    options: [TOLERANCE],
  },
  {
    id: 'area',
    name: 'Area',
    options: [SNAP],
    group: 'draw',
    icon: 'kind-location',
    key: 'a',
    input: 'a path, closed',
    output: 'an area',
    state: 'ready',
  },
  {
    id: 'cells',
    name: 'Cells',
    options: [SNAP],
    group: 'draw',
    icon: 'layers',
    key: 'g',
    input: 'clicks on cells',
    output: 'cells',
    state: 'ready',
    needsGrid: true,
  },
  {
    id: 'height-line',
    name: 'Height line',
    group: 'terrain',
    icon: 'connection',
    key: 't',
    input: 'a path and a value',
    output: 'a line with a value and a unit',
    state: 'ready',
    notOnSphere: true,
    options: [HEIGHT, UNIT],
  },
  {
    id: 'height-brush',
    name: 'Height brush',
    group: 'terrain',
    icon: 'edit',
    key: 'h',
    input: 'a brush',
    output: 'a heightmap',
    state: 'planned',
    reason: `A heightmap is a raster, which a Map does not hold. It needs its own decision first.`,
  },
  {
    id: 'cave-system',
    name: 'Cave system',
    group: 'generate',
    icon: 'layers',
    key: 'k',
    input: 'a region and a seed',
    output: 'areas',
    state: 'ready',
    notOnSphere: true,
    generator: true,
    options: [CAVE_SIZE, CAVE_DENSITY, CAVE_PASSES, CAVE_SMALLEST, ROLE, SEED],
  },
  {
    id: 'marching-squares',
    name: 'Fill by marching squares',
    group: 'generate',
    icon: 'layers',
    key: 'm',
    input: 'a region and a seed',
    output: 'areas and contour lines',
    state: 'ready',
    notOnSphere: true,
    generator: true,
    options: [
      FILL_SCALE,
      FILL_LEVEL,
      FILL_SMALLEST,
      FILL_LINES,
      FILL_FIRST,
      FILL_STEP,
      UNIT,
      ROLE,
      SEED,
    ],
  },
  {
    id: 'wave-function-collapse',
    name: 'Fill by wave function collapse',
    group: 'generate',
    icon: 'layers',
    key: 'w',
    input: 'a region on a grid and a seed',
    output: 'cells',
    state: 'ready',
    needsGrid: true,
    notOnSphere: true,
    generator: true,
    cells: true,
    options: [EXAMPLE, SEED],
  },
];

export const toolByKey = (key: string): ToolDecl | undefined =>
  TOOLS.find((tool) => tool.key === key.toLowerCase());

export const toolById = (id: string): ToolDecl | undefined => TOOLS.find((tool) => tool.id === id);

/** The tools of one group, in order. */
export const toolsOf = (group: ToolGroup): ToolDecl[] => TOOLS.filter((t) => t.group === group);

/** The tools whose name, group or key a few words match, all of them when there are none. */
export function searchTools(query: string): ToolDecl[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return TOOLS;

  return TOOLS.filter((tool) => {
    const hay = `${tool.name} ${GROUP_NAMES[tool.group]} ${tool.key}`.toLowerCase();

    return words.every((word) => hay.includes(word));
  });
}

/** Whether a tool can be used on this Map: ready, and with a grid or off a sphere where it says so. */
export function usable(tool: ToolDecl, map: { grid: boolean; sphere: boolean }): boolean {
  if (tool.state !== 'ready') return false;
  if (tool.needsGrid && !map.grid) return false;
  if (tool.notOnSphere && map.sphere) return false;

  return true;
}

/** The options of a tool that this Map can use: one that needs a grid is not offered without one. */
export function optionsOf(tool: ToolDecl, map: { grid: boolean }): ToolOption[] {
  return (tool.options ?? []).filter((option) => map.grid || !option.needsGrid);
}

export type OptionValues = {
  get(tool: ToolDecl, option: ToggleOption): boolean;
  get(tool: ToolDecl, option: NumberOption): number | null;
  get(tool: ToolDecl, option: TextOption): string;
  get(tool: ToolDecl, option: ChoiceOption): string;
  get(tool: ToolDecl, option: MapOption): string;
  get(tool: ToolDecl, option: SeedOption): number | null;
  get(tool: ToolDecl, option: ToolOption): OptionValue;
  set(tool: ToolDecl, option: ToolOption, value: OptionValue): void;
};

/** What the options are set to, kept in the page's memory: one value a tool and option, or one for all when shared. */
export function createOptionValues(): OptionValues {
  const values = new Map<string, OptionValue>();
  const key = (tool: ToolDecl, option: ToolOption) =>
    option.shared ? option.id : `${tool.id}.${option.id}`;

  return {
    get: ((tool: ToolDecl, option: ToolOption) =>
      values.get(key(tool, option)) ??
      (option.type === 'seed' ? null : option.first)) as OptionValues['get'],
    set(tool, option, value) {
      values.set(key(tool, option), value);
    },
  };
}
