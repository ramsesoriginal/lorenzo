import { describe, expect, it } from 'vitest';
import type {
  AddedOut,
  FieldChangeOut,
  NotAppliedOut,
  RowChangeOut,
  UpdatesOut,
} from '../../src/lib/types';
import {
  appliedSentence,
  applyAction,
  attachmentAction,
  attachmentAddedSentence,
  attachmentRemovedSentence,
  breakingConfirmation,
  breakingNotes,
  cleanSelection,
  cleanSentence,
  conflictsSettled,
  countsSentence,
  countUpdates,
  describeField,
  describeRow,
  detachAction,
  formulaText,
  groupUpdates,
  inboxOrder,
  nameOrWord,
  notAppliedSentence,
  releaseMark,
  rowKey,
  todo,
  warningNotes,
} from '../../src/lib/updates';

const names = {
  'e-sword': 'Longsword',
  'e-weapon': 'Weapon',
  'd-str': 'Strength',
  'd-dex': 'Dexterity',
  'g-combat': 'Combat',
  'local:e-mine': 'My sword',
};

function field(overrides: Partial<FieldChangeOut> & { field: string }): FieldChangeOut {
  return {
    label: null,
    state: 'clean',
    base: null,
    upstream: null,
    local: null,
    added: null,
    removed: null,
    ...overrides,
  };
}

function row(
  name: string,
  fields: FieldChangeOut[],
  overrides: Partial<RowChangeOut> = {},
): RowChangeOut {
  return {
    kind: 'entity',
    source_id: `src-${name}`,
    local_id: `loc-${name}`,
    name,
    fields,
    state: null,
    breaking: [],
    ...overrides,
  };
}

function updates(overrides: Partial<UpdatesOut> = {}): UpdatesOut {
  return {
    repository_id: 'repo',
    changed: [],
    removed: [],
    deleted_locally: [],
    added: [],
    attachments_added: [],
    attachments_removed: [],
    attachments_deleted_locally: [],
    names: {},
    release: null,
    ...overrides,
  };
}

function added(name: string, collision: AddedOut['collision'] = null): AddedOut {
  return { kind: 'entity', source_id: `new-${name}`, name, collision, state: null, breaking: [] };
}

describe('names', () => {
  it('uses the name the API gave', () => {
    expect(nameOrWord(names, 'e-sword', 'entry')).toBe('Longsword');
    expect(nameOrWord(names, 'local:e-mine', 'entry')).toBe('My sword');
  });

  it('says what an id with no name was, and never shows the id', () => {
    expect(nameOrWord(names, 'e-gone', 'entry')).toBe('an entry that is gone');
    expect(nameOrWord(names, 'd-gone', 'stat')).toBe('a stat that is gone');
    expect(nameOrWord(names, 'g-gone', 'stat group')).toBe('a stat group that is gone');
    expect(nameOrWord(names, 'local:x', 'stat')).not.toContain('local:');
  });

  it('has nothing to say for no id', () => {
    expect(nameOrWord(names, null, 'entry')).toBe('(none)');
  });
});

describe('a field in words', () => {
  it('shows what it was and what it is now for a value nobody else changed', () => {
    const view = describeField(
      field({ field: 'name', base: 'Sword', upstream: 'Longsword', local: 'Sword' }),
      names,
    );

    expect(view).toMatchObject({
      label: 'Name',
      state: 'clean',
      was: 'Sword',
      now: 'Longsword',
      yours: null,
    });
  });

  it('shows what the library has too when it changed it as well', () => {
    const view = describeField(
      field({
        field: 'name',
        state: 'conflict',
        base: 'Sword',
        upstream: 'Longsword',
        local: 'Blade',
      }),
      names,
    );

    expect(view).toMatchObject({ was: 'Sword', now: 'Longsword', yours: 'Blade' });
  });

  it('reads yes and no, and nothing as none', () => {
    const view = describeField(
      field({ field: 'in_public_catalog', base: false, upstream: true }),
      names,
    );

    expect(view).toMatchObject({ label: 'In the public catalog', was: 'no', now: 'yes' });
    expect(
      describeField(field({ field: 'slug', base: null, upstream: 'longsword' }), names),
    ).toMatchObject({
      label: 'Link name',
      was: '(none)',
      now: 'longsword',
    });
  });

  it('names a stat by its label, and a stat that has none by the names it was given', () => {
    expect(
      describeField(
        field({ field: 'stats:d-str', label: 'Strength', base: 10, upstream: 12 }),
        names,
      ),
    ).toMatchObject({ label: 'Stat: Strength', was: '10', now: '12' });
    expect(describeField(field({ field: 'stats:d-dex', base: 1, upstream: 2 }), names).label).toBe(
      'Stat: Dexterity',
    );
    expect(describeField(field({ field: 'stats:d-gone', base: 1, upstream: 2 }), names).label).toBe(
      'Stat: a stat that is gone',
    );
  });

  it('lists what a set gained and lost, by name', () => {
    const view = describeField(
      field({
        field: 'prototypes',
        added: ['e-weapon', 'local:e-mine', 'e-gone'],
        removed: ['e-sword'],
      }),
      names,
    );

    expect(view).toMatchObject({
      label: 'Inherits from',
      added: ['Weapon', 'My sword', 'an entry that is gone'],
      removed: ['Longsword'],
      was: null,
    });
    expect(
      describeField(field({ field: 'enum_values', added: ['red'], removed: [] }), names),
    ).toMatchObject({
      label: 'Choices',
      added: ['red'],
    });
  });

  it('names the stat group of a stat', () => {
    expect(
      describeField(field({ field: 'stat_group', base: 'g-combat', upstream: 'g-gone' }), names),
    ).toMatchObject({
      label: 'Stat group',
      was: 'Combat',
      now: 'a stat group that is gone',
    });
  });

  it('says why a changed value type cannot be applied', () => {
    const view = describeField(
      field({ field: 'value_type', state: 'not_applicable', base: 'int', upstream: 'float' }),
      names,
    );

    expect(view.note).toMatch(/change it by hand/);
    expect(view).toMatchObject({ label: 'Value type', was: 'int', now: 'float' });
  });

  it('gives a field it has no words for a readable label', () => {
    expect(
      describeField(field({ field: 'some_new_field', base: 1, upstream: 2 }), names).label,
    ).toBe('Some new field');
  });
});

describe('a formula in words', () => {
  it('reads a linear formula with its offset and rounding', () => {
    expect(
      formulaText(
        {
          kind: 'linear',
          source: 'd-str',
          multiplier: '0.5000',
          offset: '-5.0',
          round_mode: 'floor',
        },
        names,
      ),
    ).toBe('Strength × 0.5 − 5, rounded down');
    expect(
      formulaText(
        { kind: 'linear', source: 'd-str', multiplier: '1', offset: '0', round_mode: 'none' },
        names,
      ),
    ).toBe('Strength × 1');
  });

  it('reads a sum', () => {
    expect(
      formulaText(
        {
          kind: 'sum',
          terms: [
            { source: 'd-str', coefficient: '1' },
            { source: 'd-dex', coefficient: '2.0' },
          ],
          offset: '10',
          round_mode: 'none',
        },
        names,
      ),
    ).toBe('1 × Strength + 2 × Dexterity + 10');
  });

  it('reads what is held, and a comparison', () => {
    expect(formulaText({ kind: 'contents', source: 'd-str' }, names)).toBe(
      'the total of Strength in what it holds',
    );
    expect(
      formulaText(
        {
          kind: 'comparison',
          left: 'd-str',
          comparator: 'ge',
          right: null,
          right_constant: '15',
          true_value: 'strong',
          false_value: 'weak',
        },
        names,
      ),
    ).toBe('Strength is at least 15: strong, otherwise weak');
  });

  it('shows a stat that is gone as a word, not an id', () => {
    expect(formulaText({ kind: 'contents', source: 'd-gone' }, names)).toBe(
      'the total of a stat that is gone in what it holds',
    );
  });

  it('shows a field of a formula that changed', () => {
    const view = describeField(
      field({
        field: 'formulas:d-dex',
        base: { kind: 'contents', source: 'd-str' },
        upstream: {
          kind: 'linear',
          source: 'd-str',
          multiplier: '2',
          offset: '0',
          round_mode: 'none',
        },
      }),
      names,
    );

    expect(view).toMatchObject({
      label: 'Formula: Dexterity',
      was: 'the total of Strength in what it holds',
      now: 'Strength × 2',
    });
  });
});

describe('a row', () => {
  it('has its conflicts apart, and says whether there is anything to apply', () => {
    const view = describeRow(
      row('Sword', [
        field({ field: 'name', base: 'a', upstream: 'b', local: 'a' }),
        field({ field: 'slug', state: 'conflict', base: 'x', upstream: 'y', local: 'z' }),
      ]),
      names,
    );

    expect(view).toMatchObject({ kindLabel: 'Entry', name: 'Sword', appliable: true });
    expect(view.conflicts.map((c) => c.field)).toEqual(['slug']);
    expect(view.key).toBe(rowKey({ kind: 'entity', source_id: 'src-Sword' }));
  });

  it('has nothing to apply when its only change is a value type', () => {
    const view = describeRow(
      row(
        'Weight',
        [field({ field: 'value_type', state: 'not_applicable', base: 'int', upstream: 'float' })],
        {
          kind: 'stat_definition',
        },
      ),
      names,
    );

    expect(view.appliable).toBe(false);
    expect(view.kindLabel).toBe('Stat');
  });
});

describe('the groups and what they count', () => {
  const clean = row('Clean', [field({ field: 'name', base: 'a', upstream: 'b', local: 'a' })]);
  const conflicted = row('Conflicted', [
    field({ field: 'name', state: 'conflict', base: 'a', upstream: 'b', local: 'c' }),
  ]);
  const all = updates({
    changed: [clean, conflicted],
    added: [added('One'), added('Two')],
    removed: [
      { kind: 'entity', source_id: 'r', local_id: 'l', name: 'Gone', state: null, breaking: [] },
    ],
    attachments_added: [
      {
        child_source_id: 'c',
        child_local_id: 'lc',
        child_name: 'Dagger',
        parent_source_id: 'p',
        parent_local_id: 'lp',
        parent_name: 'Weapon',
        applicable: true,
        reason: null,
        state: null,
        breaking: [],
        warnings: [],
      },
    ],
  });

  it('puts a row the library changed too under conflicts, and the rest under changed', () => {
    const groups = groupUpdates(all);

    expect(groups.changed.map((r) => r.name)).toEqual(['Clean']);
    expect(groups.conflicts.map((r) => r.name)).toEqual(['Conflicted']);
  });

  it('counts them, and says them in words', () => {
    const counts = countUpdates(all);

    expect(counts).toEqual({ changed: 1, new: 2, removed: 1, conflicts: 1, parents: 1 });
    expect(todo(counts)).toBe(6);
    expect(countsSentence(counts)).toBe(
      '1 changed, 2 new, 1 removed upstream, 1 conflict, 1 parent added or removed',
    );
    expect(countsSentence(countUpdates(updates()))).toBe('Up to date');
  });

  it('orders the inbox by what there is to do, then by name', () => {
    const rows = [
      { name: 'B', counts: countUpdates(updates()) },
      { name: 'A', counts: countUpdates(all) },
      { name: 'C', counts: null },
      { name: 'Z', counts: countUpdates(all) },
    ];

    expect(inboxOrder(rows).map((r) => r.name)).toEqual(['A', 'Z', 'B', 'C']);
  });
});

describe('apply all clean', () => {
  const clean = row('Clean', [field({ field: 'name', base: 'a', upstream: 'b', local: 'a' })]);
  const conflicted = row('Conflicted', [
    field({ field: 'name', state: 'conflict', base: 'a', upstream: 'b', local: 'c' }),
  ]);
  const onlyType = row(
    'Type',
    [field({ field: 'value_type', state: 'not_applicable', base: 'int', upstream: 'float' })],
    {
      kind: 'stat_definition',
    },
  );
  const clash = added('Clash', {
    repository_id: 'r',
    kind: 'slug',
    source_id: 's',
    name: 'clash',
    local_id: null,
    choices: ['rename', 'skip'],
  });
  const all = updates({
    changed: [clean, conflicted, onlyType],
    added: [added('Free'), clash],
    removed: [
      { kind: 'entity', source_id: 'r', local_id: 'l', name: 'Gone', state: null, breaking: [] },
    ],
  });

  it('takes the rows nothing is chosen about, and leaves the rest', () => {
    const selection = cleanSelection(all);

    expect(selection.actions).toEqual([
      { kind: 'entity', source_id: 'src-Clean', action: 'apply' },
      { kind: 'entity', source_id: 'new-Free', action: 'add' },
    ]);
    expect(selection).toMatchObject({ changed: 1, added: 1 });
    expect(selection.left).toEqual({
      conflicts: 1,
      collisions: 1,
      removed: 1,
      parents: 0,
      edited: 0,
      breaking: 0,
    });
  });

  it('never takes a conflict, a clash, a removal or a parent, and not what was skipped', () => {
    const selection = cleanSelection(all, new Set([rowKey(clean)]));

    expect(selection.actions.map((a) => a.action)).toEqual(['add']);
  });

  it('says what it will do and what it leaves', () => {
    expect(cleanSentence(cleanSelection(all))).toBe(
      'Apply 1 change and 1 new. Left for you to decide: 1 conflict, 1 new with a name clash, 1 removed upstream.',
    );
    expect(cleanSentence(cleanSelection(updates()))).toBe('There is nothing clean to apply.');
  });
});

describe('the actions as the API takes them', () => {
  const target = { kind: 'entity' as const, source_id: 'src-1' };

  it('applies a row with each conflict named', () => {
    const choices = new Map<string, 'keep' | 'take'>([
      ['name', 'keep'],
      ['slug', 'take'],
    ]);

    expect(applyAction(target, choices)).toEqual({
      ...target,
      action: 'apply',
      keep_local: ['name'],
      take_upstream: ['slug'],
    });
    expect(applyAction(target, new Map())).toEqual({ ...target, action: 'apply' });
  });

  it('knows when every conflict is named', () => {
    const view = describeRow(
      row('Sword', [
        field({ field: 'name', state: 'conflict', base: 'a', upstream: 'b', local: 'c' }),
        field({ field: 'slug', state: 'conflict', base: 'a', upstream: 'b', local: 'c' }),
      ]),
      names,
    );

    expect(conflictsSettled(view, new Map([['name', 'keep']]))).toBe(false);
    expect(
      conflictsSettled(
        view,
        new Map([
          ['name', 'keep'],
          ['slug', 'take'],
        ] as const),
      ),
    ).toBe(true);
  });

  it('detaches, and adds or detaches a parent by the two origin ids', () => {
    expect(detachAction(target)).toEqual({ ...target, action: 'detach' });
    expect(attachmentAction({ child_source_id: 'c', parent_source_id: 'p' }, 'add')).toEqual({
      child_source_id: 'c',
      parent_source_id: 'p',
      action: 'add',
    });
  });

  it('says a parent in a sentence, since there is no noun for it', () => {
    const attachment = {
      child_source_id: 'c',
      child_local_id: 'lc',
      child_name: 'Dagger',
      parent_source_id: 'p',
      parent_local_id: null,
      parent_name: 'Weapon',
    };

    expect(attachmentAddedSentence(attachment)).toBe('“Dagger” would inherit from “Weapon”.');
    expect(attachmentRemovedSentence(attachment)).toBe(
      '“Dagger” no longer inherits from “Weapon” in the repository.',
    );
  });
});

describe('what an apply did', () => {
  const result = {
    dry_run: true,
    applied: 14,
    added: 12,
    detached: 1,
    attachments_added: 0,
    attachments_detached: 0,
    not_applied: [],
  };

  it('says what a check would do, and that nothing has changed', () => {
    expect(appliedSentence(result)).toBe(
      'Would apply 14 changes, add 12 new, detach 1. Nothing has changed yet.',
    );
  });

  it('says what was done', () => {
    expect(appliedSentence({ ...result, dry_run: false, attachments_added: 2 })).toBe(
      'Applied 14 changes, added 12 new, detached 1, added 2 parents.',
    );
  });

  it('says so when nothing came of it', () => {
    expect(appliedSentence({ ...result, dry_run: false, applied: 0, added: 0, detached: 0 })).toBe(
      'Nothing was applied.',
    );
  });

  it('says what could not be applied, and that it is offered again', () => {
    const entry: NotAppliedOut = {
      kind: 'entity',
      source_id: 's',
      field: 'slug',
      reason: "The slug 'axe' is taken here",
      name: 'Axe',
      label: null,
    };

    expect(notAppliedSentence(entry)).toBe(
      "Axe: link name was left as it is. The slug 'axe' is taken here. It is offered again next time.",
    );
    expect(
      notAppliedSentence({
        ...entry,
        field: 'stats:d-str',
        label: 'Strength',
        reason: 'its stat was not copied.',
      }),
    ).toBe(
      'Axe: the value of Strength was left as it is. its stat was not copied. It is offered again next time.',
    );
  });
});

describe('apply all clean and the releases', () => {
  const note = (label: string, detail = 'A parent was added.') => ({
    reason: 'attachment_added' as const,
    detail,
    release: { id: `r-${label}`, number: 1, label },
  });
  const clean = (name: string, over: Partial<RowChangeOut> = {}) =>
    row(name, [field({ field: 'name', base: 'a', upstream: 'b', local: 'a' })], over);

  it('takes rows of the latest release and rows from before releases, not rows edited since', () => {
    const selection = cleanSelection(
      updates({
        changed: [
          clean('Released', { state: 'released' }),
          clean('Before'),
          clean('Edited', { state: 'edited' }),
        ],
      }),
    );

    expect(selection.actions.map((a) => a.source_id)).toEqual(['src-Released', 'src-Before']);
    expect(selection.left).toMatchObject({ edited: 1, breaking: 0 });
  });

  it('never takes a row a release called breaking, whether or not it is released', () => {
    const selection = cleanSelection(
      updates({
        changed: [clean('Breaks', { state: 'released', breaking: [note('1.3')] })],
        added: [{ ...added('NewBreaks'), breaking: [note('1.3')] }, added('Fine')],
      }),
    );

    expect(selection.actions.map((a) => a.source_id)).toEqual(['new-Fine']);
    expect(selection.left).toMatchObject({ edited: 0, breaking: 2 });
  });

  it('says what it leaves for the release rule, in words', () => {
    const selection = cleanSelection(
      updates({
        changed: [clean('Fine'), clean('Edited', { state: 'edited' })],
        added: [{ ...added('NewBreaks'), breaking: [note('1.3')] }],
      }),
    );

    expect(cleanSentence(selection)).toBe(
      'Apply 1 change. Left for you to decide: 1 edited since the release, 1 marked breaking.',
    );
  });

  it('marks a row against the latest release, in the words of the rule', () => {
    expect(releaseMark({ state: 'released' }, '1.3')).toBe('In release 1.3');
    expect(releaseMark({ state: 'edited' }, '1.3')).toBe('Edited since release 1.3');
    expect(releaseMark({ state: null }, '1.3')).toBeNull();
    expect(releaseMark({ state: 'released' }, null)).toBeNull();
  });

  it('says what a release warned of an attachment, as a note and not as a question', () => {
    expect(warningNotes([note('1.3', '“Silvered” was added as a parent of “Dagger”.')])).toEqual([
      'Warning in release 1.3: “Silvered” was added as a parent of “Dagger”.',
    ]);
    expect(warningNotes([])).toEqual([]);
  });

  it('says what a release called breaking, and asks before it is applied', () => {
    expect(breakingNotes([note('1.3', '“Club” was removed.')])).toEqual([
      'Breaking in release 1.3: “Club” was removed.',
    ]);
    expect(breakingConfirmation([note('1.3', '“Club” was removed.')])).toBe(
      'Breaking in release 1.3: “Club” was removed.\n\nApply it anyway? Your library takes this change as the repository made it.',
    );
  });

  it('confirms only where asked to, and only an action that can break', () => {
    const target = { kind: 'entity' as const, source_id: 'src-1' };

    expect(applyAction(target, new Map(), true)).toEqual({
      ...target,
      action: 'apply',
      confirm: true,
    });
    expect(applyAction(target, new Map())).toEqual({ ...target, action: 'apply' });
    // An attachment is never confirmed: a release only warned of it, and naming it is the decision.
    expect(attachmentAction({ child_source_id: 'c', parent_source_id: 'p' }, 'detach')).toEqual({
      child_source_id: 'c',
      parent_source_id: 'p',
      action: 'detach',
    });
  });
});
