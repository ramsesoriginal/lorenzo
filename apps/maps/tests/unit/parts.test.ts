import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import type { Editable } from '../../src/lib/geometry-edit';
import {
  hasParts,
  isHeightLines,
  movedPart,
  partAt,
  partNames,
  partShape,
  refAfterRemoval,
  withoutPart,
  withPart,
  withParts,
} from '../../src/lib/parts-edit';
import { splinePart } from '../../src/lib/spline';

const FORMAT = 'lorenzo.geometry/1';

const outline: [number, number][] = [
  [100, 100],
  [400, 100],
  [400, 400],
  [100, 400],
];
const hole: [number, number][] = [
  [200, 200],
  [300, 200],
  [300, 300],
  [200, 300],
];
const several: Geometry = {
  format: FORMAT,
  parts: [
    { shape: 'polygon', rings: [outline, hole] },
    {
      shape: 'polyline',
      pts: [
        [500, 500],
        [700, 500],
      ],
      value: 40,
      unit: 'm',
    },
    { shape: 'point', at: [800, 200] },
    { shape: 'circle', at: [800, 600], r: 50 },
    splinePart(
      [
        [500, 100],
        [600, 150],
        [700, 100],
      ],
      0.5,
    ),
    {
      shape: 'bezier',
      start: [0, 700],
      segs: [
        [
          [10, 650],
          [90, 790],
          [100, 700],
        ],
      ],
    },
    {
      shape: 'polyline',
      pts: [
        [500, 600],
        [700, 600],
      ],
    },
  ],
};

describe('the parts of a placement (ADR 0474)', () => {
  it('is edited part by part when it has several parts, or one area with holes', () => {
    expect(hasParts(several)).toBe(true);
    expect(
      hasParts({ format: FORMAT, parts: [{ shape: 'polygon', rings: [outline, hole] }] }),
    ).toBe(true);
    expect(hasParts({ format: FORMAT, parts: [{ shape: 'polygon', rings: [outline] }] })).toBe(
      false,
    );
    expect(hasParts({ format: FORMAT, parts: [{ shape: 'point', at: [1, 2] }] })).toBe(false);
  });

  it('names every part and hole, each numbered among its own kind', () => {
    expect(partNames(several).map((p) => [p.name, p.ref.part, p.ref.ring, p.editable])).toEqual([
      ['Area 1', 0, 0, true],
      ['Hole 1 of Area 1', 0, 1, true],
      ['Height line 1, 40 m', 1, 0, true],
      ['Point 1', 2, 0, true],
      ['Circle 1', 3, 0, true],
      ['Curve 1', 4, 0, true],
      // A curve that is no spline is listed and kept, and not edited by its points.
      ['Curve 2', 5, 0, false],
      ['Line 1', 6, 0, true],
    ]);
  });

  it('gives a part as the shape the editor changes, a ring of an area as an outline', () => {
    expect(partShape(several, { part: 0, ring: 0 })).toEqual({ kind: 'area', pts: outline });
    expect(partShape(several, { part: 0, ring: 1 })).toEqual({ kind: 'area', pts: hole });
    expect(partShape(several, { part: 1, ring: 0 })).toMatchObject({
      kind: 'line',
      value: 40,
      unit: 'm',
    });
    expect(partShape(several, { part: 4, ring: 0 })).toMatchObject({
      kind: 'spline',
      tension: 0.5,
    });
    expect(partShape(several, { part: 5, ring: 0 })).toBeNull();
    expect(partShape(several, { part: 0, ring: 2 })).toBeNull();
    expect(partShape(several, { part: 1, ring: 1 })).toBeNull();
    expect(partShape(several, { part: 99, ring: 0 })).toBeNull();
  });

  it('writes a changed part back and leaves every other part as it was', () => {
    const line = partShape(several, { part: 1, ring: 0 }) as Extract<Editable, { kind: 'line' }>;
    const next = withPart(
      several,
      { part: 1, ring: 0 },
      {
        ...line,
        pts: [
          [500.004, 520],
          [700, 500],
        ],
      },
    );

    expect(next.parts[1]).toEqual({
      shape: 'polyline',
      pts: [
        [500, 520],
        [700, 500],
      ],
      value: 40,
      unit: 'm',
    });
    expect(next.parts.filter((_, i) => i !== 1)).toEqual(several.parts.filter((_, i) => i !== 1));
  });

  it('writes one ring of an area back and keeps its other rings and its value', () => {
    const valued: Geometry = {
      format: FORMAT,
      parts: [{ shape: 'polygon', rings: [outline, hole], value: 3, unit: 'storeys' }],
    };
    const ring = partShape(valued, { part: 0, ring: 1 }) as Extract<Editable, { kind: 'area' }>;
    const moved = withPart(
      valued,
      { part: 0, ring: 1 },
      { ...ring, pts: [[210, 200], ...hole.slice(1)] },
    );

    expect(moved.parts[0]).toMatchObject({
      rings: [outline, [[210, 200], ...hole.slice(1)]],
      value: 3,
      unit: 'storeys',
    });
    // The outline carries the area's value: changing it keeps the value and the hole.
    const outer = partShape(valued, { part: 0, ring: 0 }) as Extract<Editable, { kind: 'area' }>;

    expect(outer).toMatchObject({ value: 3, unit: 'storeys' });
    expect(withPart(valued, { part: 0, ring: 0 }, outer)).toEqual(valued);
  });

  it('moves a whole part: an area with its holes, a curve with its controls', () => {
    const moved = movedPart(several, 0, 10, -5);

    expect(moved.parts[0]).toEqual({
      shape: 'polygon',
      rings: [outline.map(([x, y]) => [x + 10, y - 5]), hole.map(([x, y]) => [x + 10, y - 5])],
    });
    expect(moved.parts.slice(1)).toEqual(several.parts.slice(1));
    expect(movedPart(several, 2, 1, 1).parts[2]).toEqual({ shape: 'point', at: [801, 201] });
    expect(movedPart(several, 3, 1, 1).parts[3]).toEqual({
      shape: 'circle',
      at: [801, 601],
      r: 50,
    });
    expect(movedPart(several, 5, 100, 0).parts[5]).toMatchObject({
      start: [100, 700],
      segs: [
        [
          [110, 650],
          [190, 790],
          [200, 700],
        ],
      ],
    });
  });

  it('removes a part or a hole, and never the last part', () => {
    expect(withoutPart(several, { part: 2, ring: 0 })?.parts).toHaveLength(
      several.parts.length - 1,
    );
    expect(withoutPart(several, { part: 0, ring: 1 })?.parts[0]).toEqual({
      shape: 'polygon',
      rings: [outline],
    });
    // The outline removed takes the area with it.
    expect(withoutPart(several, { part: 0, ring: 0 })?.parts[0]).toEqual(several.parts[1]);

    const one: Geometry = { format: FORMAT, parts: [{ shape: 'polygon', rings: [outline, hole] }] };

    expect(withoutPart(one, { part: 0, ring: 0 })).toBeNull();
    expect(withoutPart(one, { part: 0, ring: 1 })?.parts[0]).toEqual({
      shape: 'polygon',
      rings: [outline],
    });
  });

  it('keeps the chosen part chosen when another is removed, by its new place', () => {
    expect(refAfterRemoval(null, { part: 0, ring: 0 })).toBeNull();
    expect(refAfterRemoval({ part: 3, ring: 0 }, { part: 1, ring: 0 })).toEqual({
      part: 2,
      ring: 0,
    });
    expect(refAfterRemoval({ part: 1, ring: 0 }, { part: 3, ring: 0 })).toEqual({
      part: 1,
      ring: 0,
    });
    expect(refAfterRemoval({ part: 1, ring: 0 }, { part: 1, ring: 0 })).toBeNull();
    // A hole removed: the area and an earlier hole stay, a later hole moves up, the hole itself goes.
    expect(refAfterRemoval({ part: 0, ring: 0 }, { part: 0, ring: 1 })).toEqual({
      part: 0,
      ring: 0,
    });
    expect(refAfterRemoval({ part: 0, ring: 2 }, { part: 0, ring: 1 })).toEqual({
      part: 0,
      ring: 1,
    });
    expect(refAfterRemoval({ part: 0, ring: 1 }, { part: 0, ring: 1 })).toBeNull();
    expect(refAfterRemoval({ part: 0, ring: 1 }, { part: 0, ring: 0 })).toBeNull();
    expect(refAfterRemoval({ part: 2, ring: 1 }, { part: 0, ring: 1 })).toEqual({
      part: 2,
      ring: 1,
    });
  });

  it('finds the part under a point: a line or a pin before the area it lies on', () => {
    expect(partAt(several, [150, 150], 5)).toEqual({ part: 0, ring: 0 });
    // In the hole there is no area.
    expect(partAt(several, [250, 250], 5)).toBeNull();
    expect(partAt(several, [600, 503], 5)).toEqual({ part: 1, ring: 0 });
    expect(partAt(several, [600, 520], 5)).toBeNull();
    expect(partAt(several, [802, 198], 5)).toEqual({ part: 2, ring: 0 });
    expect(partAt(several, [820, 620], 5)).toEqual({ part: 3, ring: 0 });
    // A spline is found along its curve, which goes through its middle point.
    expect(partAt(several, [600, 152], 5)).toEqual({ part: 4, ring: 0 });
    expect(partAt(several, [0, 0], 5)).toBeNull();

    const over: Geometry = {
      format: FORMAT,
      parts: [
        { shape: 'polygon', rings: [outline] },
        {
          shape: 'polyline',
          pts: [
            [100, 250],
            [400, 250],
          ],
        },
      ],
    };

    expect(partAt(over, [250, 252], 5)).toEqual({ part: 1, ring: 0 });
    expect(partAt(over, [250, 300], 5)).toEqual({ part: 0, ring: 0 });
  });

  it('knows a set of height lines, and adds a line to one', () => {
    const lines: Geometry = {
      format: FORMAT,
      parts: [several.parts[1] as Geometry['parts'][number]],
    };

    expect(isHeightLines(lines)).toBe(true);
    expect(isHeightLines(several)).toBe(false);
    expect(isHeightLines({ format: FORMAT, parts: [] })).toBe(false);
    expect(
      isHeightLines({ format: FORMAT, parts: [several.parts[6] as Geometry['parts'][number]] }),
    ).toBe(false);

    const more = withParts(lines, {
      format: FORMAT,
      parts: [
        {
          shape: 'polyline',
          pts: [
            [0, 0],
            [1, 1],
          ],
          value: 60,
          unit: 'm',
        },
      ],
    });

    expect(more.parts.map((part) => part.value)).toEqual([40, 60]);
    expect(isHeightLines(more)).toBe(true);
    expect(partNames(more).map((p) => p.name)).toEqual([
      'Height line 1, 40 m',
      'Height line 2, 60 m',
    ]);
  });
});
