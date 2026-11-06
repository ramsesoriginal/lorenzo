// Step one: layout(model, view, theme) -> Scene. Pure: the same input is the same bytes, in the
// screen pixels of the viewport, with numbers rounded to two decimals (ADR 0407).

import { ENGINES } from './engines';
import { cos, round2, sin, TAU } from './math';
import { defaultTheme } from './themes/default';
import {
  type Dash,
  DEFAULT_VIEW,
  type GraphEdge,
  type GraphModel,
  type GraphView,
  type LayoutGraph,
  type Point,
  type Primitive,
  type Scene,
  type Theme,
} from './types';

/** A Scene holds at most this many nodes and edges; above that the app asks for a smaller
 * selection (*proposed default*, ADR 0407). */
export const LIMITS = { nodes: 500, edges: 2_000 } as const;

const MARGIN = 48;
const MAX_UNIT = 90;
const DASHES: Record<GraphEdge['status'], Dash> = {
  direct: null,
  derived: '7 5',
  uncertain: '1.5 5',
};

/** Plain code-point order: `localeCompare` differs between engines, and the bytes must not. */
function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function byName(model: GraphModel) {
  return [...model.nodes].sort((x, y) => cmp(x.name, y.name) || cmp(x.id, y.id));
}

/** The graph an engine sees: node ids in name order, undirected pairs, pins and the focus. */
export function layoutGraph(model: GraphModel, view: GraphView): LayoutGraph {
  const ordered = byName(model);
  const ids = ordered.map((n) => n.id);
  const index = new Map(ids.map((id, i) => [id, i] as const));
  const seen = new Set<string>();
  const pairs: [number, number][] = [];
  const degree = ids.map(() => 0);
  for (const edge of model.edges) {
    const a = index.get(edge.a);
    const b = index.get(edge.b);
    if (a === undefined || b === undefined || a === b) continue;
    degree[a] = (degree[a] as number) + 1;
    degree[b] = (degree[b] as number) + 1;
    const key = a < b ? `${a}:${b}` : `${b}:${a}`;
    if (!seen.has(key)) {
      seen.add(key);
      pairs.push(a < b ? [a, b] : [b, a]);
    }
  }
  pairs.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  const pins = new Map<number, Point>();
  for (const [id, point] of Object.entries(view.positions ?? {})) {
    const at = index.get(id);
    if (at !== undefined) pins.set(at, { x: point.x, y: point.y });
  }
  let focus = view.focus ? index.get(view.focus) : undefined;
  if (focus === undefined) {
    focus = 0;
    degree.forEach((d, i) => {
      if (d > (degree[focus as number] as number)) focus = i;
    });
  }
  return { ids, pairs, pins, focus };
}

/** Where the engine puts every node, in abstract units, hand placements kept. */
export function place(model: GraphModel, view: GraphView): Map<string, Point> {
  const graph = layoutGraph(model, view);
  const positions = ENGINES[view.layout](graph, view.seed);
  const out = new Map<string, Point>();
  graph.ids.forEach((id, i) => {
    const pinned = graph.pins.get(i);
    const at = pinned ?? positions[i] ?? { x: 0, y: 0 };
    if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) {
      throw new RangeError(`The ${view.layout} layout produced a position that is not a number`);
    }
    out.set(id, at);
  });
  return out;
}

function hull(points: Point[]): Point[] {
  const sorted = [...points].sort((p, q) => p.x - q.x || p.y - q.y);
  if (sorted.length < 3) return sorted;
  const cross = (o: Point, a: Point, b: Point) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower: Point[] = [];
  for (const p of sorted) {
    while (
      lower.length >= 2 &&
      cross(lower[lower.length - 2] as Point, lower[lower.length - 1] as Point, p) <= 0
    )
      lower.pop();
    lower.push(p);
  }
  const upper: Point[] = [];
  for (const p of [...sorted].reverse()) {
    while (
      upper.length >= 2 &&
      cross(upper[upper.length - 2] as Point, upper[upper.length - 1] as Point, p) <= 0
    )
      upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

function cut(text: string, chars: number): string {
  const letters = [...text];
  return letters.length <= chars ? text : `${letters.slice(0, chars - 1).join('')}…`;
}

export function layout(
  model: GraphModel,
  view: GraphView = DEFAULT_VIEW,
  theme: Theme = defaultTheme,
): Scene {
  if (model.nodes.length > LIMITS.nodes || model.edges.length > LIMITS.edges) {
    throw new RangeError(
      `A graph holds at most ${LIMITS.nodes} nodes and ${LIMITS.edges} edges: choose fewer`,
    );
  }
  const world = place(model, view);
  const nodes = byName(model);
  // Fit the world into the viewport, then zoom and pan.
  const xs = [...world.values()].map((p) => p.x);
  const ys = [...world.values()].map((p) => p.y);
  const x0 = Math.min(0, ...xs);
  const x1 = Math.max(0, ...xs);
  const y0 = Math.min(0, ...ys);
  const y1 = Math.max(0, ...ys);
  const spanX = Math.max(x1 - x0, 1e-6);
  const spanY = Math.max(y1 - y0, 1e-6);
  const fit = Math.min(
    MAX_UNIT,
    (view.width - 2 * MARGIN) / spanX,
    (view.height - 2 * MARGIN) / spanY,
  );
  const scale = Math.max(1, fit) * view.zoom;
  const ox = view.width / 2 - ((x0 + x1) / 2) * scale + view.pan.x;
  const oy = view.height / 2 - ((y0 + y1) / 2) * scale + view.pan.y;
  const screen = new Map<string, Point>();
  for (const [id, p] of world) screen.set(id, { x: ox + p.x * scale, y: oy + p.y * scale });

  const primitives: Primitive[] = [];
  const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  const grow = (x: number, y: number, pad = 0) => {
    box.x0 = Math.min(box.x0, x - pad);
    box.y0 = Math.min(box.y0, y - pad);
    box.x1 = Math.max(box.x1, x + pad);
    box.y1 = Math.max(box.y1, y + pad);
  };
  const selected = view.selection ?? null;
  const nodeById = new Map(model.nodes.map((n) => [n.id, n] as const));

  // Hulls of the groups, behind everything.
  if (view.hulls) {
    for (const group of model.groups ?? []) {
      const members = group.members.map((id) => screen.get(id)).filter((p): p is Point => !!p);
      if (members.length < 2) continue;
      const ring: Point[] = [];
      for (const m of members) {
        for (let k = 0; k < 8; k += 1) {
          const angle = (TAU * k) / 8;
          ring.push({
            x: m.x + theme.hullPadding * cos(angle),
            y: m.y + theme.hullPadding * sin(angle),
          });
        }
      }
      const outline = hull(ring);
      const d = `${outline.map((p, i) => `${i === 0 ? 'M' : 'L'}${round2(p.x)} ${round2(p.y)}`).join(' ')} Z`;
      for (const p of outline) grow(p.x, p.y);
      primitives.push({
        kind: 'path',
        id: `hull:${group.id}`,
        role: 'hull',
        d,
        dash: null,
        width: 1,
        className: theme.classes.hull,
        selected: false,
        dim: false,
        source: { kind: 'group', id: group.id },
      });
      const top = outline.reduce((a, b) => (b.y < a.y ? b : a));
      primitives.push({
        kind: 'text',
        id: `hull-label:${group.id}`,
        role: 'hull-label',
        x: round2(top.x),
        y: round2(top.y - 6),
        text: cut(group.name, theme.labelChars),
        className: theme.classes.label,
        source: { kind: 'group', id: group.id },
      });
    }
  }

  // Edges: parallel ones of a pair fan out, each ends at the edge of its nodes.
  const pairKey = (e: GraphEdge) => (e.a < e.b ? `${e.a}|${e.b}` : `${e.b}|${e.a}`);
  const family = new Map<string, GraphEdge[]>();
  for (const edge of [...model.edges].sort((p, q) => cmp(p.id, q.id))) {
    if (!screen.has(edge.a) || !screen.has(edge.b) || edge.a === edge.b) continue;
    const list = family.get(pairKey(edge)) ?? [];
    list.push(edge);
    family.set(pairKey(edge), list);
  }
  const arrows: Primitive[] = [];
  const labels: Primitive[] = [];
  for (const edge of [...model.edges].sort((p, q) => cmp(p.id, q.id))) {
    const from = screen.get(edge.a);
    const to = screen.get(edge.b);
    if (!from || !to || edge.a === edge.b) continue;
    const siblings = family.get(pairKey(edge)) ?? [edge];
    const slot = siblings.indexOf(edge) - (siblings.length - 1) / 2;
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.sqrt(dx * dx + dy * dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const sign = edge.a < edge.b ? 1 : -1;
    const bend = slot * theme.parallelGap * 2 * sign;
    const cx = (from.x + to.x) / 2 - uy * bend;
    const cy = (from.y + to.y) / 2 + ux * bend;
    // Along the first and last part of the curve, outside the node discs.
    const startX =
      from.x +
      ((cx - from.x) / (Math.sqrt((cx - from.x) ** 2 + (cy - from.y) ** 2) || 1)) *
        theme.nodeRadius;
    const startY =
      from.y +
      ((cy - from.y) / (Math.sqrt((cx - from.x) ** 2 + (cy - from.y) ** 2) || 1)) *
        theme.nodeRadius;
    const tipLen = Math.sqrt((to.x - cx) ** 2 + (to.y - cy) ** 2) || 1;
    const tx = (to.x - cx) / tipLen;
    const ty = (to.y - cy) / tipLen;
    const endX = to.x - tx * (theme.nodeRadius + 2);
    const endY = to.y - ty * (theme.nodeRadius + 2);
    const straight = Math.abs(bend) < 0.01;
    const d = straight
      ? `M${round2(startX)} ${round2(startY)} L${round2(endX)} ${round2(endY)}`
      : `M${round2(startX)} ${round2(startY)} Q${round2(cx)} ${round2(cy)} ${round2(endX)} ${round2(endY)}`;
    let width = theme.edgeWidth;
    if (edge.value !== undefined && edge.scale) {
      const [low, high] = edge.scale;
      const t = high > low ? Math.min(1, Math.max(0, (edge.value - low) / (high - low))) : 0;
      width = theme.edgeWidth + (theme.edgeWidthMax - theme.edgeWidth) * t;
    }
    const isSelected = selected?.kind === 'edge' && selected.id === edge.id;
    grow(startX, startY);
    grow(endX, endY);
    grow(cx, cy);
    primitives.push({
      kind: 'path',
      id: `edge:${edge.id}`,
      role: 'edge',
      d,
      dash: DASHES[edge.status],
      width: round2(width),
      className: theme.classes.edge,
      selected: isSelected,
      dim: false,
      source: { kind: 'edge', id: edge.id },
    });
    if (edge.directed) {
      const s = theme.arrowSize;
      const px = -ty;
      const py = tx;
      const bx = endX - tx * s;
      const by = endY - ty * s;
      arrows.push({
        kind: 'path',
        id: `arrow:${edge.id}`,
        role: 'arrow',
        d: `M${round2(endX)} ${round2(endY)} L${round2(bx + px * s * 0.45)} ${round2(by + py * s * 0.45)} L${round2(bx - px * s * 0.45)} ${round2(by - py * s * 0.45)} Z`,
        dash: null,
        width: 1,
        className: theme.classes.arrow,
        selected: isSelected,
        dim: false,
        source: { kind: 'edge', id: edge.id },
      });
    }
    if (view.labels && edge.label) {
      const mx = straight ? (startX + endX) / 2 : 0.25 * startX + 0.5 * cx + 0.25 * endX;
      const my = straight ? (startY + endY) / 2 : 0.25 * startY + 0.5 * cy + 0.25 * endY;
      labels.push({
        kind: 'text',
        id: `edge-label:${edge.id}`,
        role: 'edge-label',
        x: round2(mx),
        y: round2(my - 5),
        text: cut(edge.label, theme.labelChars + 8),
        className: theme.classes.label,
        source: { kind: 'edge', id: edge.id },
      });
    }
  }
  primitives.push(...arrows, ...labels);

  // Nodes last, so they are on top and the first to be hit.
  for (const node of nodes) {
    const at = screen.get(node.id) as Point;
    grow(at.x, at.y, theme.nodeRadius + 4);
    const source = { kind: 'node', id: node.id } as const;
    primitives.push({
      kind: 'circle',
      id: `node:${node.id}`,
      role: 'node',
      name: node.name,
      cx: round2(at.x),
      cy: round2(at.y),
      r: theme.nodeRadius,
      className: theme.classes.node,
      selected: selected?.kind === 'node' && selected.id === node.id,
      dim: !!nodeById.get(node.id)?.dim,
      source,
    });
    if (node.icon) {
      primitives.push({
        kind: 'icon',
        id: `icon:${node.id}`,
        role: 'node-icon',
        x: round2(at.x - theme.iconSize / 2),
        y: round2(at.y - theme.iconSize / 2),
        size: theme.iconSize,
        key: node.icon,
        source,
      });
    }
    if (view.labels) {
      primitives.push({
        kind: 'text',
        id: `label:${node.id}`,
        role: 'node-label',
        x: round2(at.x),
        y: round2(at.y + theme.nodeRadius + theme.fontSize + 2),
        text: cut(node.name, theme.labelChars),
        className: theme.classes.label,
        source,
      });
    }
  }
  if (!Number.isFinite(box.x0))
    Object.assign(box, { x0: 0, y0: 0, x1: view.width, y1: view.height });
  return {
    width: view.width,
    height: view.height,
    frame: { scale: round2(scale), ox: round2(ox), oy: round2(oy) },
    bounds: { x0: round2(box.x0), y0: round2(box.y0), x1: round2(box.x1), y1: round2(box.y1) },
    primitives,
  };
}
