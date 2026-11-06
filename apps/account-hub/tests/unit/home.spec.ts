import { describe, expect, it } from 'vitest';
import { needsYou, pageTitle, parseRecent, rememberPage, splitTables } from '../../src/lib/home';

const card = (name: string, roles: string[]) => ({ name, roles }) as never;

describe('splitTables', () => {
  it('puts a seat in where you play, and any other role in what you run', () => {
    const { play, run } = splitTables([
      card('Zorro', ['Player']),
      card('Heist', ['GM']),
      card('Both', ['Player', 'Organizer']),
    ]);

    expect(play.map((c) => c.name)).toEqual(['Zorro', 'Both']);
    expect(run.map((c) => c.name)).toEqual(['Heist', 'Both']);
  });
});

describe('needsYou', () => {
  const href = (slug: string) => `/studio/?repository=${slug}`;

  it('is a task for each repository still a draft, and none for the rest', () => {
    const tasks = needsYou(
      [
        { name: 'Orla', slug: 'orla', role: 'Owner', status: 'Draft' },
        { name: 'Vale', slug: 'vale', role: 'Author', status: 'Published 2026-10-01' },
        { name: 'Odd', slug: 'odd', role: 'Author', status: null },
      ],
      href,
    );

    expect(tasks).toEqual([
      {
        id: 'draft:orla',
        text: 'Orla is still a draft.',
        action: 'Open it',
        href: '/studio/?repository=orla',
      },
    ]);
  });

  it('is empty on a quiet day', () => {
    expect(needsYou([], href)).toEqual([]);
  });
});

describe('rememberPage', () => {
  it('puts the page just opened first, with no repeats, at most three', () => {
    let recent = rememberPage([], { href: '/a/', title: 'A' });

    recent = rememberPage(recent, { href: '/b/', title: 'B' });
    recent = rememberPage(recent, { href: '/c/', title: 'C' });
    recent = rememberPage(recent, { href: '/a/', title: 'A' });
    recent = rememberPage(recent, { href: '/d/', title: 'D' });

    expect(recent.map((p) => p.href)).toEqual(['/d/', '/a/', '/c/']);
  });
});

describe('parseRecent', () => {
  it('keeps only well-formed local entries and survives rubbish', () => {
    expect(
      parseRecent('[{"href":"/a/","title":"A"},{"href":"https://x","title":"X"},{"title":"?"}]'),
    ).toEqual([{ href: '/a/', title: 'A' }]);
    expect(parseRecent('not json')).toEqual([]);
    expect(parseRecent('{}')).toEqual([]);
    expect(parseRecent(null)).toEqual([]);
  });
});

describe('pageTitle', () => {
  it('drops the product', () => {
    expect(pageTitle('Your profile — Lorenzo')).toBe('Your profile');
    expect(pageTitle('Lorenzo - Account')).toBe('Lorenzo - Account');
  });
});
