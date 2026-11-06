import { describe, expect, it } from 'vitest';
import {
  ENGINES,
  LAYOUT_NAMES,
  LIMITS,
  layout,
  type Primitive,
  place,
  round2,
  type Scene,
} from '../src';
import { model, view } from './fixtures';

const ENGINE_NAMES = ['circle', 'radial', 'stress', 'forceatlas2', 'manual'] as const;

function shapes(scene: Scene, role: Primitive['role']) {
  return scene.primitives.filter((p) => p.role === role);
}

describe('layout', () => {
  it('keeps the closed list of layouts in one place', () => {
    expect([...LAYOUT_NAMES].sort()).toEqual(Object.keys(ENGINES).sort());
  });

  for (const name of ENGINE_NAMES) {
    it(`is the same bytes for the same input: ${name}`, () => {
      const first = JSON.stringify(layout(model, view({ layout: name, seed: 7 })));
      const second = JSON.stringify(layout(model, view({ layout: name, seed: 7 })));
      expect(first).toBe(second);
    });

    it(`puts every node inside the viewport with a finite position: ${name}`, () => {
      const scene = layout(model, view({ layout: name }));
      const nodes = shapes(scene, 'node');
      expect(nodes).toHaveLength(model.nodes.length);
      for (const node of nodes) {
        if (node.kind !== 'circle') continue;
        expect(Number.isFinite(node.cx) && Number.isFinite(node.cy)).toBe(true);
        expect(node.cx).toBeGreaterThanOrEqual(0);
        expect(node.cx).toBeLessThanOrEqual(scene.width);
        expect(node.cy).toBeGreaterThanOrEqual(0);
        expect(node.cy).toBeLessThanOrEqual(scene.height);
      }
    });

    it(`matches the golden scene: ${name}`, () => {
      expect(layout(model, view({ layout: name, seed: 3, hulls: true }))).toMatchSnapshot();
    });
  }

  it('changes with the seed only where a layout starts from noise', () => {
    const at = (name: (typeof ENGINE_NAMES)[number], seed: number) =>
      JSON.stringify(layout(model, view({ layout: name, seed })));
    expect(at('circle', 1)).toBe(at('circle', 2));
    expect(at('forceatlas2', 1)).not.toBe(at('forceatlas2', 2));
  });

  it('keeps a hand placement in every layout and moves the rest around it', () => {
    for (const name of ENGINE_NAMES) {
      const pinned = { mara: { x: 9, y: -4 } };
      const moved = place(model, view({ layout: name, positions: pinned }));
      expect(moved.get('mara')).toEqual({ x: 9, y: -4 });
      const free = place(model, view({ layout: name }));
      expect(moved.get('tomas')).toBeDefined();
      expect(free.get('mara')).not.toEqual({ x: 9, y: -4 });
    }
  });

  it('puts the focus at the centre of the radial layout and the unreachable on the outer ring', () => {
    const at = place(model, view({ layout: 'radial', focus: 'tomas' }));
    expect(at.get('tomas')).toEqual({ x: 0, y: 0 });
    const radius = (id: string) => {
      const p = at.get(id) as { x: number; y: number };
      return Math.sqrt(p.x * p.x + p.y * p.y);
    };
    expect(radius('mara')).toBeLessThan(radius('dren'));
    expect(radius('loner')).toBeGreaterThan(radius('dren'));
  });

  it('draws an edge as its status says: solid, dashed or dotted', () => {
    const edges = shapes(layout(model, view()), 'edge');
    const dash = (id: string) => {
      const found = edges.find((e) => e.id === `edge:${id}`);
      return found?.kind === 'path' ? found.dash : 'missing';
    };
    expect(dash('e1')).toBeNull();
    expect(dash('e3')).toBe('7 5');
    expect(dash('e4')).toBe('1.5 5');
  });

  it('gives an arrowhead to each one-way tie and none to a two-way one', () => {
    const arrows = shapes(layout(model, view()), 'arrow').map((a) => a.source.id);
    expect(arrows.sort()).toEqual(['e1', 'e2', 'e3', 'e5']);
  });

  it('fans parallel edges apart and draws a weighted one heavier', () => {
    const edges = shapes(layout(model, view()), 'edge');
    const path = (id: string) => {
      const found = edges.find((e) => e.id === `edge:${id}`);
      if (found?.kind !== 'path') throw new Error('missing edge');
      return found;
    };
    expect(path('e4').d).not.toBe(path('e5').d);
    expect(path('e4').d).toContain('Q');
    expect(path('e5').width).toBeGreaterThan(path('e4').width);
  });

  it('marks the selection without changing a shape', () => {
    const plain = layout(model, view());
    const chosen = layout(model, view({ selection: { kind: 'node', id: 'wren' } }));
    const strip = (scene: Scene) =>
      JSON.stringify(scene.primitives.map((p) => ({ ...p, selected: undefined })));
    expect(strip(chosen)).toBe(strip(plain));
    const marked = chosen.primitives.filter((p) => 'selected' in p && p.selected);
    expect(marked.map((p) => p.id)).toEqual(['node:wren']);
  });

  it('draws a hull only when asked, and names it', () => {
    expect(shapes(layout(model, view()), 'hull')).toHaveLength(0);
    const scene = layout(model, view({ hulls: true }));
    expect(shapes(scene, 'hull')).toHaveLength(1);
    expect(shapes(scene, 'hull-label').map((p) => (p.kind === 'text' ? p.text : ''))).toEqual([
      'Family',
    ]);
  });

  it('cuts a long name and drops labels when they are off', () => {
    const long = { ...model, nodes: [{ id: 'x', name: 'A'.repeat(60) }, ...model.nodes] };
    const label = layout(long, view()).primitives.find((p) => p.id === 'label:x');
    expect(label?.kind === 'text' && label.text.endsWith('…')).toBe(true);
    const bare = layout(model, view({ labels: false }));
    expect(shapes(bare, 'node-label')).toHaveLength(0);
    expect(shapes(bare, 'edge-label')).toHaveLength(0);
  });

  it('zooms and pans in screen pixels and reports the frame to take a point back', () => {
    const base = layout(model, view());
    const zoomed = layout(model, view({ zoom: 2, pan: { x: 10, y: -5 } }));
    expect(zoomed.frame.scale).toBeCloseTo(base.frame.scale * 2, 1);
    expect(zoomed.frame.ox).not.toBe(base.frame.ox);
  });

  it('refuses a graph beyond the limits and a position that is not a number', () => {
    const many = {
      nodes: Array.from({ length: LIMITS.nodes + 1 }, (_, i) => ({ id: `n${i}`, name: `N${i}` })),
      edges: [],
    };
    expect(() => layout(many, view())).toThrow(RangeError);
    expect(() => round2(Number.NaN)).toThrow(RangeError);
    expect(() => round2(Number.POSITIVE_INFINITY)).toThrow(RangeError);
    expect(() =>
      layout(model, view({ layout: 'manual', positions: { mara: { x: Number.NaN, y: 0 } } })),
    ).toThrow(RangeError);
  });

  it('draws an empty graph and ignores edges to nodes that are not there', () => {
    expect(layout({ nodes: [], edges: [] }, view()).primitives).toEqual([]);
    const dangling = layout(
      {
        nodes: [{ id: 'a', name: 'A' }],
        edges: [{ id: 'z', a: 'a', b: 'ghost', directed: false, status: 'direct' }],
      },
      view(),
    );
    expect(dangling.primitives.filter((p) => p.role === 'edge')).toHaveLength(0);
  });
});
