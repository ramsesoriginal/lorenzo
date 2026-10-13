// Where would a dragged tab land? Pure: the caller supplies the pointer, the size of the
// workspace, and a way to find the tab slot under the pointer (the only part that needs a DOM).

import { type Float, type Hint, layout, type Rect, type Workspace } from './model';

export interface Drag {
  /** A tab dragged from the tree, or a whole floating window by its bar. */
  kind: 'tab' | 'float';
  /** The group the drag started in. */
  gid: string;
}

export interface HitResult {
  hint: Hint;
  /** The target group's rect in workspace pixels, for the drop overlay. */
  rect: Rect;
  /** x of the insertion mark when dropping on a tab strip, in workspace pixels. */
  markX: number | null;
}

export type TabSlot = (gid: string, clientX: number) => { idx: number; x: number };

const EDGE_TAB = 0.25;
const EDGE_FLOAT = 0.18;

export function hitTest(
  ws: Workspace,
  px: number,
  py: number,
  size: { w: number; h: number },
  drag: Drag,
  barH: (g: { panes: string[] }) => number,
  clientX: number,
  tabSlot: TabSlot,
): HitResult | null {
  const isFloat = drag.kind === 'float';
  const floats: Float[] = ws.floats.slice().reverse();
  for (const f of floats) {
    if (isFloat && f.id === drag.gid) continue;
    if (px < f.x || px > f.x + f.w || py < f.y || py > f.y + f.h) continue;
    const inBar = py - f.y <= barH(f);
    if (!inBar && isFloat) return null;
    const t = inBar ? tabSlot(f.id, clientX) : null;
    return {
      hint: { gid: f.id, zone: 'center', float: true, idx: t ? t.idx : null },
      rect: { x: f.x, y: f.y, w: f.w, h: f.h },
      markX: t ? t.x : null,
    };
  }
  const L = layout(ws.tree);
  for (const q of L.groups) {
    const x0 = q.x * size.w;
    const y0 = q.y * size.h;
    const gw = q.w * size.w;
    const gh = q.h * size.h;
    if (px < x0 || px > x0 + gw || py < y0 || py > y0 + gh) continue;
    // A lone tab dropped on its own group is a no-op.
    if (!isFloat && q.g.id === drag.gid && q.g.panes.length === 1) return null;
    const inBar = py - y0 <= barH(q.g);
    let zone: Hint['zone'] = 'center';
    if (!inBar) {
      const fx = (px - x0) / gw;
      const fy = (py - y0) / gh;
      const m = Math.min(fx, 1 - fx, fy, 1 - fy);
      if (m < (isFloat ? EDGE_FLOAT : EDGE_TAB))
        zone = m === fx ? 'left' : m === 1 - fx ? 'right' : m === fy ? 'top' : 'bottom';
      else if (isFloat) return null;
    }
    const t = inBar && zone === 'center' ? tabSlot(q.g.id, clientX) : null;
    return {
      hint: { gid: q.g.id, zone, float: false, idx: t ? t.idx : null },
      rect: { x: x0, y: y0, w: gw, h: gh },
      markX: t ? t.x : null,
    };
  }
  return null;
}
