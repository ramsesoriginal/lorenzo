import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { type Editable, editableOf, toGeometry } from '../../src/lib/geometry-edit';
import { heightFromText, heightOf, MAX_VALUE, unitOf } from '../../src/lib/height';

describe('a height and its unit (ADR 0473)', () => {
  it('reads a typed height as the number the API takes', () => {
    expect(heightOf('250')).toBe(250);
    expect(heightOf(' -12.5 ')).toBe(-12.5);
    expect(heightOf('.5')).toBe(0.5);
    expect(heightOf('0')).toBe(0);
    // At most six decimals are kept.
    expect(heightOf('1.23456789')).toBe(1.234568);
    expect(heightOf(String(MAX_VALUE))).toBe(MAX_VALUE);
  });

  it('refuses what is not a number, or is too large', () => {
    for (const bad of ['', ' ', 'high', '1e3', '12m', '--1', '1.2.3', String(MAX_VALUE * 10)]) {
      expect(heightOf(bad), bad).toBeNull();
    }
  });

  it('keeps a unit as the author wrote it, trimmed and composed', () => {
    expect(unitOf(' m ')).toBe('m');
    expect(unitOf('days on foot')).toBe('days on foot');
    expect(unitOf('me\u0301tre')).toBe('m\u00e9tre');
    expect(unitOf('x'.repeat(32))).toHaveLength(32);
  });

  it('refuses a unit that is empty, too long or holds a control character', () => {
    expect(unitOf('')).toBeNull();
    expect(unitOf('   ')).toBeNull();
    expect(unitOf('x'.repeat(33))).toBeNull();
    expect(unitOf('m\u0007')).toBeNull();
    expect(unitOf('m\nm')).toBeNull();
  });

  it('reads back the pair it kept, and nothing from anything else', () => {
    expect(heightFromText(JSON.stringify({ value: 250, unit: 'm' }))).toEqual({
      value: 250,
      unit: 'm',
    });
    for (const bad of [
      null,
      '',
      'not json',
      '[]',
      JSON.stringify({ value: '250', unit: 'm' }),
      JSON.stringify({ value: 250 }),
      JSON.stringify({ value: 250, unit: '' }),
      JSON.stringify({ value: MAX_VALUE * 10, unit: 'm' }),
    ]) {
      expect(heightFromText(bad), String(bad)).toBeNull();
    }
  });

  it('is written with the line, and taken away when both are emptied', () => {
    const line: Editable = {
      kind: 'line',
      pts: [
        [0, 0],
        [10, 0],
      ],
      value: 250,
      unit: 'm',
    };
    const geometry: Geometry = toGeometry(line);

    expect(geometry.parts[0]).toEqual({
      shape: 'polyline',
      pts: [
        [0, 0],
        [10, 0],
      ],
      value: 250,
      unit: 'm',
    });
    expect(editableOf(geometry)).toEqual(line);
    expect(toGeometry({ ...line, value: undefined, unit: undefined }).parts[0]).toEqual({
      shape: 'polyline',
      pts: [
        [0, 0],
        [10, 0],
      ],
    });
  });
});
