import { describe, expect, it } from 'vitest';
import { agoText, pageTitle, parseRecent, rememberPage } from '../src/index';

describe('Continue, the pages a person had open', () => {
  it('puts the page just opened first, without repeats and at most three', () => {
    const a = { href: '/a/', title: 'A' };
    const b = { href: '/b/', title: 'B' };
    const c = { href: '/c/', title: 'C' };
    const d = { href: '/d/', title: 'D' };

    expect(rememberPage([a, b], c)).toEqual([c, a, b]);
    expect(rememberPage([a, b, c], b)).toEqual([b, a, c]);
    expect(rememberPage([a, b, c], d)).toEqual([d, a, b]);
  });

  it('reads back only what has the right shape', () => {
    expect(parseRecent(null)).toEqual([]);
    expect(parseRecent('not json')).toEqual([]);
    expect(parseRecent('{"href":"/a/"}')).toEqual([]);
    expect(
      parseRecent(
        JSON.stringify([
          { href: '/a/', title: 'A', at: 1 },
          { href: 'https://elsewhere.example/', title: 'X' },
          { href: '/b/' },
        ]),
      ),
    ).toEqual([{ href: '/a/', title: 'A', at: 1 }]);
  });

  it('says how long ago in days, and a title without the product', () => {
    const day = 24 * 60 * 60 * 1000;

    expect(agoText(5 * day, 5 * day - 1000)).toBe('today');
    expect(agoText(5 * day, 4 * day)).toBe('yesterday');
    expect(agoText(5 * day, 2 * day)).toBe('3 days ago');
    expect(pageTitle('Isles calendar — Lorenzo Calendars')).toBe('Isles calendar');
    expect(pageTitle('Your profile - Lorenzo')).toBe('Your profile');
    // No space before the dash, or nothing before it: the title is left as it is.
    expect(pageTitle('Well-Lorenzo — not it')).toBe('Well-Lorenzo — not it');
    expect(pageTitle('— Lorenzo')).toBe('— Lorenzo');
    // A long run of spaces is not slow.
    const started = Date.now();

    pageTitle(`${' '.repeat(100_000)}x`);
    expect(Date.now() - started).toBeLessThan(500);
  });
});
