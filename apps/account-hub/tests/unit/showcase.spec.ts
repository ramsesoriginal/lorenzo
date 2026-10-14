import { describe, expect, it } from 'vitest';
import {
  actionLabel,
  added,
  canAdd,
  candidates,
  FEATURED_NONE,
  featuredCount,
  LOOK_EXPLANATION,
  LOOK_HEADING,
  limitLine,
  moved,
  RELEASE_NOTE,
  refusal,
  removedAt,
} from '../../src/lib/showcase';
import { PREVIEW_CHOICES } from '../../src/lib/visibility';

const entries = (...names: string[]) => names.map((name) => ({ id: name.toLowerCase(), name }));

describe('moving the featured entries', () => {
  it('moves one place up or down, and not past either end', () => {
    const list = entries('A', 'B', 'C');

    expect(moved(list, 1, -1).map((e) => e.name)).toEqual(['B', 'A', 'C']);
    expect(moved(list, 1, 1).map((e) => e.name)).toEqual(['A', 'C', 'B']);
    expect(moved(list, 0, -1).map((e) => e.name)).toEqual(['A', 'B', 'C']);
    expect(moved(list, 2, 1).map((e) => e.name)).toEqual(['A', 'B', 'C']);
    expect(moved(list, 5, 1).map((e) => e.name)).toEqual(['A', 'B', 'C']);
  });

  it('does not change the list it was given', () => {
    const list = entries('A', 'B');

    moved(list, 0, 1);
    removedAt(list, 0);
    expect(list.map((e) => e.name)).toEqual(['A', 'B']);
  });

  it('removes the one at an index', () => {
    expect(removedAt(entries('A', 'B', 'C'), 1).map((e) => e.name)).toEqual(['A', 'C']);
    expect(removedAt(entries('A'), 3).map((e) => e.name)).toEqual(['A']);
  });
});

describe('adding one', () => {
  it('adds at the end', () => {
    expect(added(entries('A'), { id: 'b', name: 'B' }, 12).map((e) => e.name)).toEqual(['A', 'B']);
  });

  it('adds none twice', () => {
    expect(added(entries('A'), { id: 'a', name: 'A' }, 12)).toHaveLength(1);
  });

  it('adds none past the limit', () => {
    const full = Array.from({ length: 12 }, (_, i) => ({ id: String(i), name: `E${i}` }));

    expect(added(full, { id: 'x', name: 'X' }, 12)).toHaveLength(12);
    expect(canAdd(full, 12)).toBe(false);
    expect(canAdd(full.slice(1), 12)).toBe(true);
  });

  it('offers what a search found except what is featured', () => {
    expect(
      candidates(entries('Owlbear', 'Owl', 'Bear'), entries('Owl')).map((e) => e.name),
    ).toEqual(['Owlbear', 'Bear']);
  });
});

describe('the words', () => {
  it('say how many may be featured', () => {
    expect(limitLine(12)).toBe('You can feature up to 12 entries.');
    expect(featuredCount(3, 12)).toBe('3 of 12 entries featured');
    expect(actionLabel('Move up', 'Owlbear')).toBe('Move up: Owlbear');
  });

  it('say that a visitor reads the latest release', () => {
    expect(RELEASE_NOTE).toBe(
      'Visitors read the latest release, so an entry you add is shown from the next release.',
    );
  });

  it('use the words of the dialog that makes a repository public', () => {
    expect(PREVIEW_CHOICES.map((choice) => choice.value)).toEqual(['showcase', 'public', 'off']);
    expect(LOOK_HEADING).toBe('What people can look at');
  });

  it('never say tenant, grant or subscription', () => {
    const said = [LOOK_HEADING, LOOK_EXPLANATION, RELEASE_NOTE, FEATURED_NONE].join(' ');

    expect(said).not.toMatch(/tenant|grant|subscription|stable|frozen/i);
  });

  it('explain a refusal in words, and only that one', () => {
    expect(refusal('showcase-invalid')).toMatch(/Nothing was changed/);
    expect(refusal('something-else')).toBeNull();
    expect(refusal(undefined)).toBeNull();
  });
});
