import { describe, expect, it } from 'vitest';
import { DELISTED_CANNOT_BE_MADE_PUBLIC, DELISTED_PUBLIC_NOTE } from '../../src/lib/delisting';
import type { FlipCheckOut } from '../../src/lib/types';
import {
  changedUnderTheDialog,
  madePrivateDone,
  makePrivateLines,
  makePrivateProblem,
  makePrivateQuery,
  makePublicBody,
  makePublicLines,
  makePublicProblem,
  makePublicWarnings,
  oneLine,
  PREVIEW_CHOICES,
  PREVIEW_DEFAULT,
  privateAcknowledgement,
  privateBlockers,
  publicBlockers,
  SUMMARY_MAX,
  summaryCount,
  summaryProblem,
  visibilityCard,
} from '../../src/lib/visibility';

function check(overrides: Partial<FlipCheckOut> = {}): FlipCheckOut {
  return {
    available: true,
    visibility: 'private',
    has_summary: false,
    built_on_not_public: [],
    built_on_behind: [],
    public_dependents: [],
    public_libraries: 0,
    invited_libraries: 0,
    ...overrides,
  };
}

const form = {
  summary: 'A bestiary.',
  preview: 'showcase' as const,
  label: '',
  notes: '',
  breaking: false,
  acknowledged: false,
};

// Everything a person reads, in one place, for the words nobody may read.
function words(): string {
  const dependents = [
    { id: 'd', name: 'Dragons', owned: true },
    { id: 'e', name: 'Elves', owned: false },
  ];

  return [
    visibilityCard(check(), 'owner')?.sentence,
    visibilityCard(check({ visibility: 'public' }), 'owner')?.sentence,
    ...publicBlockers(
      check({
        built_on_not_public: [
          { id: 'a', name: 'Core', owned: true },
          { id: 'b', name: 'Other', owned: false },
        ],
        built_on_behind: [
          {
            repository_id: 'c',
            name: 'Bridge',
            taken: { id: 'x', number: 1, label: '1' },
            current: { id: 'y', number: 2, label: '2' },
            readable: true,
          },
        ],
      }),
    ).flatMap((blocker) => [blocker.text, blocker.link?.label]),
    ...makePublicLines(check({ invited_libraries: 2 }), 'Bestiary'),
    ...makePublicWarnings(),
    ...makePrivateLines(check({ visibility: 'public', public_libraries: 3, invited_libraries: 1 })),
    privateAcknowledgement({ public_libraries: 3 }),
    ...privateBlockers(check({ public_dependents: dependents })).flatMap((blocker) => [
      blocker.text,
      blocker.link?.label,
    ]),
    madePrivateDone(2),
    ...PREVIEW_CHOICES.map((choice) => choice.label),
    DELISTED_CANNOT_BE_MADE_PUBLIC,
    DELISTED_PUBLIC_NOTE,
  ].join('\n');
}

describe('the card', () => {
  it('says private, with the button to make it public', () => {
    const card = visibilityCard(check(), 'owner');

    expect(card?.label).toBe('Private');
    expect(card?.button).toBe('Make public…');
    expect(card?.visibility).toBe('private');
  });

  it('says public, with the button to make it private', () => {
    const card = visibilityCard(check({ visibility: 'public' }), 'owner');

    expect(card?.label).toBe('Public');
    expect(card?.button).toBe('Make private…');
  });

  it('is not shown while the deployment has no public repositories and the repository is private', () => {
    expect(visibilityCard(check({ available: false }), 'owner')).toBeNull();
  });

  it('is shown for a repository that is public, available or not, so that it can be made private', () => {
    const card = visibilityCard(check({ available: false, visibility: 'public' }), 'owner');

    expect(card?.button).toBe('Make private…');
  });

  it('is only an Owner’s, and not before the repository was read', () => {
    expect(visibilityCard(check(), 'orga')).toBeNull();
    expect(visibilityCard(check(), 'author')).toBeNull();
    expect(visibilityCard(check({ visibility: 'public' }), 'orga')).toBeNull();
    expect(visibilityCard(null, 'owner')).toBeNull();
  });
});

describe('the card of a repository that is off Discover', () => {
  const delisted = { reason: 'It copies another publisher', at: '2026-10-15T09:00:00Z' };

  it('says so beside a button that cannot be pressed, while it is private', () => {
    const card = visibilityCard(check({ delisted }), 'owner');

    expect(card?.button).toBe('Make public…');
    expect(card?.disabled).toBe(true);
    expect(card?.note).toBe(DELISTED_CANNOT_BE_MADE_PUBLIC);
  });

  it('leaves "Make private…" pressable while it is public, and says it is off Discover', () => {
    const card = visibilityCard(check({ visibility: 'public', delisted }), 'owner');

    expect(card?.button).toBe('Make private…');
    expect(card?.disabled).toBe(false);
    expect(card?.note).toBe(DELISTED_PUBLIC_NOTE);
  });

  it('is hidden as before where the deployment has no public repositories', () => {
    expect(visibilityCard(check({ available: false, delisted }), 'owner')).toBeNull();
  });

  it('is as it was for a repository that is listed', () => {
    const card = visibilityCard(check(), 'owner');

    expect(card?.disabled).toBe(false);
    expect(card?.note).toBeNull();
  });
});

describe('what stands in the way of making it public', () => {
  it('is nothing when the repository stands alone', () => {
    expect(publicBlockers(check())).toEqual([]);
  });

  it('links a repository it is built on that the Owner owns, and tells whom to ask for the others', () => {
    const [owned, notOwned] = publicBlockers(
      check({
        built_on_not_public: [
          { id: 'core-id', name: 'Core', owned: true },
          { id: 'other-id', name: 'Other', owned: false },
        ],
      }),
    );

    expect(owned?.text).toContain('Core is not public');
    expect(owned?.link).toEqual({
      href: '/studio/?repository=core-id',
      label: 'Open Core to make it public',
    });
    expect(notOwned?.text).toContain('Other is not public');
    expect(notOwned?.text).toContain('ask its Owner to make it public');
    expect(notOwned?.link).toBeUndefined();
  });

  it('says which release a repository it is built on has that this one has not taken', () => {
    const [blocker] = publicBlockers(
      check({
        built_on_behind: [
          {
            repository_id: 'c',
            name: 'Bridge',
            taken: { id: 'x', number: 1, label: '1.0' },
            current: { id: 'y', number: 2, label: '1.1' },
            readable: true,
          },
        ],
      }),
    );

    expect(blocker?.text).toContain('Take the new release of Bridge first: open Built on.');
    expect(blocker?.text).toContain('took release 1.0, and the latest is 1.1');
  });

  it('says it without the releases when one cannot be named', () => {
    const [blocker] = publicBlockers(
      check({
        built_on_behind: [
          { repository_id: 'c', name: 'Bridge', taken: null, current: null, readable: false },
        ],
      }),
    );

    expect(blocker?.text).toBe(
      'Bridge has a release this repository has not taken. Take the new release of Bridge first: open Built on.',
    );
  });
});

describe('the Make public dialog', () => {
  it('says what a release does and who is told', () => {
    const lines = makePublicLines(check({ invited_libraries: 2 }), 'Bestiary');

    expect(lines[0]).toContain('Making Bestiary public publishes a release');
    expect(lines[1]).toContain('what you edit between two releases is not seen');
    expect(lines[2]).toBe(
      "2 libraries have an invitation and are told when you publish: each one's Owners and Organizers get a notification.",
    );
    expect(makePublicLines(check({ invited_libraries: 1 }), 'B')[2]).toContain(
      '1 library has an invitation and is told',
    );
    expect(makePublicLines(check(), 'B')).toHaveLength(2);
  });

  it('warns that GM-only text is in a copy, and that copies stay', () => {
    const [gm, keep] = makePublicWarnings();

    expect(gm).toContain('includes text marked GM only');
    expect(gm).toContain('Players never see it');
    expect(keep).toBe(
      'Libraries that copy it keep their copies, whatever you do to this repository later.',
    );
  });

  it('offers three previews, showcase first, in plain words', () => {
    expect(PREVIEW_DEFAULT).toBe('showcase');
    expect(PREVIEW_CHOICES.map((choice) => choice.value)).toEqual(['showcase', 'public', 'off']);
    expect(PREVIEW_CHOICES.map((choice) => choice.label)).toEqual([
      'People can look at the entries you feature before copying.',
      'People can look at every entry.',
      'People see its summary and counts only.',
    ]);
  });

  it('is never said in the words of the architecture', () => {
    expect(words()).not.toMatch(/tenant|grant|subscri|source =/i);
  });

  it('does not say a terms line or who is shown as the publisher: those are not decided', () => {
    expect(words()).not.toMatch(/terms|publisher|licen[cs]e/i);
  });
});

describe('the summary', () => {
  it('is required', () => {
    expect(summaryProblem('')).toContain('Write a summary');
    expect(summaryProblem('   \n  ')).toContain('Write a summary');
  });

  it('is at most 280 characters, counted as the API keeps it, on one line', () => {
    expect(summaryProblem('a'.repeat(SUMMARY_MAX))).toBeNull();
    expect(summaryProblem('a'.repeat(SUMMARY_MAX + 1))).toBe(
      `A summary is at most ${SUMMARY_MAX} characters. This one is ${SUMMARY_MAX + 1}.`,
    );
    // Whitespace runs together: two lines and some spaces count as one space each.
    expect(oneLine('  Two\n\n lines   here ')).toBe('Two lines here');
    expect(summaryCount('Two\n\n lines')).toBe('9 of 280');
  });

  it('is checked before the release', () => {
    expect(makePublicProblem({ ...form, summary: '' }, [])).toContain('Write a summary');
    expect(makePublicProblem({ ...form, label: 'x'.repeat(81) }, [])).toContain(
      'A label is at most',
    );
    expect(makePublicProblem(form, [])).toBeNull();
  });

  it('wants what a release breaks acknowledged', () => {
    const rows = [{ detail: 'It removes Longsword.' }] as never;

    expect(makePublicProblem(form, rows)).toContain('This release breaks things');
    expect(makePublicProblem({ ...form, acknowledged: true }, rows)).toBeNull();
  });
});

describe('the body of the request', () => {
  it('sends the summary on one line, the preview chosen, and leaves a blank label out', () => {
    expect(makePublicBody({ ...form, summary: '  A\n bestiary. ', preview: 'off' }, [])).toEqual({
      summary: 'A bestiary.',
      preview: 'off',
      breaking: false,
      acknowledge_breaking: false,
    });
  });

  it('sends the label and notes, and the acknowledgement of what breaks', () => {
    const rows = [{ detail: 'It removes Longsword.' }] as never;

    expect(
      makePublicBody(
        { ...form, label: ' 1.0 ', notes: ' First. ', acknowledged: true, preview: 'public' },
        rows,
      ),
    ).toEqual({
      label: '1.0',
      notes: 'First.',
      summary: 'A bestiary.',
      preview: 'public',
      breaking: true,
      acknowledge_breaking: true,
    });
  });
});

describe('the Make private dialog', () => {
  it('says how many libraries copied it by themselves, what they keep and lose, and that the invited keep access', () => {
    const lines = makePrivateLines(
      check({ visibility: 'public', public_libraries: 3, invited_libraries: 2 }),
    );

    expect(lines[0]).toBe(
      '3 libraries copied it while it was public: they keep what they copied and lose its updates. The Owners and Organizers of those libraries are told.',
    );
    expect(lines[1]).toBe(
      '2 libraries you invited keep their access, and read the repository as it is again, not its releases.',
    );
  });

  it('says one library in the singular', () => {
    const lines = makePrivateLines(
      check({ visibility: 'public', public_libraries: 1, invited_libraries: 1 }),
    );

    expect(lines[0]).toContain(
      '1 library copied it while it was public: it keeps what it copied and loses its updates.',
    );
    expect(lines[1]).toContain('1 library you invited keeps its access, and reads the repository');
  });

  it('says that nobody loses anything when nobody copied it', () => {
    const lines = makePrivateLines(check({ visibility: 'public' }));

    expect(lines[0]).toContain('No library copied it by itself');
    expect(lines).toHaveLength(2);
  });

  it('is blocked by the public repositories built on it, named', () => {
    const blockers = privateBlockers(
      check({
        visibility: 'public',
        public_dependents: [
          { id: 'a', name: 'Dragons', owned: true },
          { id: 'b', name: 'Giants', owned: false },
        ],
      }),
    );

    expect(blockers.map((blocker) => blocker.text)).toEqual([
      'Dragons is public and built on this repository. Make it private first, so that what it is built on can still be copied.',
      'Giants is public and built on this repository. It has to be private first, so that what it is built on can still be copied: ask its Owner to make it private.',
    ]);
    // A link to the Studio page of one the Owner owns, and none for the other.
    expect(blockers[0]?.link).toEqual({
      href: '/studio/?repository=a',
      label: 'Open Dragons to make it private',
    });
    expect(blockers[1]?.link).toBeUndefined();
    expect(privateBlockers(check({ visibility: 'public' }))).toEqual([]);
  });

  it('asks to be acknowledged only when libraries lose its updates', () => {
    expect(privateAcknowledgement({ public_libraries: 0 })).toBeNull();
    expect(privateAcknowledgement({ public_libraries: 2 })).toBe(
      'I understand that 2 libraries will lose the updates of this repository and keep what they copied.',
    );
    expect(makePrivateProblem({ public_libraries: 0 }, false)).toBeNull();
    expect(makePrivateProblem({ public_libraries: 2 }, false)).toContain('Say you understand');
    expect(makePrivateProblem({ public_libraries: 2 }, true)).toBeNull();
  });

  it('sends the acknowledgement only when there is something to acknowledge', () => {
    expect(makePrivateQuery({ public_libraries: 0 }, true)).toBe(false);
    expect(makePrivateQuery({ public_libraries: 2 }, false)).toBe(false);
    expect(makePrivateQuery({ public_libraries: 2 }, true)).toBe(true);
  });

  it('says what was done', () => {
    expect(madePrivateDone(0)).toBe('Private again.');
    expect(madePrivateDone(1)).toBe(
      'Private again. 1 library lost its updates and keeps what it copied.',
    );
    expect(madePrivateDone(4)).toBe(
      'Private again. 4 libraries lost its updates and keep what they copied.',
    );
  });
});

describe('a refusal that changes what the dialog says', () => {
  it('is one the API gives when something changed under it', () => {
    expect(changedUnderTheDialog('built-on-not-public')).toBe(true);
    expect(changedUnderTheDialog('public-copies-would-be-cut-off')).toBe(true);
    expect(changedUnderTheDialog('repository-delisted')).toBe(true);
    expect(changedUnderTheDialog('public-repository-summary-required')).toBe(false);
    expect(changedUnderTheDialog(undefined)).toBe(false);
  });
});
