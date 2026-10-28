import { describe, expect, it } from 'vitest';
import {
  positionWords,
  projectionFrom,
  readProjectionChoice,
  TURN_STEP,
  turned,
  writeProjectionChoice,
} from '../../src/lib/sphere-words';

describe('the words of a position', () => {
  it('name the hemispheres and show one decimal', () => {
    expect(positionWords([12.54, 40.06])).toBe('40.1° N, 12.5° E');
    expect(positionWords([-73.9857, -33.8688])).toBe('33.9° S, 74.0° W');
    expect(positionWords([0, 0])).toBe('0.0° N, 0.0° E');
  });

  it('do not say south or west of nothing', () => {
    expect(positionWords([-0.04, -0.04])).toBe('0.0° N, 0.0° E');
    expect(positionWords([180, 90])).toBe('90.0° N, 180.0° E');
    expect(positionWords([-180, -90])).toBe('90.0° S, 180.0° W');
  });
});

describe('turning a globe', () => {
  it('moves by a step, wraps round in longitude and stops at the poles', () => {
    expect(TURN_STEP).toBe(15);
    expect(turned([0, 0], 'east')).toEqual([15, 0]);
    expect(turned([0, 0], 'west')).toEqual([-15, 0]);
    expect(turned([175, 0], 'east')).toEqual([-170, 0]);
    expect(turned([-175, 0], 'west')).toEqual([170, 0]);
    expect(turned([0, 80], 'north')).toEqual([0, 90]);
    expect(turned([0, -80], 'south')).toEqual([0, -90]);
    expect(turned([20, 30], 'north')).toEqual([20, 45]);
  });
});

describe('the projection a reader chooses', () => {
  it('is read from a Map view and from this browser, and only when it is one we know', () => {
    expect(projectionFrom({ projection: { kind: 'mercator' } })).toEqual({ kind: 'mercator' });
    expect(projectionFrom(null)).toBeUndefined();
    expect(projectionFrom({})).toBeUndefined();

    const store = new Map<string, string>();

    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    };

    expect(readProjectionChoice('m1')).toBeUndefined();
    writeProjectionChoice('m1', { kind: 'orthographic', centre: [10, 20] });
    expect(readProjectionChoice('m1')).toEqual({ kind: 'orthographic', centre: [10, 20] });
    expect(readProjectionChoice('m2')).toBeUndefined();
    store.set('lorenzo:maps:projection:m3', '{"kind":"mollweide"}');
    expect(readProjectionChoice('m3')).toBeUndefined();
    writeProjectionChoice('m1', undefined);
    expect(readProjectionChoice('m1')).toBeUndefined();
  });
});
