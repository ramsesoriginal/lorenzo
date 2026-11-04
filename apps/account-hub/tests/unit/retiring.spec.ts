import { describe, expect, it } from 'vitest';
import {
  BRING_BACK_BUTTON,
  BRING_BACK_NOTE,
  messageCount,
  messageLine,
  messageProblem,
  RETIRE_BUTTON,
  RETIRE_CONFIRM,
  RETIRE_EXPLANATION,
  RETIRE_HEADING,
  RETIRE_MESSAGE_HELP,
  RETIRE_MESSAGE_LABEL,
  RETIRE_MESSAGE_MAX,
  RETIRED_CANNOT_BE_MADE_PUBLIC,
  RETIRED_CANNOT_COPY,
  RETIRED_EFFECT,
  RETIRED_KEPT,
  RETIRED_PILL,
  RETIRED_PUBLIC_NOTE,
  RETIRED_STATE,
  RETIRED_TITLE,
  retireBody,
  retireCard,
  retireDialogLines,
  retireDialogTitle,
  retiredAt,
  retiredHere,
  retiredNotice,
} from '../../src/lib/retiring';

describe('the message that goes with retiring a repository', () => {
  it('is optional, and sent only when something is written', () => {
    expect(retireBody('')).toEqual({});
    expect(retireBody('   \n ')).toEqual({});
    expect(retireBody('  Use Armoury 2 instead  ')).toEqual({ message: 'Use Armoury 2 instead' });
  });

  it('counts what is written against five hundred characters', () => {
    expect(RETIRE_MESSAGE_MAX).toBe(500);
    expect(messageCount('')).toBe('0 of 500 characters');
    expect(messageCount('  four ')).toBe('4 of 500 characters');
  });

  it('is a problem only past five hundred characters', () => {
    expect(messageProblem('x'.repeat(500))).toBeNull();
    expect(messageProblem(`  ${'x'.repeat(500)}  `)).toBeNull();
    expect(messageProblem('x'.repeat(501))).toBe('A message is at most 500 characters.');
  });

  it('is read as "Message: ..." and not at all where there is none', () => {
    expect(messageLine('Use Armoury 2 instead')).toBe('Message: Use Armoury 2 instead');
    expect(messageLine(null)).toBeNull();
    expect(messageLine('')).toBeNull();
    expect(messageLine(undefined)).toBeNull();
  });
});

describe('what the dialog says before a repository is retired', () => {
  it('names the repository', () => {
    expect(retireDialogTitle('Armoury')).toBe('Retire Armoury?');
  });

  it('says how many libraries hold it, that they keep their copy and are told', () => {
    expect(retireDialogLines(3)).toEqual([
      '3 libraries hold it. They keep their copy and its updates, and they will be told that you retired it.',
      'Nobody can copy it any more, and it leaves Discover.',
      'You can bring it back at any time.',
    ]);
    expect(retireDialogLines(1)[0]).toBe(
      '1 library holds it. It keeps its copy and its updates, and it will be told that you retired it.',
    );
    expect(retireDialogLines(0)[0]).toBe('No library holds it yet.');
  });
});

describe('the Owner’s card', () => {
  it('offers to retire a repository that is not retired', () => {
    expect(retireCard(null)).toEqual({ retired: false, message: null, since: null });
    expect(retireCard(undefined).retired).toBe(false);
  });

  it('shows the message and the way back for a retired one', () => {
    expect(retireCard({ message: 'Use Armoury 2', at: '2026-11-03T09:00:00Z' })).toEqual({
      retired: true,
      message: 'Use Armoury 2',
      since: 'Retired on 2026-11-03.',
    });
    expect(retireCard({ message: null, at: '2026-11-03T09:00:00Z' }).message).toBeNull();
    expect(retiredAt({ at: '2026-11-03T09:00:00Z' })).toBe('Retired on 2026-11-03.');
  });
});

describe('the notice of a repository that is retired', () => {
  it('is nothing for a repository that is not', () => {
    expect(retiredNotice(null)).toBeNull();
    expect(retiredNotice(undefined)).toBeNull();
  });

  it('says what it means for the libraries, with the message when there is one', () => {
    expect(retiredNotice({ message: 'Use Armoury 2', at: '2026-11-03T09:00:00Z' })).toEqual({
      pill: 'Retired',
      title: 'This repository is retired.',
      effect:
        'Libraries that copied it keep their copy and its updates. It cannot be copied or found in Discover.',
      message: 'Message: Use Armoury 2',
    });
    expect(retiredNotice({ message: null, at: '2026-11-03T09:00:00Z' })?.message).toBeNull();
  });
});

describe('what a library reads of a repository it holds that is retired', () => {
  it('is nothing for one that is not', () => {
    expect(retiredHere(null, true)).toBeNull();
    expect(retiredHere(undefined, false)).toBeNull();
  });

  it('tells a library with a copy what it keeps, and one without that it cannot copy it', () => {
    expect(retiredHere({ message: 'Use Armoury 2' }, true)).toEqual({
      pill: 'Retired',
      sentence: RETIRED_KEPT,
      message: 'Message from its Owner: Use Armoury 2',
    });
    expect(retiredHere({ message: null }, false)).toEqual({
      pill: 'Retired',
      sentence: 'This repository is retired and can no longer be copied.',
      message: null,
    });
  });
});

describe('the words', () => {
  const words = [
    RETIRED_PILL,
    RETIRE_HEADING,
    RETIRE_EXPLANATION,
    RETIRE_MESSAGE_LABEL,
    RETIRE_MESSAGE_HELP,
    RETIRE_BUTTON,
    RETIRE_CONFIRM,
    BRING_BACK_BUTTON,
    BRING_BACK_NOTE,
    RETIRED_STATE,
    RETIRED_TITLE,
    RETIRED_EFFECT,
    RETIRED_CANNOT_BE_MADE_PUBLIC,
    RETIRED_PUBLIC_NOTE,
    RETIRED_KEPT,
    RETIRED_CANNOT_COPY,
    ...retireDialogLines(2),
  ].join('\n');

  it('are those of the product, not of the architecture', () => {
    expect(words).not.toMatch(/tenant|grant|subscri|deprecat|delist/i);
  });

  it('say what the card promises', () => {
    expect(RETIRE_HEADING).toBe('Retire this repository');
    expect(RETIRE_BUTTON).toBe('Retire…');
    expect(BRING_BACK_BUTTON).toBe('Bring it back');
    expect(RETIRED_STATE).toBe('This repository is retired.');
    expect(RETIRE_EXPLANATION).toBe(
      'Libraries that already copied it keep their copy and its updates. Nobody can copy it any more, and it leaves Discover.',
    );
  });
});
