import { describe, expect, it } from 'vitest';
import {
  addTab,
  dockHome,
  emptyWorkspace,
  floatOut,
  group,
  layout,
  locate,
  move,
  type Node,
  normalize,
  parse,
  removePane,
  resize,
  serialize,
  setActive,
  showPane,
  splitGroup,
  treeGroups,
  type Workspace,
} from './model';

const KNOWN = ['a', 'b', 'c', 'd'];
const two = (): Workspace => ({
  tree: {
    t: 's',
    id: 's1',
    dir: 'row',
    ratios: [0.25, 0.75],
    kids: [group('g1', ['a']), group('g2', ['b', 'c'])],
  },
  floats: [],
  next: 10,
});

describe('normalize', () => {
  it('drops empty groups and renormalizes the ratios', () => {
    const n = normalize({
      t: 's',
      id: 's',
      dir: 'row',
      ratios: [0.5, 0.25, 0.25],
      kids: [group('x', []), group('y', ['a']), group('z', ['b'])],
    }) as Node;
    expect(n.t === 's' && n.ratios).toEqual([0.5, 0.5]);
  });
  it('unwraps a split with one child', () => {
    const g = group('g', ['a']);
    expect(normalize({ t: 's', id: 's', dir: 'col', ratios: [1], kids: [g] })).toBe(g);
  });
  it('merges a nested split of the same direction, keeping proportions', () => {
    const n = normalize({
      t: 's',
      id: 'o',
      dir: 'row',
      ratios: [0.5, 0.5],
      kids: [
        group('a', ['a']),
        {
          t: 's',
          id: 'i',
          dir: 'row',
          ratios: [0.5, 0.5],
          kids: [group('b', ['b']), group('c', ['c'])],
        },
      ],
    }) as Node;
    expect(n.t === 's' && n.ratios).toEqual([0.5, 0.25, 0.25]);
    expect(n.t === 's' && n.kids.length).toBe(3);
  });
  it('is null for nothing', () => {
    expect(normalize(null)).toBeNull();
    expect(normalize(group('g', []))).toBeNull();
  });
});

describe('layout', () => {
  it('gives every group a share of the unit square, and a divider between', () => {
    const l = layout(two().tree);
    expect(l.groups.map((g) => [g.g.id, g.x, g.w])).toEqual([
      ['g1', 0, 0.25],
      ['g2', 0.25, 0.75],
    ]);
    expect(l.splits).toHaveLength(1);
    expect(l.splits[0].rect.x).toBe(0.25);
  });
});

describe('moving tabs', () => {
  it('closing the last tab of a group collapses the split', () => {
    const ws = removePane(two(), 'a');
    expect(ws.tree?.t).toBe('g');
    expect(treeGroups(ws.tree)[0].panes).toEqual(['b', 'c']);
  });
  it('closing the active tab activates its neighbour', () => {
    const ws = removePane(two(), 'b');
    expect(treeGroups(ws.tree).find((g) => g.id === 'g2')?.active).toBe('c');
  });
  it('splits a group on a side and puts the new group first on left/top', () => {
    const ws = splitGroup(removePane(two(), 'c'), 'g2', 'top', ['c']);
    const g = treeGroups(ws.tree).find((x) => x.panes.includes('c'));
    const l = layout(ws.tree);
    const c = l.groups.find((x) => x.g.id === g?.id);
    const b = l.groups.find((x) => x.g.panes.includes('b'));
    expect(c && b && c.y < b.y).toBe(true);
  });
  it('drops a tab onto another group at an index', () => {
    const { ws } = move(
      two(),
      ['a'],
      'a',
      { gid: 'g2', zone: 'center', float: false, idx: 1 },
      'g1',
    );
    expect(ws.tree?.t).toBe('g');
    expect(treeGroups(ws.tree)[0].panes).toEqual(['b', 'a', 'c']);
  });
  it('does nothing when a lone group is dropped on itself', () => {
    const start = two();
    const { ws } = move(
      start,
      ['a'],
      'a',
      { gid: 'g1', zone: 'center', float: false, idx: null },
      'g1',
    );
    expect(ws).toBe(start);
  });
  it('floats a tab out and docks it back where it came from', () => {
    const out = floatOut(two(), ['c'], 'c', 40, 50);
    expect(out.ws.floats).toHaveLength(1);
    expect(locate(out.ws, 'c')?.kind).toBe('float');
    const back = dockHome(removePane(out.ws, 'c'), ['c'], 'c', out.home);
    expect(locate(back, 'c')).toEqual({ kind: 'tree', gid: 'g2' });
  });
  it('raises a floating window when it is activated', () => {
    let ws = floatOut(two(), ['c'], 'c', 0, 0).ws;
    ws = floatOut(ws, ['b'], 'b', 0, 0).ws;
    const first = ws.floats[0].id;
    ws = setActive(ws, first, 'c');
    expect(ws.floats[ws.floats.length - 1].id).toBe(first);
  });
  it('gives new ids that do not clash', () => {
    let ws = splitGroup(two(), 'g1', 'right', ['d']);
    ws = splitGroup(ws, 'g1', 'bottom', ['x']);
    const ids = treeGroups(ws.tree).map((g) => g.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('resize', () => {
  it('moves a divider and keeps the pair summing the same', () => {
    const ws = resize(two(), 's1', 0, 0.1);
    const s = ws.tree as Extract<Node, { t: 's' }>;
    expect(s.ratios[0]).toBeCloseTo(0.35);
    expect(s.ratios[0] + s.ratios[1]).toBeCloseTo(1);
  });
  it('does not shrink a pane under the minimum', () => {
    const s = resize(two(), 's1', 0, -5).tree as Extract<Node, { t: 's' }>;
    expect(s.ratios[0]).toBeCloseTo(0.08);
  });
});

describe('showPane', () => {
  it('focuses a pane that is open, else adds it', () => {
    const ws = showPane(two(), 'c');
    expect(treeGroups(ws.tree).find((g) => g.id === 'g2')?.active).toBe('c');
    const ws2 = showPane(ws, 'd', 'g1');
    expect(locate(ws2, 'd')).toEqual({ kind: 'tree', gid: 'g1' });
  });
  it('makes a first group from nothing', () => {
    expect(locate(showPane(emptyWorkspace(), 'a'), 'a')?.kind).toBe('tree');
  });
});

describe('addTab', () => {
  it('clamps the index', () => {
    const ws = addTab(two(), 'g2', ['d'], 99);
    expect(treeGroups(ws.tree).find((g) => g.id === 'g2')?.panes).toEqual(['b', 'c', 'd']);
  });
});

describe('persistence', () => {
  it('round-trips', () => {
    const ws = floatOut(two(), ['c'], 'c', 5, 6).ws;
    expect(parse(serialize(ws), KNOWN)).toEqual(ws);
  });
  it('drops anything it cannot trust', () => {
    expect(parse(null, KNOWN)).toBeNull();
    expect(parse('{', KNOWN)).toBeNull();
    expect(parse(JSON.stringify({ v: 99, ws: two() }), KNOWN)).toBeNull();
    expect(parse(serialize(two()), ['a'])).toBeNull(); // a pane that no longer exists
  });
});
