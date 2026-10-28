import type { Geometry } from '@lorenzo/map-renderer';
import { defaultTheme, plainTheme } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import {
  boundsOf,
  contains,
  type Editable,
  editableOf,
  handlesOf,
  insertVertex,
  moveHandle,
  placesInside,
  removeVertex,
  round2,
  toGeometry,
  translate,
} from '../../src/lib/geometry-edit';
import { type Change, createHistory, writeFor } from '../../src/lib/history';
import { chosenTheme } from '../../src/lib/look';

const square: Editable = {
  kind: 'area',
  pts: [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100],
  ],
};

describe('geometry', () => {
  it('writes each shape as the document the API takes, to two decimals', () => {
    expect(toGeometry({ kind: 'point', at: [1.2345, 2] })).toEqual({
      format: 'lorenzo.geometry/1',
      parts: [{ shape: 'point', at: [1.23, 2] }],
    });
    expect(toGeometry({ kind: 'circle', at: [5, 5], r: 3.999 }).parts[0]).toEqual({
      shape: 'circle',
      at: [5, 5],
      r: 4,
    });
    expect(
      toGeometry({
        kind: 'line',
        pts: [
          [0, 0],
          [1, 1],
        ],
      }).parts[0],
    ).toMatchObject({
      shape: 'polyline',
    });
    expect(toGeometry(square).parts[0]).toMatchObject({
      shape: 'polygon',
      rings: [square.kind === 'area' ? square.pts : []],
    });
    expect(round2(0.005)).toBe(0.01);
  });

  it('reads back a stored geometry the editor can change, and refuses the rest', () => {
    for (const shape of [
      { kind: 'point', at: [3, 4] } as Editable,
      { kind: 'circle', at: [3, 4], r: 2 } as Editable,
      {
        kind: 'line',
        pts: [
          [0, 0],
          [4, 4],
        ],
      } as Editable,
      square,
    ]) {
      expect(editableOf(toGeometry(shape))).toEqual(shape);
    }
    const two = {
      format: 'x',
      parts: [
        { shape: 'point', at: [0, 0] },
        { shape: 'point', at: [1, 1] },
      ],
    };
    const curve = { format: 'x', parts: [{ shape: 'bezier', start: [0, 0], segs: [] }] };
    const hole = {
      format: 'x',
      parts: [
        {
          shape: 'polygon',
          rings: [
            square.kind === 'area' ? square.pts : [],
            [
              [10, 10],
              [20, 10],
              [20, 20],
            ],
          ],
        },
      ],
    };

    for (const g of [two, curve, hole, { format: 'x', parts: [] }]) {
      expect(editableOf(g as unknown as Geometry)).toBeNull();
    }
  });

  it('moves handles: a vertex, a centre and the radius, and nothing for an unknown one', () => {
    expect(handlesOf(square).map((h) => h.id)).toEqual(['v0', 'v1', 'v2', 'v3']);
    expect(moveHandle(square, 'v2', [90.126, 80])).toMatchObject({
      pts: [
        [0, 0],
        [100, 0],
        [90.13, 80],
        [0, 100],
      ],
    });
    const circle: Editable = { kind: 'circle', at: [10, 10], r: 5 };

    expect(handlesOf(circle)).toEqual([
      { id: 'c', at: [10, 10] },
      { id: 'r', at: [15, 10] },
    ]);
    expect(moveHandle(circle, 'c', [20, 20])).toEqual({ kind: 'circle', at: [20, 20], r: 5 });
    expect(moveHandle(circle, 'r', [10, 30])).toEqual({ kind: 'circle', at: [10, 10], r: 20 });
    expect(moveHandle(circle, 'r', [10, 10])).toMatchObject({ r: 0.01 });
    expect(moveHandle(square, 'nope', [1, 1])).toBe(square);
    expect(moveHandle(square, 'v9', [1, 1])).toBe(square);
    expect(moveHandle({ kind: 'point', at: [0, 0] }, 'p', [2, 3])).toEqual({
      kind: 'point',
      at: [2, 3],
    });
  });

  it('translates a whole shape', () => {
    expect(translate(square, 10, -5)).toMatchObject({
      pts: [
        [10, -5],
        [110, -5],
        [110, 95],
        [10, 95],
      ],
    });
    expect(translate({ kind: 'circle', at: [1, 1], r: 2 }, 1, 1)).toEqual({
      kind: 'circle',
      at: [2, 2],
      r: 2,
    });
  });

  it('adds a point after a vertex and removes one, never below a line of two or an area of three', () => {
    const more = insertVertex(square, 0);

    expect(more.kind === 'area' && more.pts).toEqual([
      [0, 0],
      [50, 0],
      [100, 0],
      [100, 100],
      [0, 100],
    ]);
    const wrap = insertVertex(square, 3);

    expect(wrap.kind === 'area' && wrap.pts[4]).toEqual([0, 50]);
    const line: Editable = {
      kind: 'line',
      pts: [
        [0, 0],
        [10, 0],
      ],
    };
    const longer = insertVertex(line, 1);

    expect(longer.kind === 'line' && longer.pts.length).toBe(3);
    expect(removeVertex(square, 1)).toMatchObject({
      pts: [
        [0, 0],
        [100, 100],
        [0, 100],
      ],
    });
    expect(
      removeVertex(
        {
          kind: 'area',
          pts: [
            [0, 0],
            [1, 0],
            [1, 1],
          ],
        },
        0,
      ),
    ).toBeNull();
    expect(removeVertex(line, 0)).toBeNull();
    expect(removeVertex({ kind: 'point', at: [0, 0] }, 0)).toBeNull();
  });

  it('finds the box of a shape and what is inside an area or a circle', () => {
    expect(boundsOf(square)).toEqual([0, 0, 100, 100]);
    expect(boundsOf({ kind: 'circle', at: [10, 10], r: 5 })).toEqual([5, 5, 15, 15]);
    expect(contains(square, [50, 50])).toBe(true);
    expect(contains(square, [150, 50])).toBe(false);
    expect(contains({ kind: 'circle', at: [0, 0], r: 5 }, [3, 3])).toBe(true);
    expect(
      contains(
        {
          kind: 'line',
          pts: [
            [0, 0],
            [1, 1],
          ],
        },
        [0, 0],
      ),
    ).toBe(false);
  });

  it('lays n places out inside a shape, a concave one included', () => {
    const places = placesInside(square, 7);

    expect(places).toHaveLength(7);
    expect(new Set(places.map((p) => p.join())).size).toBe(7);
    expect(places.every((p) => contains(square, p))).toBe(true);
    const ell: Editable = {
      kind: 'area',
      pts: [
        [0, 0],
        [100, 0],
        [100, 20],
        [20, 20],
        [20, 100],
        [0, 100],
      ],
    };
    const inL = placesInside(ell, 10);

    expect(inL).toHaveLength(10);
    expect(inL.every((p) => contains(ell, p))).toBe(true);
    expect(placesInside({ kind: 'circle', at: [0, 0], r: 10 }, 3)).toHaveLength(3);
    expect(placesInside({ kind: 'point', at: [0, 0] }, 3)).toEqual([]);
    expect(placesInside(square, 0)).toEqual([]);
  });
});

const state = (z: number) => ({ geometry: { z }, role: null, style: null, z });

describe('history', () => {
  it('undoes and redoes steps in order, and a new step forgets what could be redone', () => {
    const history = createHistory();
    const a: Change[] = [{ entry: 'a', before: null, after: state(1) }];
    const b: Change[] = [{ entry: 'a', before: state(1), after: state(2) }];

    history.record(a);
    history.record(b);
    expect([history.canUndo(), history.canRedo()]).toEqual([true, false]);
    expect(history.undo()).toBe(b);
    expect(history.undo()).toBe(a);
    expect(history.undo()).toBeNull();
    expect(history.redo()).toBe(a);
    history.record([{ entry: 'z', before: null, after: state(9) }]);
    expect(history.canRedo()).toBe(false);
    expect(history.redo()).toBeNull();
  });

  it('keeps the last fifty and ignores an empty step', () => {
    const history = createHistory(50);

    for (let i = 0; i < 60; i += 1)
      history.record([{ entry: String(i), before: null, after: state(i) }]);
    history.record([]);
    let count = 0;

    while (history.undo()) count += 1;

    expect(count).toBe(50);
    history.clear();
    expect(history.canUndo()).toBe(false);
  });

  it('turns a change into the write that undoes or redoes it', () => {
    const drawn: Change = { entry: 'a', before: null, after: state(1) };
    const moved: Change = { entry: 'a', before: state(1), after: state(2) };

    expect(writeFor(drawn, 'undo')).toEqual({ remove: 'a' });
    expect(writeFor(drawn, 'redo')).toEqual({ put: { entry_id: 'a', ...state(1) } });
    expect(writeFor(moved, 'undo')).toEqual({ put: { entry_id: 'a', ...state(1) } });
  });
});

describe('the look', () => {
  it("is the viewer's choice, then the Map's name, then the default", () => {
    expect(chosenTheme('plain', 'default')).toBe(plainTheme);
    expect(chosenTheme('default', 'plain')).toBe(defaultTheme);
    expect(chosenTheme('map', 'plain')).toBe(plainTheme);
    expect(chosenTheme('map', null)).toBe(defaultTheme);
    expect(chosenTheme('map', 'tube')).toBe(defaultTheme);
  });
});
