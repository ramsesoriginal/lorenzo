import { describe, expect, it } from 'vitest';
import type { SubscriberOut, SubscriptionOut } from '../../src/lib/types';
import {
  BUILT_ON_ADD,
  builtOn,
  INVITE_HELP,
  libraryIdProblem,
  stopInvitingConfirmation,
  USING_LABEL,
  usingLine,
  usingState,
  usingSummary,
} from '../../src/lib/using';

function subscriber(overrides: Partial<SubscriberOut> = {}): SubscriberOut {
  return {
    tenant_id: 't-1',
    name: 'My Table',
    slug: 'my-table',
    granted_at: '2026-10-01T10:00:00Z',
    granted_by: null,
    copied_at: null,
    synced_at: null,
    ...overrides,
  } as SubscriberOut;
}

describe('where a library stands with a repository', () => {
  it('is invited when it has an invitation and no copy', () => {
    expect(usingState(subscriber())).toBe('invited');
  });

  it('is copied when it has both', () => {
    expect(usingState(subscriber({ copied_at: '2026-10-02T10:00:00Z' }))).toBe('copied');
  });

  it('is kept when it copied and the invitation is gone', () => {
    expect(usingState(subscriber({ granted_at: null, copied_at: '2026-10-02T10:00:00Z' }))).toBe(
      'kept',
    );
  });

  it('says it in words, never as the API does', () => {
    expect(USING_LABEL).toEqual({
      invited: 'Invited, not copied yet',
      copied: 'Copied',
      kept: 'Not invited any more',
    });
  });
});

describe('a row in a line', () => {
  it('says the days it was invited, copied and last updated', () => {
    expect(
      usingLine(
        subscriber({ copied_at: '2026-10-02T10:00:00Z', synced_at: '2026-10-05T10:00:00Z' }),
      ),
    ).toBe('Invited 2026-10-01, copied 2026-10-02, last updated 2026-10-05.');
  });

  it('says which release a library is on', () => {
    expect(
      usingLine(
        subscriber({
          copied_at: '2026-10-02T10:00:00Z',
          synced_release: { id: 'r1', number: 1, label: '1.2' },
        }),
      ),
    ).toBe('Invited 2026-10-01, copied 2026-10-02, on release 1.2.');
  });

  it('does not say "last updated" for the day it copied', () => {
    expect(
      usingLine(
        subscriber({ copied_at: '2026-10-02T10:00:00Z', synced_at: '2026-10-02T11:00:00Z' }),
      ),
    ).toBe('Invited 2026-10-01, copied 2026-10-02.');
  });

  it('says what a copy that outlived its invitation means', () => {
    expect(usingLine(subscriber({ granted_at: null, copied_at: '2026-10-02T10:00:00Z' }))).toBe(
      'copied 2026-10-02. It keeps its copy and gets no more updates unless you invite it again.',
    );
  });
});

describe('the summary', () => {
  it('says so when nothing uses it', () => {
    expect(usingSummary([])).toMatch(/Nothing is using this repository yet/);
  });

  it('counts those with an invitation or a copy, and those who copied', () => {
    const rows = [
      subscriber(),
      subscriber({ tenant_id: 't-2', copied_at: '2026-10-02T10:00:00Z' }),
      subscriber({ tenant_id: 't-3', granted_at: null, copied_at: '2026-10-02T10:00:00Z' }),
    ];

    expect(usingSummary(rows)).toBe(
      '3 libraries and repositories have an invitation or a copy. 2 of them have copied it.',
    );
    expect(usingSummary([rows[1] as SubscriberOut])).toBe(
      '1 library or repository has an invitation or a copy. 1 of them has copied it.',
    );
  });
});

describe('inviting one', () => {
  it('needs an id, and says what one looks like', () => {
    expect(libraryIdProblem('')).toMatch(/Paste the id/);
    expect(libraryIdProblem('my-table')).toMatch(/not an id/);
    expect(libraryIdProblem(' 3f2a9c1e-0b7d-4f6a-9d1c-2a8b7e6f5d4c ')).toBeNull();
  });

  it('uses the glossary', () => {
    const text = [INVITE_HELP, stopInvitingConfirmation('X'), BUILT_ON_ADD].join(' ');

    expect(text).not.toMatch(/tenant|grant|subscri/i);
  });

  it('says before it stops what that does: the copy stays, and the library is told', () => {
    expect(stopInvitingConfirmation('My Table')).toBe(
      'Stop inviting “My Table”? What it copied stays with it, and it gets no more updates from this repository unless you invite it again. Its Owners and Organizers are told.',
    );
  });
});

describe('built on', () => {
  function subscription(overrides: Partial<SubscriptionOut> & { name: string }): SubscriptionOut {
    const { name, ...rest } = overrides;

    return {
      repository: {
        id: `id-${name}`,
        name,
        slug: name.toLowerCase(),
        description: '',
        published_at: '2026-10-01T10:00:00Z',
      },
      granted_at: '2026-10-01T10:00:00Z',
      copied_at: null,
      synced_at: null,
      contributed: null,
      ...rest,
    } as SubscriptionOut;
  }

  it('lists what a repository copied or is invited to copy, by name, with its state in words', () => {
    const rows = builtOn([
      subscription({
        name: 'Rules',
        copied_at: '2026-10-02T10:00:00Z',
        synced_at: '2026-10-04T10:00:00Z',
      }),
      subscription({ name: 'Core' }),
    ]);

    expect(rows.map((row) => row.name)).toEqual(['Core', 'Rules']);
    expect(rows[0]).toMatchObject({
      state: 'not-copied',
      checkable: false,
      line: 'invited 2026-10-01.',
    });
    expect(rows[1]).toMatchObject({
      state: 'copied',
      checkable: true,
      line: 'copied 2026-10-02, last updated 2026-10-04.',
    });
  });

  it('checks only a copy of what is still offered and published', () => {
    const gone = subscription({
      name: 'Gone',
      granted_at: null,
      copied_at: '2026-10-02T10:00:00Z',
    });
    const unpublished = subscription({ name: 'Draft', copied_at: '2026-10-02T10:00:00Z' });

    unpublished.repository.published_at = null;

    expect(builtOn([gone, unpublished]).map((row) => row.checkable)).toEqual([false, false]);
  });
});
