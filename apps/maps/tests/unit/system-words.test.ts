import type { System } from '@lorenzo/map-renderer';
import { expect, test } from 'vitest';
import { systemWords } from '../../src/lib/system-words';

const sys = (more: Record<string, unknown>) =>
  ({ extent: [0, 0, 1, 1], ...more }) as unknown as System;

test('a Map says what it is drawn on, in the unit its author chose', () => {
  expect(systemWords(sys({ kind: 'plane', scale: { per_unit: 1, unit: 'paces' } }))).toBe(
    'Free plane · paces',
  );
  expect(systemWords(sys({ kind: 'plane' }))).toBe('Free plane');
  expect(systemWords(sys({ kind: 'outline' }))).toBe('Outline only');
  expect(systemWords(sys({ kind: 'square', measure: { per_cell: 5, unit: 'metres' } }))).toBe(
    'Grid of squares · metres',
  );
  expect(systemWords(sys({ kind: 'rect' }))).toBe('Grid of rectangles');
  expect(
    systemWords(
      sys({ kind: 'hex', orientation: 'pointy', measure: { per_cell: 5, unit: 'metres' } }),
    ),
  ).toBe('Grid of hexes · pointy top · metres');
  expect(systemWords(sys({ kind: 'hex', orientation: 'flat' }))).toBe('Grid of hexes · flat top');
  expect(systemWords(sys({ kind: 'sphere' }))).toBe('Sphere · degrees');
});

test('a kind it does not know is said as it is', () => {
  expect(systemWords(sys({ kind: 'torus' }))).toBe('torus');
});
