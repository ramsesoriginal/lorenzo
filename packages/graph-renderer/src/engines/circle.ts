import { cos, sin, TAU } from '../math';
import type { Engine, LayoutGraph, Positions } from '../types';

/** Nodes on a circle in the order given, the first at the top, clockwise. */
export function onCircle(count: number, radiusScale = 1.4): Positions {
  const radius = Math.max(1.5, (count / TAU) * radiusScale);
  const out: Positions = [];
  for (let i = 0; i < count; i += 1) {
    const angle = (TAU * i) / Math.max(1, count) - TAU / 4;
    out.push({ x: radius * cos(angle), y: radius * sin(angle) });
  }
  return out;
}

export const circle: Engine = (graph: LayoutGraph) => onCircle(graph.ids.length);
