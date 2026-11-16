import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { cos, createRandom, LAYOUT_NAMES, round2, sin } from '../src';

describe('deterministic numbers', () => {
  it('computes sine and cosine without Math.sin to 1e-10', () => {
    for (let i = -400; i <= 400; i += 1) {
      const x = i * 0.0731;
      expect(Math.abs(sin(x) - Math.sin(x))).toBeLessThan(1e-10);
      expect(Math.abs(cos(x) - Math.cos(x))).toBeLessThan(1e-10);
    }
  });

  it('draws the same integers from a seed and different ones from another', () => {
    const a = createRandom(42);
    const b = createRandom(42);
    const first = Array.from({ length: 5 }, () => a());
    expect(first).toEqual(Array.from({ length: 5 }, () => b()));
    expect(first).toMatchInlineSnapshot(`
      [
        0.6011037519201636,
        0.44829055899754167,
        0.8524657934904099,
        0.6697340414393693,
        0.17481389874592423,
      ]
    `);
    expect(createRandom(43)()).not.toBe(first[0]);
  });

  it('rounds to two decimals and never writes -0', () => {
    expect(round2(1.005)).toBe(1);
    expect(round2(2.346)).toBe(2.35);
    expect(Object.is(round2(-0.001), 0)).toBe(true);
  });

  it('never calls the approximated functions in the layout code', () => {
    for (const file of ['circle', 'forceatlas2', 'radial', 'stress']) {
      const source = readFileSync(new URL(`../src/engines/${file}.ts`, import.meta.url), 'utf8');
      expect(source).not.toMatch(/Math\.(sin|cos|exp|pow|atan|tan|random)/);
    }
    expect(readFileSync(new URL('../src/layout.ts', import.meta.url), 'utf8')).not.toMatch(
      /Math\.(sin|cos|exp|atan|tan|random)/,
    );
  });
});

describe('the closed list of layouts', () => {
  it('is the file the API checks against', () => {
    const file = JSON.parse(readFileSync(new URL('../src/layouts.json', import.meta.url), 'utf8'));
    expect(file).toEqual([...LAYOUT_NAMES]);
  });
});
