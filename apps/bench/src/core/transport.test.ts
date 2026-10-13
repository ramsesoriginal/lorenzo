import { describe, expect, it } from 'vitest';
import { decimalText, parseDecimal } from './transport';

describe('decimals', () => {
  it('writes a number as the API reads a float', () => {
    expect(decimalText(3)).toBe('3.0');
    expect(decimalText(1.5)).toBe('1.5');
    expect(decimalText(-2)).toBe('-2.0');
  });

  it('reads what is typed, with a point or a comma', () => {
    expect(parseDecimal('1.5')).toBe(1.5);
    expect(parseDecimal(' 2,25 ')).toBe(2.25);
    expect(parseDecimal('-3')).toBe(-3);
  });

  it('refuses what is not a plain decimal', () => {
    for (const t of ['', 'abc', '1e3', '1.', '.5', '1.2.3', '--1'])
      expect(parseDecimal(t)).toBeNull();
  });
});
