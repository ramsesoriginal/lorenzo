import { describe, expect, it } from 'vitest';
import {
  attachmentsSentence,
  broughtSentence,
  countsKnown,
  dayOf,
  insideCounts,
  kindLabel,
  outlineOf,
  parentsLine,
  readShelfLocation,
  shelfHref,
  shelfState,
  sortSubscriptions,
  updatesHref,
} from '../../src/lib/shelf';
import type {
  CopyPlanOut,
  CopyStepOut,
  RepositoryEntityOut,
  SubscriptionOut,
} from '../../src/lib/types';

function subscription(overrides: {
  name?: string;
  published_at?: string | null;
  granted_at?: string | null;
  copied_at?: string | null;
  synced_at?: string | null;
}): SubscriptionOut {
  return {
    repository: {
      id: 'repo-1',
      name: overrides.name ?? 'Core',
      slug: 'core',
      description: '',
      published_at:
        overrides.published_at === undefined ? '2026-10-03T10:00:00Z' : overrides.published_at,
    },
    granted_at: overrides.granted_at === undefined ? '2026-10-01T10:00:00Z' : overrides.granted_at,
    copied_at: overrides.copied_at === undefined ? null : overrides.copied_at,
    synced_at: overrides.synced_at === undefined ? null : overrides.synced_at,
    contributed: null,
  };
}

function step(
  overrides: Partial<CopyStepOut> & { repository_id: string; name: string },
): CopyStepOut {
  return {
    granted: true,
    published: true,
    already_copied: false,
    entities: 0,
    stat_groups: 0,
    stat_definitions: 0,
    information: 0,
    attachments: 0,
    dropped: [],
    ...overrides,
  };
}

describe('shelfState', () => {
  it('is "not copied yet" for an invitation nothing has been taken from', () => {
    expect(shelfState(subscription({}))).toBe('not-copied');
  });

  it('is "copied" when nothing was published after the last update', () => {
    expect(
      shelfState(
        subscription({ copied_at: '2026-10-04T10:00:00Z', synced_at: '2026-10-05T10:00:00Z' }),
      ),
    ).toBe('copied');
  });

  it('is "update announced" when the repository was published after the last update', () => {
    expect(
      shelfState(
        subscription({ copied_at: '2026-10-01T10:00:00Z', synced_at: '2026-10-02T10:00:00Z' }),
      ),
    ).toBe('update-announced');
  });

  it('counts the copy as the first update when there has been no other', () => {
    expect(shelfState(subscription({ copied_at: '2026-10-02T10:00:00Z' }))).toBe(
      'update-announced',
    );
    expect(shelfState(subscription({ copied_at: '2026-10-04T10:00:00Z' }))).toBe('copied');
  });

  it('is "no longer offered" once the invitation is gone, whatever else is true', () => {
    expect(shelfState(subscription({ granted_at: null, copied_at: '2026-10-01T10:00:00Z' }))).toBe(
      'no-longer-offered',
    );
  });

  it('is "not published" for a repository that is a draft, even one that was copied', () => {
    expect(shelfState(subscription({ published_at: null }))).toBe('not-published');
    expect(
      shelfState(subscription({ published_at: null, copied_at: '2026-10-01T10:00:00Z' })),
    ).toBe('not-published');
  });
});

describe('sortSubscriptions', () => {
  it('puts those with news first, then by name without regard to case', () => {
    const sorted = sortSubscriptions([
      subscription({ name: 'zeta', copied_at: '2026-10-04T10:00:00Z' }),
      subscription({ name: 'Alpha', copied_at: '2026-10-04T10:00:00Z' }),
      subscription({ name: 'Mid', copied_at: '2026-10-01T10:00:00Z' }),
    ]);

    expect(sorted.map((s) => s.repository.name)).toEqual(['Mid', 'Alpha', 'zeta']);
  });
});

describe('shelfHref and readShelfLocation', () => {
  it('builds the address of a library, and of one of its repositories', () => {
    expect(shelfHref('table-one')).toBe('/repositories/?tenant=table-one');
    expect(shelfHref('table-one', 'abc')).toBe('/repositories/?tenant=table-one&repository=abc');
  });

  it('builds the address of the copy wizard, only for a repository', () => {
    expect(shelfHref('table-one', 'abc', 'new')).toBe(
      '/repositories/?tenant=table-one&repository=abc&copy=new',
    );
    expect(shelfHref('table-one', 'abc', 'again')).toBe(
      '/repositories/?tenant=table-one&repository=abc&copy=again',
    );
    expect(shelfHref('table-one', undefined, 'new')).toBe('/repositories/?tenant=table-one');
  });

  it('reads them back, and says nothing for what the address leaves out', () => {
    expect(readShelfLocation('?tenant=table-one&repository=abc')).toEqual({
      library: 'table-one',
      repository: 'abc',
      copy: null,
      updates: false,
    });
    expect(readShelfLocation('')).toEqual({
      library: null,
      repository: null,
      copy: null,
      updates: false,
    });
  });

  it('builds the address of the update inbox, and of the updates of one repository', () => {
    expect(updatesHref('table-one')).toBe('/repositories/?tenant=table-one&updates=1');
    expect(updatesHref('table-one', 'abc')).toBe(
      '/repositories/?tenant=table-one&repository=abc&updates=1',
    );
    expect(readShelfLocation('?tenant=t&updates=1').updates).toBe(true);
    expect(readShelfLocation('?tenant=t&updates=0').updates).toBe(false);
  });

  it('reads a copy as a first one unless it says "again"', () => {
    expect(readShelfLocation('?tenant=t&repository=r&copy=again').copy).toBe('again');
    expect(readShelfLocation('?tenant=t&repository=r&copy=new').copy).toBe('new');
    expect(readShelfLocation('?tenant=t&repository=r&copy=').copy).toBe('new');
  });
});

describe('dayOf', () => {
  it('keeps the day of a timestamp', () => {
    expect(dayOf('2026-10-03T12:34:56Z')).toBe('2026-10-03');
  });
});

describe('outlineOf', () => {
  const plan: CopyPlanOut = {
    steps: [
      step({ repository_id: 'core', name: 'Core', already_copied: true }),
      step({ repository_id: 'rules', name: 'D&D 5e' }),
      step({ repository_id: 'lore', name: 'Faerûn', granted: false }),
      step({ repository_id: 'draft', name: 'Homebrew', published: false }),
      step({ repository_id: 'bridge', name: 'D&D 5e in Faerûn' }),
    ],
    collisions: [],
  };

  it('puts the repository first and what it is built on after, with each one in words', () => {
    const outline = outlineOf(plan, 'bridge');

    expect(outline?.root).toMatchObject({
      name: 'D&D 5e in Faerûn',
      state: 'this',
      label: 'This repository',
    });
    expect(outline?.builtOn.map((node) => [node.name, node.label])).toEqual([
      ['Core', 'Copied'],
      ['D&D 5e', 'Invited, not copied'],
      ['Faerûn', 'Not invited'],
      ['Homebrew', 'Not published'],
    ]);
  });

  it('says whom to ask for what cannot be taken in, and nothing for the rest', () => {
    const outline = outlineOf(plan, 'bridge');
    const hints = Object.fromEntries(
      (outline?.builtOn ?? []).map((node) => [node.name, node.hint]),
    );

    expect(hints.Faerûn).toBe('Ask the owner of Faerûn to invite your library.');
    expect(hints.Homebrew).toBe('Homebrew is not published; ask its owner to publish it.');
    expect(hints.Core).toBeNull();
    expect(hints['D&D 5e']).toBeNull();
  });

  it('is a repository on its own when it is built on nothing', () => {
    const alone: CopyPlanOut = {
      steps: [step({ repository_id: 'core', name: 'Core' })],
      collisions: [],
    };

    expect(outlineOf(alone, 'core')?.builtOn).toEqual([]);
  });

  it('is nothing for a plan that does not hold the repository', () => {
    expect(outlineOf(plan, 'missing')).toBeNull();
  });
});

describe('countsKnown', () => {
  const alone = (overrides: Partial<CopyStepOut> = {}): CopyPlanOut => ({
    steps: [step({ repository_id: 'r', name: 'R', ...overrides })],
    collisions: [],
  });

  it('is true for a repository offered, published and not yet copied', () => {
    expect(countsKnown(alone(), 'r')).toBe(true);
  });

  it('is false once the repository is copied, since a copy is not counted again', () => {
    expect(countsKnown(alone({ already_copied: true }), 'r')).toBe(false);
  });

  it('is false when a repository it is built on is not offered or not published', () => {
    const plan = (dependency: Partial<CopyStepOut>): CopyPlanOut => ({
      steps: [
        step({ repository_id: 'core', name: 'Core', ...dependency }),
        step({ repository_id: 'r', name: 'R' }),
      ],
      collisions: [],
    });

    expect(countsKnown(plan({ granted: false }), 'r')).toBe(false);
    expect(countsKnown(plan({ published: false }), 'r')).toBe(false);
    expect(countsKnown(plan({ already_copied: true, granted: false }), 'r')).toBe(true);
    expect(countsKnown(plan({}), 'r')).toBe(true);
  });

  it('is false for a plan that does not hold the repository', () => {
    expect(countsKnown(alone(), 'missing')).toBe(false);
  });
});

describe('insideCounts and attachmentsSentence', () => {
  it('names what the plan counts', () => {
    expect(
      insideCounts(
        step({
          repository_id: 'r',
          name: 'R',
          entities: 312,
          stat_groups: 12,
          stat_definitions: 41,
          information: 90,
        }),
      ),
    ).toEqual([
      { label: 'Entries', value: 312 },
      { label: 'Stat groups', value: 12 },
      { label: 'Stats', value: 41 },
      { label: 'Descriptions and notes', value: 90 },
    ]);
  });

  it('says nothing about attachments when there are none, and one sentence when there are', () => {
    expect(attachmentsSentence(0)).toBeNull();
    expect(attachmentsSentence(1)).toBe(
      'It adds a parent to one entry of a repository it is built on.',
    );
    expect(attachmentsSentence(6)).toBe(
      'It adds a parent to 6 entries of repositories it is built on.',
    );
  });
});

describe('broughtSentence', () => {
  it('adds copied and merged together and gets the singular right', () => {
    expect(
      broughtSentence({
        entities: 1,
        stat_groups_copied: 2,
        stat_groups_merged: 1,
        stat_definitions_copied: 0,
        stat_definitions_merged: 1,
        attachments: 0,
      }),
    ).toBe('It brought 1 entry, 3 stat groups and 1 stat.');
  });
});

describe('kindLabel and parentsLine', () => {
  const entry = (prototype_ids: string[]): RepositoryEntityOut => ({
    id: 'e',
    name: 'Ashfang',
    kinds: ['item', 'being'],
    prototype_ids,
  });

  it('calls an item in play an inventory item', () => {
    expect(kindLabel('item_instance')).toBe('Inventory item');
    expect(kindLabel('being')).toBe('Being');
  });

  it('names the parents it can and counts the rest, never showing an id', () => {
    const names = new Map([['a', 'Sword']]);

    expect(parentsLine(entry([]), names)).toBeNull();
    expect(parentsLine(entry(['a']), names)).toBe('Inherits from Sword');
    expect(parentsLine(entry(['a', 'zzz-uuid']), names)).toBe(
      'Inherits from Sword, 1 more not shown yet',
    );
    expect(parentsLine(entry(['zzz-uuid']), names)).toBe('Inherits from 1 more not shown yet');
  });
});
