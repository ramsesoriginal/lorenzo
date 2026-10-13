// The workbench's layout as plain data: a tree of splits and tab groups, plus floating windows.
// Everything here is pure (same input, same output, nothing mutated) so it is tested without a
// DOM. Ported from the design prototype (docs/design/bench), see ADR 0210.

export type PaneId = string;
export type Dir = 'row' | 'col';
export type Side = 'left' | 'right' | 'top' | 'bottom';

export interface Group {
  t: 'g';
  id: string;
  panes: PaneId[];
  active: PaneId;
}
export interface Split {
  t: 's';
  id: string;
  dir: Dir;
  ratios: number[];
  kids: Node[];
}
export type Node = Group | Split;
export interface Float extends Omit<Group, 't'> {
  t: 'g';
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface Workspace {
  tree: Node | null;
  floats: Float[];
  /** Counter for new ids, kept in the workspace so ids are deterministic. */
  next: number;
}

export const MIN_RATIO = 0.08;

export function group(id: string, panes: PaneId[]): Group {
  return { t: 'g', id, panes: panes.slice(), active: panes[0] };
}

export function emptyWorkspace(): Workspace {
  return { tree: null, floats: [], next: 1 };
}

/** Drop empty groups, merge a split into a parent split of the same direction, unwrap singles. */
export function normalize(node: Node | null): Node | null {
  if (!node) return null;
  if (node.t === 'g') return node.panes.length ? node : null;
  const kids: Node[] = [];
  let ratios: number[] = [];
  node.kids.forEach((k, i) => {
    const nk = normalize(k);
    if (nk) {
      kids.push(nk);
      ratios.push(node.ratios[i]);
    }
  });
  if (!kids.length) return null;
  const sum = ratios.reduce((a, b) => a + b, 0);
  ratios = ratios.map((r) => r / sum);
  if (kids.length === 1) return kids[0];
  const flatKids: Node[] = [];
  const flatRatios: number[] = [];
  kids.forEach((k, i) => {
    if (k.t === 's' && k.dir === node.dir) {
      k.kids.forEach((kk, j) => {
        flatKids.push(kk);
        flatRatios.push(ratios[i] * k.ratios[j]);
      });
    } else {
      flatKids.push(k);
      flatRatios.push(ratios[i]);
    }
  });
  return { ...node, kids: flatKids, ratios: flatRatios };
}

export function treeGroups(node: Node | null, out: Group[] = []): Group[] {
  if (!node) return out;
  if (node.t === 'g') out.push(node);
  else for (const k of node.kids) treeGroups(k, out);
  return out;
}

export type Location = { kind: 'tree' | 'float'; gid: string };

export function locate(ws: Workspace, pane: PaneId): Location | null {
  const g = treeGroups(ws.tree).find((x) => x.panes.includes(pane));
  if (g) return { kind: 'tree', gid: g.id };
  const f = ws.floats.find((x) => x.panes.includes(pane));
  return f ? { kind: 'float', gid: f.id } : null;
}

export function mapTree(node: Node | null, fn: (g: Group) => Node): Node | null {
  if (!node) return null;
  if (node.t === 'g') return fn(node);
  return { ...node, kids: node.kids.map((k) => mapTree(k, fn) as Node) };
}

export function setRatios(
  node: Node | null,
  sid: string,
  i: number,
  a: number,
  b: number,
): Node | null {
  if (!node || node.t === 'g') return node;
  if (node.id === sid) {
    const ratios = node.ratios.slice();
    ratios[i] = a;
    ratios[i + 1] = b;
    return { ...node, ratios };
  }
  return { ...node, kids: node.kids.map((k) => setRatios(k, sid, i, a, b) as Node) };
}

/** Resize the divider after kid `i` of split `sid` by `delta` (a fraction of the split's size). */
export function resize(ws: Workspace, sid: string, i: number, delta: number): Workspace {
  const find = (n: Node | null): Split | null => {
    if (!n || n.t === 'g') return null;
    if (n.id === sid) return n;
    for (const k of n.kids) {
      const r = find(k);
      if (r) return r;
    }
    return null;
  };
  const s = find(ws.tree);
  if (!s) return ws;
  const pair = s.ratios[i] + s.ratios[i + 1];
  const a = Math.max(MIN_RATIO, Math.min(pair - MIN_RATIO, s.ratios[i] + delta));
  return { ...ws, tree: setRatios(ws.tree, sid, i, a, pair - a) };
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface Layout {
  groups: (Rect & { g: Group })[];
  splits: { sid: string; i: number; dir: Dir; rect: Rect; nodeRect: Rect }[];
}

/** Unit-square layout: every rect is a fraction of the workspace. */
export function layout(tree: Node | null): Layout {
  const out: Layout = { groups: [], splits: [] };
  const walk = (node: Node, x: number, y: number, w: number, h: number) => {
    if (node.t === 'g') {
      out.groups.push({ g: node, x, y, w, h });
      return;
    }
    let pos = 0;
    node.kids.forEach((k, i) => {
      const r = node.ratios[i];
      if (node.dir === 'row') {
        walk(k, x + pos * w, y, r * w, h);
        pos += r;
        if (i < node.kids.length - 1)
          out.splits.push({
            sid: node.id,
            i,
            dir: 'row',
            rect: { x: x + pos * w, y, w: 0, h },
            nodeRect: { x, y, w, h },
          });
      } else {
        walk(k, x, y + pos * h, w, r * h);
        pos += r;
        if (i < node.kids.length - 1)
          out.splits.push({
            sid: node.id,
            i,
            dir: 'col',
            rect: { x, y: y + pos * h, w, h: 0 },
            nodeRect: { x, y, w, h },
          });
      }
    });
  };
  if (tree) walk(tree, 0, 0, 1, 1);
  return out;
}

export function removePane(ws: Workspace, pane: PaneId): Workspace {
  const drop = (g: Group): Group => {
    if (!g.panes.includes(pane)) return g;
    const panes = g.panes.filter((p) => p !== pane);
    return { ...g, panes, active: g.active === pane ? panes[0] : g.active };
  };
  return {
    ...ws,
    tree: normalize(mapTree(ws.tree, drop)),
    floats: ws.floats.map((f) => ({ ...f, ...drop(f) })).filter((f) => f.panes.length),
  };
}

export function addTab(
  ws: Workspace,
  gid: string,
  panes: PaneId[],
  idx: number | null,
  active?: PaneId,
): Workspace {
  const put = <T extends Group>(g: T): T => {
    if (g.id !== gid) return g;
    const list = g.panes.filter((p) => !panes.includes(p));
    const at = idx == null ? list.length : Math.max(0, Math.min(list.length, idx));
    list.splice(at, 0, ...panes);
    return { ...g, panes: list, active: active ?? panes[0] };
  };
  return { ...ws, tree: mapTree(ws.tree, put), floats: ws.floats.map(put) };
}

/** Put `panes` in a new group beside group `gid`, on `side`. */
export function splitGroup(
  ws: Workspace,
  gid: string,
  side: Side,
  panes: PaneId[],
  active?: PaneId,
): Workspace {
  const sid = `x${ws.next}`;
  const nid = `g${ws.next + 1}`;
  const ng: Group = { t: 'g', id: nid, panes: panes.slice(), active: active ?? panes[0] };
  const dir: Dir = side === 'left' || side === 'right' ? 'row' : 'col';
  const before = side === 'left' || side === 'top';
  const tree = mapTree(ws.tree, (g) =>
    g.id !== gid
      ? g
      : { t: 's', id: sid, dir, ratios: [0.5, 0.5], kids: before ? [ng, g] : [g, ng] },
  );
  return { ...ws, tree: normalize(tree), next: ws.next + 2 };
}

export function setActive(ws: Workspace, gid: string, pane: PaneId): Workspace {
  const act = <T extends Group>(g: T): T =>
    g.id === gid && g.panes.includes(pane) ? { ...g, active: pane } : g;
  let floats = ws.floats.map(act);
  const fi = floats.findIndex((f) => f.id === gid);
  // Activating a floating window also raises it: the last one is on top.
  if (fi >= 0 && fi < floats.length - 1) {
    const f = floats[fi];
    floats = floats.filter((_, i) => i !== fi).concat([f]);
  }
  return { ...ws, tree: mapTree(ws.tree, act), floats };
}

export function raise(ws: Workspace, gid: string): Workspace {
  const f = ws.floats.find((x) => x.id === gid);
  return f ? setActive(ws, gid, f.active) : ws;
}

export const DEFAULT_FLOAT: [number, number] = [420, 360];

export function addFloat(
  ws: Workspace,
  panes: PaneId[],
  active: PaneId | undefined,
  x: number,
  y: number,
  size: [number, number] = DEFAULT_FLOAT,
): Workspace {
  const f: Float = {
    t: 'g',
    id: `f${ws.next}`,
    panes: panes.slice(),
    active: active ?? panes[0],
    x,
    y,
    w: size[0],
    h: size[1],
  };
  return { ...ws, floats: ws.floats.concat([f]), next: ws.next + 1 };
}

export function moveFloat(ws: Workspace, gid: string, x: number, y: number): Workspace {
  return { ...ws, floats: ws.floats.map((f) => (f.id === gid ? { ...f, x, y } : f)) };
}

export function resizeFloat(ws: Workspace, gid: string, w: number, h: number): Workspace {
  return { ...ws, floats: ws.floats.map((f) => (f.id === gid ? { ...f, w, h } : f)) };
}

/** Where a dragged tab would land. */
export interface Hint {
  gid: string;
  zone: 'center' | Side;
  float: boolean;
  /** Tab index when dropping onto a tab strip. */
  idx: number | null;
}

/** Remembers which tree group a pane left, so "dock" can send a floating window home. */
export type Home = Record<PaneId, string>;

function lift(ws: Workspace, panes: PaneId[], home: Home): { ws: Workspace; home: Home } {
  let next = ws;
  const h = { ...home };
  for (const p of panes) {
    const loc = locate(next, p);
    if (loc && loc.kind === 'tree') h[p] = loc.gid;
    next = removePane(next, p);
  }
  return { ws: next, home: h };
}

export function move(
  ws: Workspace,
  panes: PaneId[],
  active: PaneId,
  hint: Hint,
  srcGid: string,
  home: Home = {},
): { ws: Workspace; home: Home } {
  const pool: Group[] = hint.float ? ws.floats : treeGroups(ws.tree);
  const target = pool.find((g) => g.id === hint.gid);
  if (!target) return { ws, home };
  if (hint.gid === srcGid && target.panes.length === panes.length) return { ws, home };
  let idx = hint.idx;
  if (idx != null)
    idx -= target.panes.filter((p, i) => panes.includes(p) && i < (idx as number)).length;
  const lifted = lift(ws, panes, home);
  const out =
    hint.zone === 'center'
      ? addTab(lifted.ws, hint.gid, panes, idx, active)
      : splitGroup(lifted.ws, hint.gid, hint.zone, panes, active);
  return { ws: out, home: lifted.home };
}

export function floatOut(
  ws: Workspace,
  panes: PaneId[],
  active: PaneId,
  x: number,
  y: number,
  home: Home = {},
  size?: [number, number],
): { ws: Workspace; home: Home } {
  const lifted = lift(ws, panes, home);
  return { ws: addFloat(lifted.ws, panes, active, x, y, size), home: lifted.home };
}

/** Send panes back to the group they last sat in (else the first group). */
export function dockHome(
  ws: Workspace,
  panes: PaneId[],
  active: PaneId,
  home: Home,
  fallbackPane?: PaneId,
): Workspace {
  const groups = treeGroups(ws.tree);
  let g = groups.find((x) => x.id === home[panes[0]]);
  if (!g && fallbackPane) g = groups.find((x) => x.panes.includes(fallbackPane));
  if (!g) g = groups[0];
  if (!g) return { ...ws, tree: { ...group('g-main', panes), active } };
  return addTab(ws, g.id, panes, null, active);
}

/** Open a pane: focus it where it is, else add it to `gid` (or the first group). */
export function showPane(ws: Workspace, pane: PaneId, gid?: string): Workspace {
  const loc = locate(ws, pane);
  if (loc) return setActive(ws, loc.gid, pane);
  const groups = treeGroups(ws.tree);
  const g = groups.find((x) => x.id === gid) ?? groups[0];
  if (!g) return { ...ws, tree: group('g-main', [pane]) };
  return addTab(ws, g.id, [pane], null, pane);
}

// ---- persistence ------------------------------------------------------------------------------

export const STORAGE_VERSION = 1;

export function serialize(ws: Workspace): string {
  return JSON.stringify({ v: STORAGE_VERSION, ws });
}

/** A saved layout, or null if it is missing, from another version, or not the right shape. */
export function parse(text: string | null, known: readonly PaneId[]): Workspace | null {
  if (!text) return null;
  try {
    const raw = JSON.parse(text);
    if (!raw || raw.v !== STORAGE_VERSION || !raw.ws) return null;
    const ws = raw.ws as Workspace;
    if (typeof ws.next !== 'number' || !Array.isArray(ws.floats)) return null;
    const ok = (n: unknown): n is Node => {
      const x = n as Node;
      if (!x || typeof x !== 'object') return false;
      if (x.t === 'g') return Array.isArray(x.panes) && x.panes.every((p) => known.includes(p));
      if (x.t === 's')
        return (
          (x.dir === 'row' || x.dir === 'col') &&
          Array.isArray(x.kids) &&
          x.kids.length === x.ratios?.length &&
          x.kids.every(ok)
        );
      return false;
    };
    if (ws.tree !== null && !ok(ws.tree)) return null;
    if (!ws.floats.every((f) => ok(f) && typeof f.x === 'number' && typeof f.w === 'number'))
      return null;
    return ws;
  } catch {
    return null;
  }
}
