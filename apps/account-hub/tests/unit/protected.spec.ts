import { describe, expect, it } from 'vitest';
import {
  BUILT_ON_CHOICES_TITLE,
  builtOnChoices,
  inclusionEffect,
  notShowableReason,
  offeredChoices,
  presetOf,
  presetPatch,
  TERMS_PRESETS,
  TERMS_SHOWN_LABEL,
  termsLine,
  termsShownLine,
  termsShownPatch,
} from '../../src/lib/inclusion';
import {
  PROTECTED_NOTE,
  PROTECTED_PILL,
  SHELF_STATE_EXPLANATION,
  SHELF_STATE_LABEL,
} from '../../src/lib/shelf';
import type { BuiltOnSourceOut, FlipCheckOut, SubscriptionOut } from '../../src/lib/types';
import { builtOn } from '../../src/lib/using';
import {
  changedUnderTheDialog,
  makePrivateLines,
  makeProtectedBody,
  makeProtectedConfirm,
  makeProtectedLines,
  makeProtectedProblem,
  makeProtectedTitle,
  makeProtectedWarnings,
  privateBlockers,
  protectedAcknowledgement,
  visibilityCard,
} from '../../src/lib/visibility';

function check(overrides: Partial<FlipCheckOut> = {}): FlipCheckOut {
  return {
    available: true,
    visibility: 'private',
    has_summary: false,
    listed: true,
    built_on_not_public: [],
    built_on_behind: [],
    built_on: [],
    public_dependents: [],
    public_libraries: 0,
    invited_libraries: 0,
    publishers: [{ display_name: 'Ada Author' }],
    ...overrides,
  };
}

const form = { label: '', notes: '', breaking: false, acknowledged: false };

describe('the card of a protected repository (RFC 0051 H3, ADR 0434)', () => {
  it('is on a card of its own, with the way to public and the way to private', () => {
    const card = visibilityCard(check({ visibility: 'protected' }), 'owner');

    expect(card?.label).toBe('Protected');
    expect(card?.visibility).toBe('protected');
    expect(card?.button).toBe('Make public…');
    expect(card?.mode).toBe('public');
    expect(card?.alt).toEqual({ mode: 'private', label: 'Make private…', disabled: false });
    expect(card?.disabled).toBe(false);
    expect(card?.listed).toBeNull();
    // It says what protected means: off Discover, not copied on its own, read through another.
    expect(card?.sentence).toContain('Not on Discover');
    expect(card?.sentence).toContain('public repository built on it');
  });

  it('is shown whether or not the deployment has public repositories, so that it can be made private', () => {
    expect(
      visibilityCard(check({ visibility: 'protected', available: false }), 'owner'),
    ).not.toBeNull();
  });

  it('has a second button on a private and on a public repository: the way to protected', () => {
    const privateCard = visibilityCard(check(), 'owner');
    const publicCard = visibilityCard(check({ visibility: 'public' }), 'owner');

    expect(privateCard?.mode).toBe('public');
    expect(privateCard?.alt).toEqual({
      mode: 'protected',
      label: 'Make protected…',
      disabled: false,
    });
    expect(publicCard?.mode).toBe('private');
    expect(publicCard?.alt).toEqual({
      mode: 'protected',
      label: 'Make protected…',
      disabled: false,
    });
  });

  it('cannot be made public or protected while it is off Discover or retired, and can be made private', () => {
    const delisted = { reason: 'x', at: '2026-10-15T09:00:00Z' };
    const deprecated = { message: null, at: '2026-11-03T09:00:00Z' };

    for (const closed of [{ delisted }, { deprecated }]) {
      const protectedCard = visibilityCard(check({ visibility: 'protected', ...closed }), 'owner');

      expect(protectedCard?.disabled).toBe(true);
      expect(protectedCard?.alt).toEqual({
        mode: 'private',
        label: 'Make private…',
        disabled: false,
      });
      expect(visibilityCard(check({ ...closed }), 'owner')?.alt?.disabled).toBe(true);
      // Public: "Make private…" stays, and the way to protected goes.
      expect(visibilityCard(check({ visibility: 'public', ...closed }), 'owner')?.alt).toBeNull();
    }
  });

  it('is only an Owner’s', () => {
    expect(visibilityCard(check({ visibility: 'protected' }), 'orga')).toBeNull();
    expect(visibilityCard(check({ visibility: 'protected' }), 'author')).toBeNull();
  });
});

describe('the "Make protected" dialog', () => {
  it('says what making it protected does, for a private and for a public repository', () => {
    const fromPrivate = makeProtectedLines(
      check({ visibility: 'private', invited_libraries: 2 }),
      'Armoury',
    );
    const fromPublic = makeProtectedLines(check({ visibility: 'public' }), 'Armoury');

    expect(fromPrivate[0]).toContain('publishes a release of it');
    expect(fromPrivate.join(' ')).toContain('nobody copies it on its own');
    expect(fromPrivate.join(' ')).toContain('2 libraries have an invitation and are told');
    expect(fromPublic[0]).toContain('leaves Discover');
    expect(fromPublic.join(' ')).not.toContain('publishes a release');
    expect(makeProtectedTitle('Armoury')).toBe('Make Armoury protected');
    expect(makeProtectedConfirm('private')).toBe('Make protected and publish release');
    expect(makeProtectedConfirm('public')).toBe('Make protected');
    expect(makeProtectedWarnings()[0]).toContain('GM only');
  });

  it('asks to be acknowledged only for a public repository that libraries copied by themselves', () => {
    expect(protectedAcknowledgement(check({ visibility: 'private', public_libraries: 3 }))).toBe(
      null,
    );
    expect(protectedAcknowledgement(check({ visibility: 'public', public_libraries: 0 }))).toBe(
      null,
    );
    expect(
      protectedAcknowledgement(check({ visibility: 'public', public_libraries: 3 })),
    ).toContain('3 libraries will get the updates of this repository only through a public');

    const publicOne = check({ visibility: 'public', public_libraries: 2 });

    expect(makeProtectedProblem(form, [], publicOne, false)).toContain('Say you understand');
    expect(makeProtectedProblem(form, [], publicOne, true)).toBeNull();
    // A private one needs what a release needs, and nothing else.
    expect(makeProtectedProblem({ ...form, label: 'x'.repeat(81) }, [], check(), false)).not.toBe(
      null,
    );
    expect(makeProtectedProblem(form, [], check(), false)).toBeNull();
  });

  it('sends a release for a private repository and the acknowledgement for a public one', () => {
    expect(makeProtectedBody({ ...form, label: '1.0' }, [], check(), false)).toEqual({
      label: '1.0',
      breaking: false,
      acknowledge_breaking: false,
      acknowledge_revokes: false,
    });
    expect(
      makeProtectedBody(form, [], check({ visibility: 'public', public_libraries: 2 }), true),
    ).toEqual({ breaking: false, acknowledge_breaking: false, acknowledge_revokes: true });
    // Nobody to tell, nothing to acknowledge.
    expect(
      makeProtectedBody(form, [], check({ visibility: 'public', public_libraries: 0 }), true),
    ).toEqual({ breaking: false, acknowledge_breaking: false, acknowledge_revokes: false });
  });

  it('is a reason to read the dialog again when something changed under it', () => {
    expect(changedUnderTheDialog('repository-not-showable')).toBe(true);
    expect(changedUnderTheDialog('repository-already-protected')).toBe(true);
    expect(changedUnderTheDialog('public-copies-would-be-cut-off')).toBe(true);
  });

  it('says in the private dialog that a protected repository nobody shows loses nothing', () => {
    expect(makePrivateLines(check({ visibility: 'protected' }))[0]).toContain(
      'No public repository is built on it that shows it',
    );
  });

  it('uses the words of the RFC and never the words of the tables', () => {
    const said = [
      visibilityCard(check({ visibility: 'protected' }), 'owner')?.sentence,
      ...makeProtectedLines(check({ visibility: 'private' }), 'Armoury'),
      ...makeProtectedLines(check({ visibility: 'public' }), 'Armoury'),
      ...makeProtectedWarnings(),
      protectedAcknowledgement(check({ visibility: 'public', public_libraries: 2 })),
      ...privateBlockers(
        check({
          visibility: 'protected',
          public_dependents: [
            { id: 'a', name: 'Dragons', owned: true },
            { id: 'b', name: 'Giants', owned: false },
          ],
        }),
      ).map((blocker) => blocker.text),
    ].join('\n');

    expect(said).not.toMatch(/tenant|grant|subscri|flatten|source/i);
    expect(said).toContain('protected');
  });
});

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
    may_be_shown: true,
    may_be_hidden: true,
    in_release: null,
    ...overrides,
  };
}

describe('the choices of a repository built on a protected one', () => {
  it('offers both while its terms allow both', () => {
    const [choice] = builtOnChoices([source()]);

    expect(choice?.state).toBe('Protected');
    expect(choice?.protected).toBe(true);
    expect(choice?.offered).toEqual(['show', 'include']);
    expect(choice?.notOffered).toBeNull();
    expect(choice?.effect).toContain('stays a protected repository of its own');
  });

  it('leaves include where the terms say stay hidden, and says why', () => {
    const [choice] = builtOnChoices([
      source({ showable: { allowed: false, by: null }, may_be_shown: false, inclusion: 'include' }),
    ]);

    expect(choice?.offered).toEqual(['include']);
    expect(choice?.notOffered).toContain('You cannot keep Armoury separate and visible here');
    expect(choice?.notOffered).toContain('Include it in this repository instead');
  });

  it('offers neither where it may not be shown and may not be included, and says both', () => {
    const [choice] = builtOnChoices([
      source({
        showable: { allowed: false, by: null },
        includable: { allowed: false, by: null },
        inclusion: 'show',
      }),
    ]);

    // What is chosen stays offered, so that it shows as chosen.
    expect(choice?.offered).toEqual(['show']);
    expect(choice?.notOffered).toContain('You cannot include Armoury here');
    expect(choice?.notOffered).toContain('You cannot keep Armoury separate and visible here');
  });

  it('is offered everything to an Owner of it', () => {
    const [choice] = builtOnChoices([
      source({
        owned: true,
        showable: { allowed: true, by: 'owner' },
        includable: { allowed: true, by: 'owner' },
      }),
    ]);

    expect(choice?.offered).toEqual(['show', 'include']);
  });

  it('keeps what was chosen offered, and names a public, a private and a protected source', () => {
    expect(offeredChoices({ allowed: true }, 'include', { allowed: false })).toEqual(['include']);
    expect(offeredChoices({ allowed: false }, 'show', { allowed: true })).toEqual(['show']);
    expect(builtOnChoices([source({ protected: false, public: true })])[0]?.state).toBe('Public');
    expect(builtOnChoices([source({ protected: false, public: false })])[0]?.state).toBe('Private');
    expect(notShowableReason('Armoury', { allowed: true })).toBeNull();
    expect(notShowableReason('Armoury', undefined)).toBeNull();
    expect(inclusionEffect('show', 'Armoury')).toContain('has to be one the library can read');
    expect(BUILT_ON_CHOICES_TITLE).toBe('How this repository carries what it is built on');
  });
});

describe('A’s terms: the presets and the switch', () => {
  it('are two, in the words of the RFC', () => {
    expect(TERMS_PRESETS.map((preset) => preset.label)).toEqual(['Open', 'Stay hidden']);
    expect(TERMS_SHOWN_LABEL).toBe('May be shown');
  });

  it('set both switches, so that a preset is the same whatever was said before', () => {
    expect(presetPatch('open')).toEqual({
      terms: { may_be_included: true, may_be_shown: true, may_be_hidden: true },
    });
    expect(presetPatch('stay-hidden')).toEqual({
      terms: { may_be_included: true, may_be_shown: false, may_be_hidden: true },
    });
    expect(termsShownPatch(false)).toEqual({ terms: { may_be_shown: false } });
  });

  it('are read from the switches, and none where they say something else', () => {
    const terms = { may_be_included: true, may_be_shown: true, may_be_hidden: true };

    expect(presetOf(terms, 'protected')).toBe('open');
    expect(presetOf({ ...terms, may_be_shown: false }, 'protected')).toBe('stay-hidden');
    expect(presetOf({ ...terms, may_be_included: false }, 'protected')).toBeNull();
    // A repository that may not be hidden is neither preset (RFC 0051 H4).
    expect(presetOf({ ...terms, may_be_hidden: false }, 'protected')).toBeNull();
    // Only a protected repository can stay hidden: what a private one said is not a preset.
    expect(presetOf({ ...terms, may_be_shown: false }, 'private')).toBeNull();
  });

  it('say who chose, and that only a protected repository can say no', () => {
    expect(
      termsShownLine({ may_be_shown: true, may_be_shown_is_default: true }, 'protected'),
    ).toContain('Nobody chose: a protected repository may be shown');
    expect(
      termsShownLine({ may_be_shown: false, may_be_shown_is_default: false }, 'protected'),
    ).toContain('You did not allow it');
    expect(
      termsShownLine({ may_be_shown: true, may_be_shown_is_default: false }, 'protected'),
    ).toContain('You allowed it');
    expect(
      termsShownLine({ may_be_shown: true, may_be_shown_is_default: true }, 'public'),
    ).toContain('Only a protected repository can say no');
    expect(termsLine({ may_be_included: true, is_default: true }, 'protected')).toContain(
      'a protected repository may be included',
    );
    // Without a visibility it says what it said before.
    expect(termsLine({ may_be_included: true, is_default: true })).toContain('a public repository');
  });
});

function subscription(overrides: Partial<SubscriptionOut> = {}): SubscriptionOut {
  return {
    repository: {
      id: 'a',
      name: 'A protected repository',
      slug: '',
      description: '',
      published_at: '2026-11-01T09:00:00Z',
    },
    granted_at: '2026-11-01T09:00:00Z',
    copied_at: '2026-11-02T09:00:00Z',
    synced_at: '2026-11-02T09:00:00Z',
    contributed: null,
    synced_release: null,
    current_release: null,
    protected: true,
    ...overrides,
  } as SubscriptionOut;
}

describe('Shelf and the built-on list', () => {
  it('say Protected, and that it cannot be copied on its own', () => {
    expect(PROTECTED_PILL).toBe('Protected');
    expect(PROTECTED_NOTE).toContain('cannot be copied on its own');
    expect(`${PROTECTED_NOTE}`).not.toMatch(/tenant|grant|subscri|flatten|source/i);
    // The states are as they were: the pill is beside them.
    expect(SHELF_STATE_LABEL.copied).toBe('Copied');
    expect(SHELF_STATE_EXPLANATION.copied).toContain('has copied this repository');
  });

  it('carries whether a repository it built on is protected and whether it may be shown', () => {
    const [row] = builtOn([
      subscription({
        inclusion: 'show',
        includable: { allowed: true, by: 'terms' },
        showable: { allowed: false, by: null },
      }),
    ]);

    expect(row?.protected).toBe(true);
    expect(row?.showable).toEqual({ allowed: false, by: null });
    expect(row?.name).toBe('A protected repository');
    expect(builtOn([subscription({ protected: false })])[0]?.protected).toBe(false);
  });
});
