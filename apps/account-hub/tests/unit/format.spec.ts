import { describe, expect, it } from 'vitest';
import { localesToText, textOrNull, textToLocales } from '../../src/lib/format';

describe('textToLocales', () => {
  it('splits, trims, and drops empty entries', () => {
    expect(textToLocales('en, de ,  , fr')).toEqual(['en', 'de', 'fr']);
  });

  it('returns an empty array for blank input', () => {
    expect(textToLocales('   ')).toEqual([]);
  });
});

describe('localesToText', () => {
  it('joins with a comma and space', () => {
    expect(localesToText(['en', 'de'])).toBe('en, de');
  });

  it('round-trips through textToLocales', () => {
    const locales = ['en', 'de', 'fr'];
    expect(textToLocales(localesToText(locales))).toEqual(locales);
  });
});

describe('textOrNull', () => {
  it('returns null for blank/whitespace-only input', () => {
    expect(textOrNull('')).toBeNull();
    expect(textOrNull('   ')).toBeNull();
  });

  it('returns the value unchanged otherwise', () => {
    expect(textOrNull('Cael')).toBe('Cael');
  });
});
