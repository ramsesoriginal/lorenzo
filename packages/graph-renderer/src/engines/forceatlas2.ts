import { createRandom } from '../math';
import type { Engine, LayoutGraph, Point, Positions } from '../types';
import { onCircle } from './circle';

const ITERATIONS = 150;
const REPULSION = 2;
const GRAVITY = 1;
const SPEED = 0.1;

/** ForceAtlas2 without Barnes-Hut (a Scene holds at most 500 nodes): degree-weighted repulsion,
 * linear attraction along edges, gravity to the centre, a fixed number of rounds and a small
 * seeded jitter so symmetric starts come apart the same way every time. */
export const forceatlas2: Engine = (graph: LayoutGraph, seed: number) => {
  const count = graph.ids.length;
  if (count < 2) return onCircle(count);
  const random = createRandom(seed);
  const pos: Positions = onCircle(count).map((p) => ({
    x: p.x + (random() - 0.5) * 0.2,
    y: p.y + (random() - 0.5) * 0.2,
  }));
  for (const [index, point] of graph.pins) pos[index] = { ...point };
  const degree = new Array<number>(count).fill(0);
  for (const [a, b] of graph.pairs) {
    degree[a] = (degree[a] as number) + 1;
    degree[b] = (degree[b] as number) + 1;
  }
  for (let round = 0; round < ITERATIONS; round += 1) {
    const fx = new Array<number>(count).fill(0);
    const fy = new Array<number>(count).fill(0);
    for (let i = 0; i < count; i += 1) {
      const a = pos[i] as Point;
      for (let j = i + 1; j < count; j += 1) {
        const b = pos[j] as Point;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 1e-6;
        const push = (REPULSION * ((degree[i] as number) + 1) * ((degree[j] as number) + 1)) / d2;
        fx[i] = (fx[i] as number) + dx * push;
        fy[i] = (fy[i] as number) + dy * push;
        fx[j] = (fx[j] as number) - dx * push;
        fy[j] = (fy[j] as number) - dy * push;
      }
    }
    for (const [i, j] of graph.pairs) {
      const a = pos[i] as Point;
      const b = pos[j] as Point;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      fx[i] = (fx[i] as number) + dx;
      fy[i] = (fy[i] as number) + dy;
      fx[j] = (fx[j] as number) - dx;
      fy[j] = (fy[j] as number) - dy;
    }
    // Cooling keeps the last rounds small, so the layout comes to rest.
    const step = SPEED * (1 - round / ITERATIONS);
    for (let i = 0; i < count; i += 1) {
      if (graph.pins.has(i)) continue;
      const here = pos[i] as Point;
      const pull = GRAVITY * ((degree[i] as number) + 1);
      const gx = (fx[i] as number) - here.x * pull * 0.1;
      const gy = (fy[i] as number) - here.y * pull * 0.1;
      const length = Math.sqrt(gx * gx + gy * gy);
      // A step is never longer than a unit, so one hub cannot throw a node out of the picture.
      const scale = length * step > 1 ? 1 / (step * length) : 1;
      pos[i] = { x: here.x + gx * step * scale, y: here.y + gy * step * scale };
    }
  }
  return pos;
};
