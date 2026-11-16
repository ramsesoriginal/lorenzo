import { describe, expect, it } from 'vitest';
import { type GraphModel, layout, layoutGraph, place, rankOf, themeFor } from '../src';
import { view } from './fixtures';

/** A family: grandparents above parents above children, partners side by side. */
const family: GraphModel = {
  nodes: [
    { id: 'gp1', name: 'Tomas' },
    { id: 'gp2', name: 'Edda' },
    { id: 'p1', name: 'Mara' },
    { id: 'p2', name: 'Joren' },
    { id: 'c1', name: 'Wren' },
    { id: 'c2', name: 'Dren' },
    { id: 'friend', name: 'Anselm' },
  ],
  edges: [
    { id: 'e1', a: 'gp1', b: 'p1', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e2', a: 'gp2', b: 'p1', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e3', a: 'gp1', b: 'gp2', directed: false, label: 'married to', status: 'direct' },
    { id: 'e4', a: 'p1', b: 'p2', directed: false, label: 'married to', status: 'direct' },
    { id: 'e5', a: 'p1', b: 'c1', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e6', a: 'p2', b: 'c1', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e7', a: 'p1', b: 'c2', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e8', a: 'c2', b: 'friend', directed: false, label: 'friend of', status: 'uncertain' },
  ],
};

describe('the layered layout', () => {
  const at = place(family, view({ layout: 'layered' }));
  const y = (id: string) => (at.get(id) as { y: number }).y;

  it('puts a parent above a child, and partners on one row', () => {
    expect(y('gp1')).toBeLessThan(y('p1'));
    expect(y('p1')).toBeLessThan(y('c1'));
    expect(y('gp1')).toBe(y('gp2'));
    expect(y('p1')).toBe(y('p2'));
    expect(y('c1')).toBe(y('c2'));
  });

  it('keeps the nodes of a row apart and finite', () => {
    const rows = new Map<number, number[]>();
    for (const id of family.nodes.map((n) => n.id)) {
      const p = at.get(id) as { x: number; y: number };
      expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
      rows.set(p.y, [...(rows.get(p.y) ?? []), p.x]);
    }
    for (const xs of rows.values()) expect(new Set(xs).size).toBe(xs.length);
  });

  it('is the same bytes twice and matches the golden scene in the family theme', () => {
    const scene = () => layout(family, view({ layout: 'layered' }), themeFor('family'));
    expect(JSON.stringify(scene())).toBe(JSON.stringify(scene()));
    expect(scene()).toMatchSnapshot();
  });

  it('cuts a cycle the same way every time, and ranks a graph with no one-way ties by steps', () => {
    const loop: GraphModel = {
      nodes: [
        { id: 'a', name: 'A' },
        { id: 'b', name: 'B' },
        { id: 'c', name: 'C' },
      ],
      edges: [
        { id: '1', a: 'a', b: 'b', directed: true, status: 'direct' },
        { id: '2', a: 'b', b: 'c', directed: true, status: 'direct' },
        { id: '3', a: 'c', b: 'a', directed: true, status: 'direct' },
      ],
    };
    expect(rankOf(layoutGraph(loop, view()))).toEqual([0, 1, 2]);
    const plain = place(
      { nodes: family.nodes, edges: family.edges.map((e) => ({ ...e, directed: false })) },
      view({ layout: 'layered', focus: 'p1' }),
    );
    expect((plain.get('p1') as { y: number }).y).toBe(0);
    expect((plain.get('gp1') as { y: number }).y).toBeGreaterThan(0);
  });
});

describe('the family theme', () => {
  it('draws a tie with right angles, and the default theme keeps straight lines', () => {
    const scene = layout(family, view({ layout: 'layered' }), themeFor('family'));
    const parentOf = scene.primitives.find((p) => p.id === 'edge:e5');
    if (parentOf?.kind !== 'path') throw new Error('missing edge');
    expect(parentOf.d.match(/L/g)?.length).toBe(3);
    const plain = layout(family, view({ layout: 'layered' }));
    const straight = plain.primitives.find((p) => p.id === 'edge:e5');
    expect(straight?.kind === 'path' && straight.d.match(/L/g)?.length).toBe(1);
  });

  it('is chosen by the viewer, then the hint, then the default', () => {
    expect(themeFor('family', 'default').name).toBe('family');
    expect(themeFor(null, 'family').name).toBe('family');
    expect(themeFor('nonsense', undefined).name).toBe('default');
  });
});
