// The Ancestry pane: what the selected entry inherits from and what inherits from it, drawn as a
// graph. An entry is opened by clicking it, or with Enter when it has the focus.

import type { Bench } from '../core/bench';
import { ancestryLayout } from './ancestryLayout';

const NS = 'http://www.w3.org/2000/svg';
const svg = <K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string> = {}) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};

export function renderAncestry(
  bench: Bench,
  id: string | null,
  go: (id: string) => void,
): HTMLElement {
  const c = document.createElement('div');
  c.className = 'pane pane-ancestry';
  const layout = id ? ancestryLayout(bench.listing(), id) : null;
  if (!id || !layout || !layout.nodes.length) {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = 'Choose an entry in the explorer.';
    c.append(p);
    return c;
  }
  const g = svg('svg', {
    viewBox: `0 0 ${layout.width} ${layout.height}`,
    width: String(layout.width),
    height: String(layout.height),
    role: 'group',
    'aria-label': 'Ancestry',
  });
  const defs = svg('defs');
  const marker = svg('marker', {
    id: 'ancestry-arrow',
    viewBox: '0 0 10 10',
    refX: '9',
    refY: '5',
    markerWidth: '7',
    markerHeight: '7',
    orient: 'auto-start-reverse',
  });
  marker.append(svg('path', { d: 'M0,0 L10,5 L0,10 z', class: 'ancestry-arrowhead' }));
  defs.append(marker);
  g.append(defs);
  const at = new Map(layout.nodes.map((n) => [n.id, n]));
  for (const edge of layout.edges) {
    const a = at.get(edge.from);
    const b = at.get(edge.to);
    if (!a || !b) continue;
    g.append(
      svg('line', {
        x1: String(a.x + a.w / 2),
        y1: String(a.y),
        x2: String(b.x + b.w / 2),
        y2: String(b.y + b.h),
        class: 'ancestry-edge',
        'marker-end': 'url(#ancestry-arrow)',
      }),
    );
  }
  for (const n of layout.nodes) {
    const node = svg('g', {
      class: n.selected ? 'ancestry-node on' : 'ancestry-node',
      tabindex: '0',
      role: 'button',
      'aria-label': n.selected ? `${n.name} (this entry)` : `Open ${n.name}`,
      'data-ancestry': n.id,
    });
    // A pale pill behind the entry itself; the others are only their names.
    if (n.selected)
      node.append(
        svg('rect', {
          x: String(n.x),
          y: String(n.y),
          width: String(n.w),
          height: String(n.h),
          rx: '6',
        }),
      );
    else
      node.append(
        svg('rect', {
          x: String(n.x),
          y: String(n.y),
          width: String(n.w),
          height: String(n.h),
          rx: '6',
          class: 'hit',
        }),
      );
    const label = svg('text', {
      x: String(n.x + n.w / 2),
      y: String(n.y + n.h / 2 + 4),
      'text-anchor': 'middle',
    });
    label.textContent = n.name;
    node.append(label);
    node.addEventListener('click', () => go(n.id));
    node.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        go(n.id);
      }
    });
    g.append(node);
  }
  c.append(g);
  if (layout.hidden) {
    const more = document.createElement('p');
    more.className = 'muted';
    more.textContent = `${layout.hidden} more under this entry; see Parents and children.`;
    c.append(more);
  }
  return c;
}
