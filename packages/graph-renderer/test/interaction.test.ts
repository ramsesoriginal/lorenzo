import { describe, expect, it } from 'vitest';
import {
  centreOn,
  clampZoom,
  hitTest,
  layout,
  moveAlongEdges,
  neighbours,
  panBy,
  samplePath,
  toWorld,
  ZOOM,
  zoomAt,
} from '../src';
import { model, view } from './fixtures';

describe('hitTest', () => {
  const scene = layout(model, view({ layout: 'circle' }));
  const disc = (id: string) => {
    const found = scene.primitives.find((p) => p.id === `node:${id}`);
    if (found?.kind !== 'circle') throw new Error('missing node');
    return found;
  };

  it('finds a node under the point, and none far from everything', () => {
    const mara = disc('mara');
    expect(hitTest(scene, { x: mara.cx + 3, y: mara.cy - 2 })).toEqual({
      kind: 'node',
      id: 'mara',
    });
    expect(hitTest(scene, { x: -50, y: -50 })).toBeNull();
  });

  it('finds an edge near its line, preferring a node on top of it', () => {
    const e1 = scene.primitives.find((p) => p.id === 'edge:e1');
    if (e1?.kind !== 'path') throw new Error('missing edge');
    const points = samplePath(e1.d);
    const first = points[0] as { x: number; y: number };
    const last = points[points.length - 1] as { x: number; y: number };
    const mid = { x: (first.x + last.x) / 2, y: (first.y + last.y) / 2 };
    expect(hitTest(scene, mid)).toEqual({ kind: 'edge', id: 'e1' });
    const tomas = disc('tomas');
    expect(hitTest(scene, { x: tomas.cx, y: tomas.cy })?.kind).toBe('node');
  });

  it('samples a curve and a line', () => {
    expect(samplePath('M0 0 L10 0')).toEqual([
      { x: 0, y: 0 },
      { x: 10, y: 0 },
    ]);
    const curve = samplePath('M0 0 Q5 10 10 0', 4);
    expect(curve).toHaveLength(5);
    expect(curve[2]).toEqual({ x: 5, y: 5 });
  });
});

describe('the view reducers', () => {
  it('pans by pixels and keeps the zoom inside its limits', () => {
    expect(panBy(view(), 5, -3).pan).toEqual({ x: 5, y: -3 });
    expect(clampZoom(100)).toBe(ZOOM.max);
    expect(clampZoom(0.001)).toBe(ZOOM.min);
  });

  it('zooms about a point so what is under it stays under it', () => {
    const start = view({ zoom: 1 });
    const before = layout(model, start);
    const mara = before.primitives.find((p) => p.id === 'node:mara');
    if (mara?.kind !== 'circle') throw new Error('missing node');
    const next = zoomAt(start, 1.5, { x: mara.cx, y: mara.cy });
    const after = layout(model, next).primitives.find((p) => p.id === 'node:mara');
    if (after?.kind !== 'circle') throw new Error('missing node');
    expect(Math.abs(after.cx - mara.cx)).toBeLessThan(0.1);
    expect(Math.abs(after.cy - mara.cy)).toBeLessThan(0.1);
    expect(next.zoom).toBe(1.5);
  });

  it('centres on a node', () => {
    const start = view();
    const scene = layout(model, start);
    const next = centreOn(scene, start, 'dren');
    const after = layout(model, next).primitives.find((p) => p.id === 'node:dren');
    if (after?.kind !== 'circle') throw new Error('missing node');
    expect(Math.abs(after.cx - start.width / 2)).toBeLessThan(0.1);
    expect(Math.abs(after.cy - start.height / 2)).toBeLessThan(0.1);
  });

  it('takes a screen point back to layout units', () => {
    const scene = layout(model, view({ layout: 'manual', positions: { mara: { x: 2, y: 3 } } }));
    const mara = scene.primitives.find((p) => p.id === 'node:mara');
    if (mara?.kind !== 'circle') throw new Error('missing node');
    const world = toWorld(scene, { x: mara.cx, y: mara.cy });
    expect(world.x).toBeCloseTo(2, 1);
    expect(world.y).toBeCloseTo(3, 1);
  });
});

describe('moving along edges', () => {
  it('lists neighbours in order and moves only to one that lies that way', () => {
    expect(neighbours(model, 'wren')).toEqual(['dren', 'mara', 'tomas']);
    expect(neighbours(model, 'loner')).toEqual([]);
    const scene = layout(model, view({ layout: 'circle' }));
    const reached = (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'] as const)
      .map((key) => moveAlongEdges(scene, model, 'wren', key))
      .filter((id): id is string => id !== null);
    for (const id of reached) expect(neighbours(model, 'wren')).toContain(id);
    expect(moveAlongEdges(scene, model, 'loner', 'ArrowUp')).toBeNull();
    expect(moveAlongEdges(scene, model, 'ghost', 'ArrowUp')).toBeNull();
  });
});
