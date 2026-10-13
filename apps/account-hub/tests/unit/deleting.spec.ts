import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/lib/apiError';
import {
  deletedMessage,
  deleteFootnote,
  deleteIntro,
  deleteStanding,
  distinctPeople,
  lossLines,
  nameMatches,
  refusalMessage,
  standingNote,
  typeNamePrompt,
} from '../../src/lib/deleting';
import type { RosterEntry } from '../../src/lib/types';

function problem(status: number, type: string, detail: string): ApiError {
  return new ApiError(detail, status, type, { title: detail, status, detail, type });
}

describe('deleteStanding', () => {
  it('offers the button to an Owner whose account may delete', () => {
    expect(deleteStanding({ role: 'owner' }, true)).toBe('allowed');
  });

  it('tells an Owner without the platform permission, rather than showing a button that is refused', () => {
    expect(deleteStanding({ role: 'owner' }, false)).toBe('needs-permission');
  });

  it('gives an Organizer the reason, not the button', () => {
    expect(deleteStanding({ role: 'orga' }, true)).toBe('owner-only');
    expect(standingNote('owner-only', 'play')).toBe(
      'Only an Owner can delete this library. Ask one of its Owners if it should go.',
    );
  });

  it('shows anyone else nothing', () => {
    expect(deleteStanding({ role: 'participant' }, true)).toBe('none');
    expect(standingNote('none', 'play')).toBeNull();
    expect(standingNote('allowed', 'play')).toBeNull();
  });

  it('names the permission an Owner lacks, in the noun of the thing', () => {
    expect(standingNote('needs-permission', 'repository')).toContain('this repository');
    expect(standingNote('needs-permission', 'play')).toContain('permission to create');
  });
});

describe('what is said to be lost', () => {
  it('counts, with the singular where it is one', () => {
    expect(lossLines({ campaigns: 1, entries: 12, people: 1 })).toEqual([
      '1 campaign',
      '12 entries',
      '1 person with a role',
    ]);
    expect(lossLines({ campaigns: 0, entries: 1, people: 4 })).toEqual([
      '0 campaigns',
      '1 entry',
      '4 people with a role',
    ]);
  });

  it('leaves out what could not be read, rather than claiming zero', () => {
    expect(lossLines({ campaigns: null, entries: null, people: 2 })).toEqual([
      '2 people with a role',
    ]);
  });

  it('counts each person once, however many roles they hold', () => {
    const roster = [
      { kind: 'membership', user_id: 'a' },
      { kind: 'gm', user_id: 'a' },
      { kind: 'player', user_id: 'b' },
      { kind: 'player', user_id: null },
    ] as unknown as RosterEntry[];

    expect(distinctPeople(roster)).toBe(2);
  });

  it('says the deletion is for good, and the footnote differs for a repository', () => {
    expect(deleteIntro('Greywatch')).toBe(
      'This deletes "Greywatch" and everything in it for good. There is no undo.',
    );
    expect(deleteFootnote('repository')).toContain('keep what they copied');
    expect(deleteFootnote('play')).not.toContain('keep what they copied');
  });
});

describe('nameMatches', () => {
  it('opens only for the exact name, apart from space around it', () => {
    expect(nameMatches('Greywatch', 'Greywatch')).toBe(true);
    expect(nameMatches('  Greywatch ', 'Greywatch')).toBe(true);
    expect(nameMatches('greywatch', 'Greywatch')).toBe(false);
    expect(nameMatches('Greywatc', 'Greywatch')).toBe(false);
    expect(nameMatches('', 'Greywatch')).toBe(false);
  });

  it('never opens for a name that is empty', () => {
    expect(nameMatches('', '')).toBe(false);
  });

  it('prompts with the name in quotes', () => {
    expect(typeNamePrompt('Greywatch')).toBe('Type "Greywatch" to confirm');
    expect(deletedMessage('Greywatch', 'play')).toBe('Deleted library "Greywatch".');
    expect(deletedMessage('Bestiary', 'repository')).toBe('Deleted repository "Bestiary".');
  });
});

describe('refusalMessage', () => {
  it('explains a repository other libraries draw on, and the way out', () => {
    const message = refusalMessage(
      problem(409, 'repository-still-granted', 'Tenant x is still granted to 2 tenant(s)'),
      'repository',
    );

    expect(message).toContain('Other libraries still draw on this repository');
    expect(message).toContain('Libraries using it');
    expect(message).not.toMatch(/tenant/i);
  });

  it('says it in plain words when it is not an Owner or lacks the permission', () => {
    expect(refusalMessage(problem(403, 'tenant-deletion-forbidden', 'x'), 'play')).toBe(
      'Only an Owner can delete this library.',
    );
    expect(refusalMessage(problem(403, 'tenant-creation-forbidden', 'x'), 'play')).toContain(
      'permission',
    );
  });

  it('leaves anything else to describeError', () => {
    expect(refusalMessage(problem(500, 'something-else', 'boom'), 'play')).toBeNull();
    expect(refusalMessage(new Error('plain'), 'play')).toBeNull();
  });
});
