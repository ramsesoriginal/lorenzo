import { LorenzoApiError } from '@lorenzo/api-client';
import { describe, expect, it } from 'vitest';
import {
  alsoRemovedSentence,
  CHOICE_LABEL,
  type Choice,
  COPY_LIMITS,
  choiceExplanation,
  choiceProblem,
  collisionKey,
  collisionSentence,
  copyRefusal,
  droppedSentences,
  missingSentence,
  previousSentence,
  receiptSentence,
  recommendedAction,
  recommendedChoices,
  resolutionsOf,
  stepHeading,
  stepLine,
  suggestedName,
  unsettled,
  withFound,
  wizardSteps,
} from '../../src/lib/copyWizard';
import type { CollisionOut, CopyOut, CopyStepOut } from '../../src/lib/types';

function collision(overrides: Partial<CollisionOut> = {}): CollisionOut {
  return {
    repository_id: 'repo-1',
    kind: 'stat_definition',
    source_id: 'src-1',
    name: 'Weight',
    local_id: 'local-1',
    choices: ['rename', 'merge', 'skip'],
    ...overrides,
  };
}

function step(overrides: Partial<CopyStepOut> = {}): CopyStepOut {
  return {
    repository_id: 'repo-1',
    name: 'Core rules',
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

function copy(overrides: Partial<CopyOut> = {}): CopyOut {
  return {
    steps: [step({ entities: 309, stat_groups: 2, stat_definitions: 12 })],
    dry_run: true,
    previous: null,
    ...overrides,
  };
}

describe('the limits of a copy', () => {
  it('say what cannot be undone, the one game system and what GM only means', () => {
    const text = COPY_LIMITS.join(' ');

    expect(text).toMatch(/cannot be undone as a whole/);
    expect(text).toMatch(/one game system at a time/);
    expect(text).toMatch(/GM only/);
  });

  it('use the glossary: a library, never a tenant', () => {
    expect(COPY_LIMITS.join(' ')).not.toMatch(/tenant|collision|dry run/i);
  });
});

describe('a name clash in words', () => {
  it('says what the library already has', () => {
    expect(collisionSentence(collision({ kind: 'stat_group', name: 'Combat' }))).toBe(
      'Your library already has a stat group called “Combat”.',
    );
    expect(collisionSentence(collision())).toBe('Your library already has a stat called “Weight”.');
    expect(collisionSentence(collision({ kind: 'slug', name: 'longsword' }))).toBe(
      'Your library already has an entry with the link name “longsword”.',
    );
  });

  it('names the three choices as the glossary does', () => {
    expect(CHOICE_LABEL).toEqual({
      rename: 'Keep both',
      merge: 'Use the existing one',
      skip: 'Leave it out',
    });
  });

  it('says what a choice costs next to it', () => {
    expect(choiceExplanation(collision({ kind: 'stat_group' }), 'skip')).toMatch(
      /nor are its stats/,
    );
    expect(choiceExplanation(collision(), 'skip')).toMatch(/value or formula that uses it/);
    expect(choiceExplanation(collision({ kind: 'slug' }), 'rename')).toMatch(
      /Links in the copied text .* point at your own entry/,
    );
    expect(choiceExplanation(collision({ kind: 'slug' }), 'skip')).toMatch(/without a link name/);
  });
});

describe('what is recommended', () => {
  it('is to use the existing stat group or stat of the same name', () => {
    expect(recommendedAction(collision({ kind: 'stat_group' }))).toBe('merge');
    expect(recommendedAction(collision())).toBe('merge');
  });

  it('is to keep both when the existing one cannot be used, and for a link name', () => {
    expect(recommendedAction(collision({ choices: ['rename', 'skip'] }))).toBe('rename');
    expect(recommendedAction(collision({ kind: 'slug', choices: ['rename', 'skip'] }))).toBe(
      'rename',
    );
  });

  it('never leaves something out', () => {
    for (const kind of ['stat_group', 'stat_definition', 'slug'] as const) {
      expect(recommendedAction(collision({ kind }))).not.toBe('skip');
    }
  });

  it('starts a new name from where the copy came from', () => {
    expect(suggestedName(collision(), 'Core rules')).toBe('Weight (Core rules)');
    expect(suggestedName(collision({ kind: 'slug', name: 'longsword' }), 'Core rules')).toBe(
      'longsword-2',
    );
    expect(suggestedName(collision({ kind: 'slug', name: 'a'.repeat(100) }), 'x')).toHaveLength(
      100,
    );
  });

  it('gives each clash its own recommendation, by key', () => {
    const one = collision();
    const two = collision({
      kind: 'slug',
      source_id: 'src-2',
      name: 'axe',
      choices: ['rename', 'skip'],
    });
    const choices = recommendedChoices([one, two], 'Core rules');

    expect(choices.get(collisionKey(one))?.action).toBe('merge');
    expect(choices.get(collisionKey(two))).toEqual({ action: 'rename', name: 'axe-2' });
  });
});

describe('whether a choice can be sent', () => {
  it('needs a choice, one that is open for the clash', () => {
    expect(choiceProblem(collision(), undefined)).toBe('Choose what to do.');
    expect(
      choiceProblem(collision({ choices: ['rename', 'skip'] }), { action: 'merge', name: '' }),
    ).toBe('That choice is not open for this one.');
  });

  it('needs a new name only for Keep both', () => {
    expect(choiceProblem(collision(), { action: 'merge', name: '' })).toBeNull();
    expect(choiceProblem(collision(), { action: 'skip', name: '' })).toBeNull();
    expect(choiceProblem(collision(), { action: 'rename', name: '  ' })).toBe('Type a new name.');
    expect(choiceProblem(collision(), { action: 'rename', name: 'Weight' })).toBe(
      'Type a name that is different.',
    );
    expect(choiceProblem(collision(), { action: 'rename', name: 'Mass' })).toBeNull();
  });

  it('holds a link name to the grammar of link names', () => {
    const slug = collision({ kind: 'slug', name: 'axe', choices: ['rename', 'skip'] });

    expect(choiceProblem(slug, { action: 'rename', name: '' })).toBe('Type a new link name.');
    expect(choiceProblem(slug, { action: 'rename', name: 'two words' })).toMatch(
      /letters, numbers/,
    );
    expect(choiceProblem(slug, { action: 'rename', name: '-axe' })).toMatch(/letters, numbers/);
    expect(choiceProblem(slug, { action: 'rename', name: 'axe-2' })).toBeNull();
  });

  it('counts the clashes that are not settled yet', () => {
    const one = collision();
    const two = collision({ source_id: 'src-2', name: 'Height' });
    const choices = new Map<string, Choice>([[collisionKey(one), { action: 'merge', name: '' }]]);

    expect(unsettled([one, two], choices)).toEqual([two]);
  });
});

describe('the choices as the API takes them', () => {
  it('sends one resolution per clash, with a name only for Keep both', () => {
    const one = collision();
    const two = collision({ kind: 'stat_group', source_id: 'src-2', name: 'Combat' });
    const three = collision({
      kind: 'slug',
      source_id: 'src-3',
      name: 'axe',
      choices: ['rename', 'skip'],
    });
    const choices = new Map<string, Choice>([
      [collisionKey(one), { action: 'merge', name: 'ignored' }],
      [collisionKey(two), { action: 'skip', name: 'ignored' }],
      [collisionKey(three), { action: 'rename', name: '  axe-2 ' }],
    ]);

    expect(resolutionsOf([one, two, three], choices)).toEqual([
      { kind: 'stat_definition', source_id: 'src-1', action: 'merge' },
      { kind: 'stat_group', source_id: 'src-2', action: 'skip' },
      { kind: 'slug', source_id: 'src-3', action: 'rename', name: 'axe-2' },
    ]);
  });

  it('leaves out a clash nothing was chosen for', () => {
    expect(resolutionsOf([collision()], new Map())).toEqual([]);
  });

  it('keeps the clashes it knew, in place, and adds only the new ones', () => {
    const known = [collision()];
    const found = [collision(), collision({ source_id: 'src-9', name: 'Height' })];
    const result = withFound(known, found);

    expect(result.all.map((c) => c.name)).toEqual(['Weight', 'Height']);
    expect(result.added.map((c) => c.name)).toEqual(['Height']);
  });
});

describe('the receipt of a copy', () => {
  it('says what a check-first copy would add, and that nothing has changed', () => {
    expect(receiptSentence(copy(), [], new Map())).toBe(
      'Would add 309 entries, 2 stat groups and 12 stats. Nothing has changed yet.',
    );
  });

  it('adds what was chosen for the clashes', () => {
    const one = collision();
    const two = collision({ source_id: 'src-2', name: 'Height' });
    const three = collision({ kind: 'stat_group', source_id: 'src-3', name: 'Combat' });
    const four = collision({
      kind: 'slug',
      source_id: 'src-4',
      name: 'axe',
      choices: ['rename', 'skip'],
    });
    const choices = new Map<string, Choice>([
      [collisionKey(one), { action: 'merge', name: '' }],
      [collisionKey(two), { action: 'merge', name: '' }],
      [collisionKey(three), { action: 'merge', name: '' }],
      [collisionKey(four), { action: 'rename', name: 'axe-2' }],
    ]);

    expect(receiptSentence(copy(), [one, two, three, four], choices)).toBe(
      'Would add 309 entries, 2 stat groups and 12 stats, use 1 existing stat group, use 2 existing stats, keep both of 1. Nothing has changed yet.',
    );
  });

  it('is in the past once the copy is made, and sums every repository it brought', () => {
    const made = copy({
      dry_run: false,
      steps: [step({ entities: 1 }), step({ name: 'Faerûn', entities: 2, stat_groups: 1 })],
    });
    const skipped = collision();

    expect(
      receiptSentence(
        made,
        [skipped],
        new Map([[collisionKey(skipped), { action: 'skip', name: '' }]]),
      ),
    ).toBe('Added 3 entries, 1 stat group and 0 stats, left out 1.');
  });

  it('describes each repository in one line', () => {
    expect(
      stepLine(
        step({
          name: 'Faerûn',
          entities: 1,
          stat_groups: 1,
          stat_definitions: 2,
          information: 3,
          attachments: 1,
        }),
      ),
    ).toBe(
      'Faerûn: 1 entry, 1 stat group, 2 stats, 3 descriptions and notes, 1 parent added to a repository below',
    );
  });

  it('groups what is left out, by what and why', () => {
    const reason = "its stat group wasn't copied";
    const steps = [
      step({
        dropped: [
          { kind: 'stat_definition', source_id: 'a', reason },
          { kind: 'stat_definition', source_id: 'b', reason },
          { kind: 'entity_stat', source_id: 'c', reason: 'its stat was left out' },
        ],
      }),
    ];

    expect(droppedSentences(steps)).toEqual([
      `2 stats left out: ${reason}.`,
      '1 entity stat left out: its stat was left out.',
    ]);
    expect(droppedSentences([step()])).toEqual([]);
  });
});

describe('copying again', () => {
  it('says the earlier copy stays as the library’s own when both are kept', () => {
    expect(
      previousSentence({
        mode: 'keep',
        entities: 4,
        stat_groups: 1,
        stat_definitions: 3,
        also_removed: {},
      }),
    ).toBe(
      'The earlier copy stays as your own: 4 entries, 1 stat group, 3 stats. They are no longer linked to the repository, so later updates will not touch them.',
    );
  });

  it('counts what a purge also takes of the library’s own work, in words', () => {
    expect(
      previousSentence({
        mode: 'purge',
        entities: 4,
        stat_groups: 1,
        stat_definitions: 3,
        also_removed: { stat_definition: 1, entity_stat: 1, computed_stat: 2, entity_prototype: 1 },
      }),
    ).toBe(
      'The earlier copy is removed: 4 entries, 1 stat group, 3 stats. It also removes 1 stat you added to a copied group, 1 stat value you set, 2 formulas of yours, 1 parent you gave one of your entries.',
    );
  });

  it('says nothing extra when a purge costs nothing of the library’s own', () => {
    expect(alsoRemovedSentence({})).toBeNull();
    expect(alsoRemovedSentence({ entity_stat: 0 })).toBeNull();
  });

  it('never shows a kind it has no words for as an id', () => {
    expect(alsoRemovedSentence({ some_new_kind: 2 })).toBe('It also removes 2 some new kind.');
  });
});

describe('a copy the API refused', () => {
  const refusal = (type: string, status: number, problem: Record<string, unknown> = {}) =>
    new LorenzoApiError('refused', status, type, problem);

  it('reads the clashes it lists', () => {
    const result = copyRefusal(
      refusal('repository-copy-needs-choices', 409, {
        collisions: [
          {
            repository_id: 'r',
            kind: 'slug',
            source_id: 's',
            name: 'axe',
            local_id: null,
            choices: ['rename', 'skip'],
          },
          { nonsense: true },
        ],
      }),
    );

    expect(result).toEqual({
      kind: 'needs-choices',
      collisions: [
        {
          repository_id: 'r',
          kind: 'slug',
          source_id: 's',
          name: 'axe',
          local_id: null,
          choices: ['rename', 'skip'],
        },
      ],
    });
  });

  it('reads the repositories a copy is missing, and what to do about each', () => {
    const result = copyRefusal(
      refusal('repository-copy-needs-grants', 409, {
        missing: [
          { repository_id: 'a', name: 'Core', granted: false, published: true },
          { repository_id: 'b', name: 'Rules', granted: true, published: false },
        ],
      }),
    );

    expect(result?.kind).toBe('needs-grants');

    if (result?.kind !== 'needs-grants') return;

    expect(result.missing.map(missingSentence)).toEqual([
      'Ask the owner of Core to invite your library.',
      'Rules is not published; ask its owner to publish it.',
    ]);
  });

  it('knows a copy that was made already, a formula loop and a choice that cannot work', () => {
    expect(copyRefusal(refusal('repository-already-copied', 409))).toEqual({
      kind: 'already-copied',
    });
    expect(
      copyRefusal(refusal('repository-copy-formula-cycle', 409, { detail: 'A loop' })),
    ).toEqual({ kind: 'formula-cycle', detail: 'A loop' });
    expect(
      copyRefusal(
        refusal('invalid-repository-copy-choice', 422, { detail: "'Mass' is taken here too" }),
      ),
    ).toEqual({ kind: 'bad-choice', detail: "'Mass' is taken here too" });
  });

  it('leaves anything else to be shown as the API worded it', () => {
    expect(copyRefusal(refusal('something-else', 500))).toBeNull();
    expect(copyRefusal(new Error('network'))).toBeNull();
  });
});

describe('the steps', () => {
  it('has a step for the clashes only when there are some', () => {
    expect(wizardSteps(true)).toEqual(['check', 'clashes', 'review', 'done']);
    expect(wizardSteps(false)).toEqual(['check', 'review', 'done']);
  });

  it('numbers them for the steps there are', () => {
    expect(stepHeading('review', true)).toBe('Step 3 of 4: Review');
    expect(stepHeading('review', false)).toBe('Step 2 of 3: Review');
    expect(stepHeading('check', false)).toBe('Step 1 of 3: Check first');
  });
});
