import { describe, expect, it } from 'vitest';
import {
  canViewAsSubscriber,
  findTestLibrary,
  leftBehind,
  makeTestLibrary,
  subscriberUnavailable,
  testLibraryLine,
  testLibraryName,
} from '../../src/lib/subscriber';
import type { SubscriberOut } from '../../src/lib/types';

function subscriber(overrides: Partial<SubscriberOut> = {}): SubscriberOut {
  return {
    tenant_id: 'lib',
    name: testLibraryName('Bestiary'),
    slug: 'test-library-bestiary',
    granted_at: '2026-10-01T10:00:00Z',
    granted_by: null,
    copied_at: null,
    synced_at: null,
    ...overrides,
  } as SubscriberOut;
}

const owned = [{ id: 'lib', role: 'owner' as const, kind: 'play' as const }];

describe('findTestLibrary', () => {
  it('finds a library the person owns, with the name, that is invited', () => {
    expect(findTestLibrary('Bestiary', [subscriber()], owned)).toEqual({
      id: 'lib',
      slug: 'test-library-bestiary',
      copied: false,
    });
    expect(
      findTestLibrary('Bestiary', [subscriber({ copied_at: '2026-10-02T10:00:00Z' })], owned)
        ?.copied,
    ).toBe(true);
  });

  it('does not take a library of the same name that is someone else is, or whose invitation is gone', () => {
    expect(findTestLibrary('Bestiary', [subscriber()], [])).toBeNull();
    expect(
      findTestLibrary('Bestiary', [subscriber()], [{ id: 'lib', role: 'orga', kind: 'play' }]),
    ).toBeNull();
    expect(findTestLibrary('Bestiary', [subscriber({ granted_at: null })], owned)).toBeNull();
  });

  it('does not take another repository’s Test library', () => {
    expect(findTestLibrary('Other', [subscriber()], owned)).toBeNull();
  });
});

describe('who is offered the button', () => {
  it('is an Owner who may create, on a published repository', () => {
    expect(canViewAsSubscriber('owner', true, true)).toBe(true);
    expect(canViewAsSubscriber('orga', true, true)).toBe(false);
    expect(canViewAsSubscriber('owner', false, true)).toBe(false);
    expect(canViewAsSubscriber('owner', true, false)).toBe(false);
  });

  it('says why not', () => {
    expect(subscriberUnavailable('owner', true, true)).toBeNull();
    expect(subscriberUnavailable('orga', true, true)).toMatch(/Only an Owner/);
    expect(subscriberUnavailable('owner', false, true)).toMatch(/isn't open/);
    expect(subscriberUnavailable('owner', true, false)).toMatch(/Publish this repository first/);
  });
});

describe('testLibraryLine', () => {
  it('says where the Test library stands', () => {
    expect(testLibraryLine(null)).toMatch(/no Test library/);
    expect(testLibraryLine({ id: 'a', slug: 'a', copied: false })).toMatch(/not copied/);
    expect(testLibraryLine({ id: 'a', slug: 'a', copied: true })).toMatch(/has copied/);
  });
});

describe('makeTestLibrary', () => {
  const repository = { id: 'repo', name: 'Bestiary' };

  it('creates the library and invites it', async () => {
    const calls: string[] = [];
    const library = await makeTestLibrary(
      {
        create: async (name) => {
          calls.push(`create ${name}`);
          return { id: 'lib', slug: 'test' };
        },
        invite: async (repo, lib) => void calls.push(`invite ${repo} ${lib}`),
        remove: async (lib) => void calls.push(`remove ${lib}`),
      },
      repository,
    );

    expect(library).toEqual({ id: 'lib', slug: 'test', copied: false });
    expect(calls).toEqual(['create Test library: Bestiary', 'invite repo lib']);
  });

  it('removes the library again when the invitation fails', async () => {
    const removed: string[] = [];
    const failure = new Error('refused');

    await expect(
      makeTestLibrary(
        {
          create: async () => ({ id: 'lib', slug: 'test' }),
          invite: async () => {
            throw failure;
          },
          remove: async (id) => void removed.push(id),
        },
        repository,
      ),
    ).rejects.toMatchObject({ cause: failure, cleanedUp: true });
    expect(removed).toEqual(['lib']);
  });

  it('says so when the clean-up fails too, and when nothing was made', async () => {
    await expect(
      makeTestLibrary(
        {
          create: async () => ({ id: 'lib', slug: 'test' }),
          invite: async () => {
            throw new Error('refused');
          },
          remove: async () => {
            throw new Error('also refused');
          },
        },
        repository,
      ),
    ).rejects.toMatchObject({ cleanedUp: false, libraryName: 'Test library: Bestiary' });
    expect(leftBehind('Test library: Bestiary')).toContain('could not be removed');

    const removed: string[] = [];

    await expect(
      makeTestLibrary(
        {
          create: async () => {
            throw new Error('no');
          },
          invite: async () => {},
          remove: async (id) => void removed.push(id),
        },
        repository,
      ),
    ).rejects.toThrow('no');
    expect(removed).toEqual([]);
  });
});
