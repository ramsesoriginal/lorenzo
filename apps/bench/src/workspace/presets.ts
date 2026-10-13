// The layout presets of the design (Write, Inspect, Compare) as pure functions of a workspace:
// the panes a preset arranges go to their places, panes in floating windows stay where they are,
// and any other pane that is docked (the compare grid, a formula editor...) stays with the entry.
// Ported from the prototype's `buildTree`; tested without a DOM.

import {
  type Group,
  group,
  locate,
  type Node,
  normalize,
  treeGroups,
  type Workspace,
} from './model';

export type Preset = 'write' | 'inspect' | 'compare';
export const PRESETS: readonly Preset[] = ['write', 'inspect', 'compare'];
export const PRESET_LABEL: Record<Preset, string> = {
  write: 'Write',
  inspect: 'Inspect',
  compare: 'Compare',
};

/** The panes a preset places itself; every other docked pane stays with the entry. */
const OWN = ['explorer', 'entry', 'props', 'links', 'table', 'ancestry'];

export function applyPreset(ws: Workspace, name: Preset): Workspace {
  const floating = new Set(ws.floats.flatMap((f) => f.panes));
  const docked = (p: string) => !floating.has(p);
  const kept = treeGroups(ws.tree)
    .flatMap((g) => g.panes)
    .filter((p) => !OWN.includes(p) && docked(p));
  const g = (id: string, panes: string[]): Group => group(id, panes.filter(docked));
  const main = g('g-main', ['entry', ...kept]);
  let tree: Node | null;
  if (name === 'write') tree = main;
  else {
    const rail = g('g-rail', ['explorer']);
    const right = g('g-right', ['props', 'links']);
    if (name === 'inspect')
      tree = {
        t: 's',
        id: 's-a',
        dir: 'row',
        ratios: [0.172, 0.568, 0.26],
        kids: [rail, main, right],
      };
    else {
      const top: Node = {
        t: 's',
        id: 's-c',
        dir: 'row',
        ratios: [0.74, 0.26],
        kids: [main, right],
      };
      const bottom: Node = {
        t: 's',
        id: 's-d',
        dir: 'row',
        ratios: [0.69, 0.31],
        kids: [g('g-table', ['table']), g('g-graph', ['ancestry'])],
      };
      const centre: Node = {
        t: 's',
        id: 's-b',
        dir: 'col',
        ratios: [0.66, 0.34],
        kids: [top, bottom],
      };
      tree = { t: 's', id: 's-a', dir: 'row', ratios: [0.172, 0.828], kids: [rail, centre] };
    }
  }
  return { ...ws, tree: normalize(tree) };
}

/** The panes of each group, nested by direction: what a layout is, without its sizes or tabs. */
function shape(node: Node | null): unknown {
  if (!node) return null;
  if (node.t === 'g') return [...node.panes].sort();
  return { dir: node.dir, kids: node.kids.map(shape) };
}

/** The preset a workspace is arranged as (whatever the sizes and the active tabs), if any. */
export function activePreset(ws: Workspace): Preset | null {
  const mine = JSON.stringify(shape(ws.tree));
  for (const name of PRESETS)
    if (JSON.stringify(shape(applyPreset(ws, name).tree)) === mine) return name;
  return null;
}

export { locate };
