// The tools of the drawing view (MP6) as declarations, not as a layout: a tool states its name, its
// group, its icon, its key, what it takes as input, what it makes and whether it can be used yet. The
// toolbox, the list of all tools, the key map and the command line are drawn from this one list, so a
// new tool is one more entry. Pure, so it is tested without a browser.
//
// A tool that the data cannot hold yet, or that is not built yet, is `planned`: it is listed, says
// why, and does nothing. Each is built later, with its own ADR (ADR 0421).

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
 * A type is built with the first tool that has one: `toggle` for snapping, `number` for a spline.
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
      first: number;
      least: number;
      most: number;
      /** A value is kept to a whole number of steps from the least. */
      step: number;
    }
);

export type ToggleOption = Extract<ToolOption, { type: 'toggle' }>;
export type NumberOption = Extract<ToolOption, { type: 'number' }>;

export type OptionValue = boolean | number;

/** A number an option can hold: within its range and on its step; null when it is out of range. */
export function numberFor(option: NumberOption, value: number): number | null {
  if (!Number.isFinite(value) || value < option.least || value > option.most) return null;
  const stepped = option.least + Math.round((value - option.least) / option.step) * option.step;

  return Math.min(option.most, Math.round(stepped * 1e6) / 1e6);
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
  /** What a person can set for it (ADR 0470). */
  options?: ToolOption[];
};

const later = 'It is built later, with its own decision.';

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
    state: 'planned',
    reason: later,
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
    state: 'planned',
    reason: later,
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
    state: 'planned',
    reason: later,
  },
  {
    id: 'marching-squares',
    name: 'Fill by marching squares',
    group: 'generate',
    icon: 'layers',
    key: 'm',
    input: 'a region and a seed',
    output: 'areas and contour lines',
    state: 'planned',
    reason: later,
  },
  {
    id: 'wave-function-collapse',
    name: 'Fill by wave function collapse',
    group: 'generate',
    icon: 'layers',
    key: 'w',
    input: 'a region on a grid and a seed',
    output: 'cells',
    state: 'planned',
    reason: later,
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
  get(tool: ToolDecl, option: NumberOption): number;
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
      values.get(key(tool, option)) ?? option.first) as OptionValues['get'],
    set(tool, option, value) {
      values.set(key(tool, option), value);
    },
  };
}
