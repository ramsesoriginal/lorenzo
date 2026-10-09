import { describe, expect, it } from 'vitest';
import { hitTest } from './hit';
import { floatOut, group, type Workspace } from './model';

const ws = (): Workspace => ({
  tree: {
    t: 's',
    id: 's',
    dir: 'row',
    ratios: [0.5, 0.5],
    kids: [group('g1', ['a', 'b']), group('g2', ['c'])],
  },
  floats: [],
  next: 5,
});
const size = { w: 1000, h: 800 };
const bar = () => 30;
const slot = () => ({ idx: 1, x: 120 });
const hit = (w: Workspace, x: number, y: number, kind: 'tab' | 'float' = 'tab', gid = 'g1') =>
  hitTest(w, x, y, size, { kind, gid }, bar, x, slot);

describe('hitTest', () => {
  it('finds a tab slot on a tab strip', () => {
    const h = hit(ws(), 700, 10);
    expect(h?.hint).toEqual({ gid: 'g2', zone: 'center', float: false, idx: 1 });
    expect(h?.markX).toBe(120);
  });
  it('splits near an edge, and lands in the middle otherwise', () => {
    expect(hit(ws(), 510, 400)?.hint.zone).toBe('left');
    expect(hit(ws(), 990, 400)?.hint.zone).toBe('right');
    expect(hit(ws(), 750, 790)?.hint.zone).toBe('bottom');
    expect(hit(ws(), 750, 400)?.hint.zone).toBe('center');
  });
  it('a lone tab over its own group is nothing', () => {
    expect(hit(ws(), 700, 400, 'tab', 'g2')).toBeNull();
  });
  it('a floating window only docks at edges or onto tab strips', () => {
    const w = floatOut(ws(), ['b'], 'b', 600, 300).ws;
    const fid = w.floats[0].id;
    expect(hit(w, 750, 400, 'float', fid)).toBeNull();
    expect(hit(w, 990, 400, 'float', fid)?.hint.zone).toBe('right');
  });
  it('a floating window above the tree is hit first', () => {
    const w = floatOut(ws(), ['b'], 'b', 600, 300).ws;
    const h = hit(w, 650, 310, 'tab', 'g2');
    expect(h?.hint.float).toBe(true);
  });
  it('outside everything is null', () => {
    expect(hit(ws(), 2000, 2000)).toBeNull();
  });
});
