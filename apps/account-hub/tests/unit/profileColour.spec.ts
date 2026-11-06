import { describe, expect, it } from 'vitest';
import { colourProblem, contrast, normalizeHex, SWATCHES } from '../../src/lib/profileColour';

describe('normalizeHex', () => {
  it('takes three or six digits, with or without the #, in any case', () => {
    expect(normalizeHex('#b5471e')).toBe('#B5471E');
    expect(normalizeHex('b5471e')).toBe('#B5471E');
    expect(normalizeHex('#abc')).toBe('#AABBCC');
    expect(normalizeHex('  #123456 ')).toBe('#123456');
  });

  it('refuses anything else', () => {
    for (const bad of ['', '#12', '#12345', '#1234567', '#ggg', 'red']) {
      expect(normalizeHex(bad)).toBeNull();
    }
  });
});

describe('contrast', () => {
  it('is 21 for black on white and 1 for a colour with itself', () => {
    expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
    expect(contrast('#336699', '#336699')).toBeCloseTo(1, 5);
  });
});

describe('colourProblem', () => {
  it('lets every swatch through', () => {
    for (const swatch of SWATCHES) expect(colourProblem(swatch.hex)).toBeNull();
  });

  it('turns away a colour that vanishes on a light page or on a dark one', () => {
    expect(colourProblem('#F0F0F0')).toMatch(/hard to see/);
    expect(colourProblem('#101820')).toMatch(/hard to see/);
  });

  it('says what a colour is when it is not one', () => {
    expect(colourProblem('blue')).toMatch(/six characters/);
  });
});
