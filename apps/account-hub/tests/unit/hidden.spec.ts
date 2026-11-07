import { describe, expect, it } from 'vitest';
import {
  asInclusion,
  builtOnChoices,
  INCLUSION_CHOICES,
  INCLUSION_LABEL,
  inclusionChangeLine,
  inclusionChangesOf,
  inclusionEffect,
  notHidableReason,
  offeredChoices,
  presetOf,
  presetPatch,
  TERMS_HIDDEN_LABEL,
  termsHiddenLine,
  termsHiddenPatch,
} from '../../src/lib/inclusion';
import type {
  ApplyUpdatesOut,
  BuiltOnSourceOut,
  SubscriberOut,
  UpdatesOut,
} from '../../src/lib/types';
import {
  appliedSentence,
  countsSentence,
  countUpdates,
  hiddenBreakingOf,
  hiddenChanges,
  hiddenConfirmation,
  hiddenSentence,
  todo,
} from '../../src/lib/updates';
import { usingLine } from '../../src/lib/using';

function source(overrides: Partial<BuiltOnSourceOut> = {}): BuiltOnSourceOut {
  return {
    id: 'a',
    name: 'Armoury',
    public: false,
    protected: true,
    owned: false,
    inclusion: 'show',
    includable: { allowed: true, by: 'terms' },
    showable: { allowed: true, by: 'terms' },
    hidable: { allowed: true, by: 'terms' },
    may_be_shown: true,
    may_be_hidden: true,
    in_release: null,
    ...overrides,
  };
}

describe('hiding a repository built on (RFC 0051 H4, ADR 0435)', () => {
  it('is a third choice, in the words of the RFC', () => {
    expect(INCLUSION_CHOICES).toEqual(['show', 'hide', 'include']);
    expect(INCLUSION_LABEL.hide).toBe('Keep separate and hidden');
    expect(asInclusion('hide')).toBe('hide');
    // A word the API adds later is nothing here, never a guess.
    expect(asInclusion('seal')).toBeNull();
    expect(asInclusion(null)).toBeNull();
  });

  it('is offered where the API says it may be, and what is chosen stays offered', () => {
    const yes = { allowed: true };
    const no = { allowed: false };

    expect(offeredChoices(yes, 'show', yes, yes)).toEqual(['show', 'hide', 'include']);
    expect(offeredChoices(yes, 'show', yes, no)).toEqual(['show', 'include']);
    expect(offeredChoices(yes, 'hide', yes, no)).toEqual(['show', 'hide', 'include']);
    // A reply that says nothing of it is an older one: hide is not offered.
    expect(offeredChoices(yes, 'show', yes)).toEqual(['show', 'include']);
  });

  it('says what it does, and that it is not a secret', () => {
    const effect = inclusionEffect('hide', 'Armoury', true, false);

    expect(effect).toContain('Armoury stays a repository of its own');
    expect(effect).toContain('does not see them');
    expect(effect).toContain('still inherit from them');
    expect(effect).toContain('not a secret');
    expect(inclusionEffect('hide', 'Armoury', false, true)).toContain('Anyone can copy it');
    expect(inclusionEffect('hide', 'Armoury', false, true)).not.toContain('not a secret');
  });

  it('says why it is not offered, and offers what is left', () => {
    expect(notHidableReason('Armoury', { allowed: true })).toBeNull();
    expect(notHidableReason('Armoury', undefined)).toBeNull();
    expect(notHidableReason('Armoury', { allowed: false })).toBe(
      'You cannot keep Armoury separate and hidden here: its Owner has asked that what is built on it is not hidden. Keep it separate and visible instead, or ask its Owner.',
    );

    const [offered] = builtOnChoices([source()]);
    const [refused] = builtOnChoices([
      source({ hidable: { allowed: false, by: null }, may_be_hidden: false }),
    ]);
    const [publicOne] = builtOnChoices([source({ public: true, protected: false })]);

    expect(offered?.offered).toEqual(['show', 'hide', 'include']);
    expect(refused?.offered).toEqual(['show', 'include']);
    expect(refused?.notOffered).toContain('You cannot keep Armoury separate and hidden here');
    expect(publicOne?.state).toBe('Public');
    expect(builtOnChoices([source({ inclusion: 'hide' })])[0]?.effect).toContain(
      'does not see them',
    );
    // What the API calls something this client does not know reads as `show`.
    expect(builtOnChoices([source({ inclusion: 'seal' })])[0]?.inclusion).toBe('show');
  });

  it('is a switch of the terms, and a preset says all three', () => {
    expect(TERMS_HIDDEN_LABEL).toBe('May be hidden');
    expect(termsHiddenPatch(false)).toEqual({ terms: { may_be_hidden: false } });
    expect(
      termsHiddenLine({ may_be_hidden: true, may_be_hidden_is_default: true }, 'private'),
    ).toBe('Only a protected repository can say no to this. Make it protected first.');
    expect(
      termsHiddenLine({ may_be_hidden: true, may_be_hidden_is_default: true }, 'protected'),
    ).toContain('Nobody chose: a protected repository may be hidden');
    expect(
      termsHiddenLine({ may_be_hidden: false, may_be_hidden_is_default: false }, 'protected'),
    ).toContain('You did not allow it');
    expect(presetPatch('open').terms.may_be_hidden).toBe(true);
    expect(presetPatch('stay-hidden').terms).toEqual({
      may_be_included: true,
      may_be_shown: false,
      may_be_hidden: true,
    });
    expect(
      presetOf({ may_be_included: true, may_be_shown: true, may_be_hidden: false }, 'protected'),
    ).toBeNull();
  });

  it('is a breaking change when it is changed after a release, in words that say what moves', () => {
    expect(inclusionChangeLine({ name: 'Armoury', before: 'show', after: 'hide' })).toContain(
      'kept separate and hidden now',
    );
    expect(inclusionChangeLine({ name: 'Armoury', before: 'hide', after: 'show' })).toContain(
      'kept separate and visible now',
    );
    expect(inclusionChangeLine({ name: 'Armoury', before: 'hide', after: 'include' })).toContain(
      'is included now',
    );
    expect(inclusionChangeLine({ name: 'Armoury', before: 'include', after: 'hide' })).toContain(
      'was included in the last public release',
    );
    expect(
      inclusionChangesOf({
        inclusion_changes: [
          { repository_id: 'a', name: 'Armoury', before: 'show', after: 'hide' },
          { repository_id: 'b', name: 'Other', before: 'show', after: 'seal' },
        ],
      }).map((change) => change.name),
    ).toEqual(['Armoury']);
  });
});

function updates(hidden: UpdatesOut['hidden']): UpdatesOut {
  return {
    repository_id: 'a',
    changed: [],
    removed: [],
    deleted_locally: [],
    added: [],
    attachments_added: [],
    attachments_removed: [],
    attachments_deleted_locally: [],
    names: {},
    release: null,
    hidden,
  };
}

describe('what an update says of hidden entries', () => {
  const hidden = {
    changed: 1,
    added: 1,
    removed: 1,
    breaking: 1,
    label: '3 changes to hidden entries',
  };

  it('counts them, never names them, and they count as something to take', () => {
    expect(hiddenSentence(1)).toBe('1 change to a hidden entry');
    expect(hiddenSentence(3)).toBe('3 changes to hidden entries');
    expect(hiddenChanges(null)).toBe(0);
    expect(hiddenChanges(undefined)).toBe(0);
    expect(hiddenChanges(hidden)).toBe(3);

    const counts = countUpdates(updates(hidden));

    expect(counts.hidden).toBe(3);
    expect(todo(counts)).toBe(3);
    expect(countsSentence(counts)).toBe('3 changes to hidden entries');
    expect(countsSentence(countUpdates(updates(null)))).toBe('Up to date');
  });

  it('are taken with the rest, and the receipt says so', () => {
    const result: ApplyUpdatesOut = {
      dry_run: false,
      applied: 1,
      added: 0,
      detached: 0,
      attachments_added: 0,
      attachments_detached: 0,
      not_applied: [],
      hidden,
    };

    expect(appliedSentence(result)).toBe('Applied 1 change, took 3 changes to hidden entries.');
    expect(appliedSentence({ ...result, dry_run: true })).toBe(
      'Would apply 1 change, take 3 changes to hidden entries. Nothing has changed yet.',
    );
  });

  it('are acknowledged as one line when a release called them breaking', () => {
    const problem = {
      unconfirmed: [{ kind: 'hidden', name: '2 changes to hidden entries', source_id: null }],
    };

    expect(hiddenBreakingOf(problem)).toBe('2 changes to hidden entries');
    expect(hiddenBreakingOf({ unconfirmed: [{ kind: 'entity', name: 'Longsword' }] })).toBeNull();
    expect(hiddenBreakingOf({})).toBeNull();
    expect(hiddenConfirmation('2 changes to hidden entries')).toBe(
      'A release since this library last updated marked these changes breaking: 2 changes to hidden entries. They are taken with the rest of the update, and their entries stay hidden.\n\nApply the update anyway?',
    );
  });
});

describe('what the Owner of a repository reads of one that hides it', () => {
  it('says so in the list of who built on it', () => {
    const row = {
      name: 'Bridge',
      granted_at: '2026-01-01T00:00:00Z',
      copied_at: '2026-01-02T00:00:00Z',
      synced_at: '2026-01-02T00:00:00Z',
      inclusion: 'hide',
    } as unknown as SubscriberOut;

    expect(usingLine(row)).toContain('keeps it separate and hides it');
  });
});
