import { describe, expect, it } from 'vitest';
import {
  openRequired,
  READINESS_HEADING,
  READINESS_NOTE,
  readinessOf,
  showsReadiness,
} from '../../src/lib/readiness';
import type { FlipCheckOut } from '../../src/lib/types';

const READY = { has_summary: true, built_on_not_public: [], built_on_behind: [] };

describe('what a private repository lacks before it can be public', () => {
  it('says the heading and that it only tells', () => {
    expect(READINESS_HEADING).toBe('Before this can be public');
    expect(READINESS_NOTE).toContain('only tells you what is missing');
  });

  it('is all done for a repository with a summary, a cover and nothing in the way', () => {
    const items = readinessOf(READY, true);

    expect(items.map((item) => item.done)).toEqual([true, true, true]);
    expect(items.every((item) => item.link === null)).toBe(true);
    expect(openRequired(items)).toBe(0);
  });

  it('asks for a summary, which the flip needs, and links to the field', () => {
    const [summary] = readinessOf({ ...READY, has_summary: false }, true);

    expect(summary).toMatchObject({ need: 'required', done: false });
    expect(summary?.text).toContain('needs a summary');
    expect(summary?.link).toEqual({ label: 'Write the summary', target: { kind: 'summary' } });
  });

  it('recommends a cover without requiring it, and links to the control', () => {
    const items = readinessOf(READY, false);
    const cover = items[1];

    expect(cover).toMatchObject({ need: 'recommended', done: false });
    expect(cover?.link).toEqual({ label: 'Add a cover', target: { kind: 'cover' } });
    // Required items are what the flip asks for: a missing cover is not one of them.
    expect(openRequired(items)).toBe(0);
  });

  it('lists each repository it is built on that is not public, as the flip check returned it', () => {
    const items = readinessOf(
      {
        ...READY,
        built_on_not_public: [
          { id: 'u1', name: 'Core rules', owned: true },
          { id: 'u2', name: 'Their rules', owned: false },
        ],
      },
      true,
    );
    const upstream = items.slice(2);

    expect(upstream).toHaveLength(2);
    expect(upstream[0]?.text).toContain('Core rules is private');
    // One the Owner owns links to its own page, to make it public.
    expect(upstream[0]?.link?.target).toEqual({
      kind: 'page',
      href: '/repositories/?repository=u1',
    });
    // One they do not own says whom to ask and links to the tab.
    expect(upstream[1]?.text).toContain('ask its Owner');
    expect(upstream[1]?.link).toEqual({ label: 'Open Built on', target: { kind: 'built-on' } });
    expect(openRequired(items)).toBe(2);
  });

  it('lists a repository it is built on that has a release it has not taken, linking to Built on', () => {
    const items = readinessOf(
      {
        ...READY,
        built_on_behind: [
          {
            repository_id: 'u3',
            name: 'Core rules',
            taken: null,
            current: null,
            readable: true,
          },
        ],
      },
      true,
    );

    expect(items[2]?.text).toContain('Take the new release of Core rules first');
    expect(items[2]?.link?.target).toEqual({ kind: 'built-on' });
  });

  it('counts the open required items, a summary and each blocker', () => {
    expect(
      openRequired(
        readinessOf(
          {
            has_summary: false,
            built_on_not_public: [{ id: 'u1', name: 'A', owned: false }],
            built_on_behind: [],
          },
          false,
        ),
      ),
    ).toBe(2);
  });
});

describe('who sees the list', () => {
  const check = (overrides: Partial<FlipCheckOut>) =>
    ({ available: true, visibility: 'private', ...overrides }) as Pick<
      FlipCheckOut,
      'available' | 'visibility'
    >;

  it('is an Owner of a private repository where it can be made public', () => {
    expect(showsReadiness(check({}), 'owner')).toBe(true);
  });

  it('is nobody else, and not for a public repository or a deployment without them', () => {
    expect(showsReadiness(check({}), 'orga')).toBe(false);
    expect(showsReadiness(check({}), 'author')).toBe(false);
    expect(showsReadiness(check({ visibility: 'public' }), 'owner')).toBe(false);
    expect(showsReadiness(check({ available: false }), 'owner')).toBe(false);
    expect(showsReadiness(null, 'owner')).toBe(false);
  });
});
