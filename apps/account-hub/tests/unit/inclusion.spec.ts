import { describe, expect, it } from 'vitest';
import {
  BREAKING_NOTE,
  BUILT_ON_CHOICES_TITLE,
  breakingNote,
  builtOnChoices,
  INCLUSION_LABEL,
  includesFacts,
  includesLine,
  includesLines,
  inclusionChangeLine,
  inclusionChangeLines,
  inclusionChangesOf,
  inclusionEffect,
  inclusionSaved,
  notOfferedReason,
  offeredChoices,
  TERMS_HEADING,
  TERMS_INCLUDE_LABEL,
  termsLine,
  termsPatch,
} from '../../src/lib/inclusion';
import type { BuiltOnSourceOut, InclusionOut } from '../../src/lib/types';

const WORDS_NEVER_ON_SCREEN = /tenant|grant|subscri|flatten|\bsource/i;

function source(overrides: Partial<BuiltOnSourceOut> = {}): BuiltOnSourceOut {
  return {
    id: 'a-1',
    name: 'Armoury',
    public: false,
    owned: true,
    inclusion: 'show',
    includable: { allowed: true, by: 'owner' },
    in_release: null,
    protected: false,
    may_be_shown: true,
    may_be_hidden: true,
    ...overrides,
  };
}

describe('the words of the choice', () => {
  it('are the ones of the RFC', () => {
    expect(INCLUSION_LABEL).toEqual({
      show: 'Keep separate and visible',
      include: 'Include in this repository',
      hide: 'Keep separate and hidden',
    });
    expect(TERMS_HEADING).toBe('How repositories built on this one may use it');
    expect(TERMS_INCLUDE_LABEL).toBe('May be included');
    expect(BREAKING_NOTE).toBe('Changing how this is included makes a breaking release.');
  });

  it('say what each does, to the library and to the Owner, and never the words kept off the screen', () => {
    const include = inclusionEffect('include', 'Armoury');
    const show = inclusionEffect('show', 'Armoury');

    expect(include).toContain('The entries of Armoury become this repository’s own');
    expect(include).toContain('never reads it');
    expect(include).toContain('is not changed, and you keep taking its updates');
    expect(show).toContain('stays a repository of its own');
    expect(show).toContain('is given Armoury too');
    for (const text of [include, show, BREAKING_NOTE, TERMS_HEADING]) {
      expect(text).not.toMatch(WORDS_NEVER_ON_SCREEN);
    }
  });
});

describe('what is offered, and why not', () => {
  it('offers both where the user may include it', () => {
    expect(offeredChoices({ allowed: true }, 'show')).toEqual(['show', 'include']);
    expect(notOfferedReason('Armoury', { allowed: true })).toBeNull();
  });

  it('leaves out include where the user may not, and says why, naming the repository', () => {
    expect(offeredChoices({ allowed: false }, 'show')).toEqual(['show']);

    const reason = notOfferedReason('Armoury', { allowed: false });

    expect(reason).toContain('You cannot include Armoury here');
    expect(reason).toContain('Ask its Owner to turn on “May be included”');
    expect(reason).not.toMatch(WORDS_NEVER_ON_SCREEN);
  });

  it('keeps what is already chosen offered, so that it shows as chosen', () => {
    expect(offeredChoices({ allowed: false }, 'include')).toEqual(['show', 'include']);
  });

  it('offers include to nobody it knows nothing about', () => {
    expect(offeredChoices(null, 'show')).toEqual(['show']);
    expect(notOfferedReason('Armoury', null)).toBeNull();
  });
});

describe('changing it after a release carried it', () => {
  it('says the next release is breaking only once one carried it', () => {
    expect(breakingNote({ inclusion_in_release: null })).toBeNull();
    expect(breakingNote({ inclusion_in_release: 'include' })).toBe(BREAKING_NOTE);
    expect(breakingNote({ inclusion_in_release: 'show' })).toBe(BREAKING_NOTE);
    expect(breakingNote(source({ in_release: 'show' }))).toBe(BREAKING_NOTE);
    expect(breakingNote(source())).toBeNull();
  });

  it('is said when a choice was saved', () => {
    const answer = (breaking: boolean): InclusionOut => ({
      repository_id: 'a-1',
      name: 'Armoury',
      inclusion: 'include',
      includable: { allowed: true, by: 'owner' },
      inclusion_in_release: 'show',
      breaking_next_release: breaking,
    });

    expect(inclusionSaved(answer(false))).toBe('Saved.');
    expect(inclusionSaved(answer(true))).toContain(BREAKING_NOTE);
  });

  it('reads each repository carried differently in words, for the release that is breaking', () => {
    const toInclude = inclusionChangeLine({ name: 'Armoury', before: 'show', after: 'include' });
    const toShow = inclusionChangeLine({ name: 'Armoury', before: 'include', after: 'show' });

    expect(toInclude).toContain('was kept separate in the last public release and is included now');
    expect(toShow).toContain('was included in the last public release and is kept separate now');
    expect(toInclude).not.toMatch(WORDS_NEVER_ON_SCREEN);
    expect(toShow).not.toMatch(WORDS_NEVER_ON_SCREEN);
    expect(inclusionChangeLines(undefined)).toEqual([]);
  });

  it('reads them from the API’s refusal, and nothing else', () => {
    const change = { repository_id: 'a-1', name: 'Armoury', before: 'show', after: 'include' };

    expect(inclusionChangesOf({ inclusion_changes: [change] })).toEqual([change]);
    expect(inclusionChangesOf({ inclusion_changes: [{ name: 3 }, null, 'x'] })).toEqual([]);
    expect(inclusionChangesOf({ inclusion_changes: 'no' })).toEqual([]);
    expect(inclusionChangesOf({})).toEqual([]);
  });
});

describe('the terms', () => {
  it('say who chose, and what they follow when nobody did', () => {
    expect(termsLine({ may_be_included: true, is_default: false })).toContain('You allowed it');
    expect(termsLine({ may_be_included: false, is_default: false })).toContain(
      'You did not allow it',
    );
    expect(termsLine({ may_be_included: true, is_default: true })).toContain(
      'a public repository may be included',
    );
    expect(termsLine({ may_be_included: false, is_default: true })).toContain(
      'a private repository may not be included',
    );
  });

  it('are sent as the one switch', () => {
    expect(termsPatch(true)).toEqual({ terms: { may_be_included: true } });
    expect(termsPatch(false)).toEqual({ terms: { may_be_included: false } });
  });
});

describe('what a storefront says it includes', () => {
  it('names it with its licence, and says where there is none', () => {
    const licensed = includesLine({
      name: 'Armoury',
      licence: { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    });

    expect(licensed.text).toBe('Includes content from Armoury, CC BY 4.0');
    expect(licensed.url).toBe('https://creativecommons.org/licenses/by/4.0/');
    expect(includesLine({ name: 'Armoury', licence: null }).text).toBe(
      'Includes content from Armoury, no licence stated',
    );
  });

  it('links only to an https address', () => {
    expect(
      includesLine({ name: 'A', licence: { label: 'X', url: 'http://example.com/x' } }).url,
    ).toBeNull();
  });

  it('is nothing for a repository that includes nothing, or that the API says nothing of', () => {
    expect(includesLines([])).toEqual([]);
    expect(includesLines(undefined)).toEqual([]);
    expect(includesFacts(undefined)).toEqual([]);
  });

  it('is a fact of the preview in Studio', () => {
    expect(includesFacts([{ name: 'Armoury', licence: { label: 'OGL', url: null } }])).toEqual([
      { term: 'Includes content from', value: 'Armoury, OGL', url: null },
    ]);
  });
});

describe('the list of the dialog', () => {
  it('has a row for each repository it is built on, with the state and the choice', () => {
    const rows = builtOnChoices([
      source(),
      source({
        id: 'a-2',
        name: 'Rules',
        public: true,
        inclusion: 'include',
        includable: { allowed: false, by: null },
        in_release: 'include',
      }),
    ]);

    expect(BUILT_ON_CHOICES_TITLE).toBe('How this repository carries what it is built on');
    expect(rows.map((row) => [row.name, row.state, row.inclusion, row.offered])).toEqual([
      ['Armoury', 'Private', 'show', ['show', 'include']],
      ['Rules', 'Public', 'include', ['show', 'include']],
    ]);
    expect(rows[0]?.notOffered).toBeNull();
    expect(rows[0]?.note).toBeNull();
    expect(rows[1]?.notOffered).toContain('You cannot include Rules here');
    expect(rows[1]?.note).toBe(BREAKING_NOTE);
    expect(rows[1]?.effect).toContain('The entries of Rules become');
  });

  it('is empty for a repository built on nothing, and for what the API did not say', () => {
    expect(builtOnChoices([])).toEqual([]);
    expect(builtOnChoices(undefined)).toEqual([]);
  });
});
