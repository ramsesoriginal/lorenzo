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
};

const later = 'It is built later, with its own decision.';

export const TOOLS: ToolDecl[] = [
  {
    id: 'select',
    name: 'Select',
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
    state: 'planned',
    reason: later,
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
