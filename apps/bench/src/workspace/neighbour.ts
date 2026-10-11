// Which group is next to another, in a direction (ADR 0257): for moving a tab with the keyboard.

import type { Side } from './model';

export interface Box {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

const EPS = 1e-6;

/**
 * The group beside `id` on `side`: among those that start where it ends and share some of its
 * extent, the one nearest, ties to the one that overlaps most. Null when it is at that edge.
 */
export function neighbourGroup(boxes: readonly Box[], id: string, side: Side): string | null {
  const me = boxes.find((b) => b.id === id);
  if (!me) return null;
  const horizontal = side === 'left' || side === 'right';
  let best: { id: string; gap: number; overlap: number } | null = null;
  for (const b of boxes) {
    if (b.id === id) continue;
    const gap = horizontal
      ? side === 'right'
        ? b.x - (me.x + me.w)
        : me.x - (b.x + b.w)
      : side === 'bottom'
        ? b.y - (me.y + me.h)
        : me.y - (b.y + b.h);
    if (gap < -EPS) continue;
    const overlap = horizontal
      ? Math.min(me.y + me.h, b.y + b.h) - Math.max(me.y, b.y)
      : Math.min(me.x + me.w, b.x + b.w) - Math.max(me.x, b.x);
    if (overlap <= EPS) continue;
    if (
      !best ||
      gap < best.gap - EPS ||
      (Math.abs(gap - best.gap) <= EPS && overlap > best.overlap)
    )
      best = { id: b.id, gap, overlap };
  }
  return best?.id ?? null;
}
