import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { MAX_SPLIT, splitPieces } from '../../src/lib/split-entries';

const FORMAT = 'lorenzo.geometry/1';
const square = (x: number) => ({
  shape: 'polygon' as const,
  rings: [
    [
      [x, 0],
      [x + 10, 0],
      [x + 10, 10],
      [x, 10],
    ] as [number, number][],
  ],
});

describe('splitting a drawing into entries (ADR 0482)', () => {
  it('makes one piece of each part, named from the base and numbered in drawing order', () => {
    const geometry: Geometry = { format: FORMAT, parts: [square(0), square(20), square(40)] };
    const split = splitPieces(geometry, '  Field ');

    expect(split).toEqual({
      ok: true,
      pieces: [
        { name: 'Field 1', geometry: { format: FORMAT, parts: [square(0)] } },
        { name: 'Field 2', geometry: { format: FORMAT, parts: [square(20)] } },
        { name: 'Field 3', geometry: { format: FORMAT, parts: [square(40)] } },
      ],
    });
  });

  it('keeps what a part carries, such as the height of a height line', () => {
    const lines: Geometry = {
      format: FORMAT,
      parts: [
        {
          shape: 'polyline',
          pts: [
            [0, 0],
            [10, 0],
          ],
          value: 100,
          unit: 'm',
        },
        {
          shape: 'polyline',
          pts: [
            [0, 5],
            [10, 5],
          ],
          value: 200,
          unit: 'm',
        },
      ],
    };
    const split = splitPieces(lines, 'Contour');
    if (!split.ok) throw new Error(split.why);

    expect(split.pieces.map((piece) => piece.geometry.parts[0])).toEqual(lines.parts);
  });

  it('refuses one part, more parts than one batch writes, and no name, each with its words', () => {
    expect(splitPieces({ format: FORMAT, parts: [square(0)] }, 'A')).toEqual({
      ok: false,
      why: 'A drawing of one part is one entry already.',
    });
    const many: Geometry = {
      format: FORMAT,
      parts: Array.from({ length: MAX_SPLIT + 1 }, (_, i) => square(i * 20)),
    };
    expect(MAX_SPLIT).toBe(100);
    expect(splitPieces(many, 'A')).toEqual({
      ok: false,
      why: 'This drawing has 101 parts, and one split makes at most 100 entries. Remove some parts first.',
    });
    expect(splitPieces({ format: FORMAT, parts: [square(0), square(20)] }, '   ')).toEqual({
      ok: false,
      why: 'Give a name for the new places to be numbered from.',
    });
    // At the limit it is still one batch.
    const hundred: Geometry = {
      format: FORMAT,
      parts: Array.from({ length: MAX_SPLIT }, (_, i) => square(i * 20)),
    };
    expect(splitPieces(hundred, 'A')).toMatchObject({ ok: true });
  });
});
