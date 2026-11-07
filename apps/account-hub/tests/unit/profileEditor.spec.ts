import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/lib/apiError';
import {
  addLanguages,
  addTags,
  apiProblems,
  CREDITS_MAX,
  capLine,
  changedFields,
  creditKey,
  type Draft,
  draftOf,
  isChanged,
  keyOfLocation,
  LANGUAGES_MAX,
  LICENCES,
  languageName,
  languageProblem,
  licenceChoiceOf,
  licenceOf,
  linkOf,
  linkProblem,
  mayEditProfile,
  moved,
  OTHER_LICENCE,
  patchOf,
  previewCard,
  previewFacts,
  problemsOf,
  SYSTEM_MAX,
  savedFacts,
  suggestLanguages,
  suggestValues,
  TAGS_MAX,
  tagOf,
  usualLink,
} from '../../src/lib/profileEditor';
import type { MemberProfileOut } from '../../src/lib/types';

function profile(overrides: Partial<MemberProfileOut> = {}): MemberProfileOut {
  return {
    visibility: 'private',
    preview: 'showcase',
    summary: '',
    licence: null,
    credits: [],
    tags: [],
    system: null,
    languages: [],
    has_cover: false,
    updated_at: '2026-11-03T10:00:00Z',
    listed: true,
    includes: [],
    terms: {
      may_be_included: false,
      is_default: true,
      may_be_shown: true,
      may_be_shown_is_default: true,
      may_be_hidden: true,
      may_be_hidden_is_default: true,
    },
    ...overrides,
  };
}

function draft(overrides: Partial<Draft> = {}): Draft {
  return { ...draftOf(profile()), ...overrides };
}

describe('who may change the profile', () => {
  it('is an Owner and nobody else, as the API has it (ADR 0213)', () => {
    expect(mayEditProfile('owner')).toBe(true);
    expect(mayEditProfile('orga')).toBe(false);
    expect(mayEditProfile('author')).toBe(false);
  });
});

describe('a link: https only, as the API keeps it', () => {
  it('accepts an https address and keeps the scheme in lower case', () => {
    expect(linkProblem('https://example.com/licence')).toBeNull();
    expect(linkProblem('  HTTPS://Example.com  ')).toBeNull();
    expect(linkOf('  HTTPS://Example.com  ')).toBe('https://Example.com');
    expect(linkOf('   ')).toBeNull();
  });

  it('refuses http and every other scheme in the API words', () => {
    expect(linkProblem('http://example.com')).toBe('A link must start with https://');
    expect(linkProblem('javascript:alert(1)')).toBe('A link must start with https://');
    expect(linkProblem('mailto:a@b.c')).toBe('A link must start with https://');
    expect(linkProblem('example.com')).toBe('A link must start with https://');
  });

  it('refuses spaces, a missing host, a password and an address that is too long', () => {
    expect(linkProblem('https://exa mple.com')).toBe("A link can't hold spaces");
    expect(linkProblem('https://')).toBe('A link needs a host, as in https://example.com');
    expect(linkProblem('https:///path')).toBe('A link needs a host, as in https://example.com');
    expect(linkProblem('https://user:pw@example.com')).toBe(
      "A link can't hold a user name or a password",
    );
    expect(linkProblem(`https://example.com/${'a'.repeat(500)}`)).toBe(
      'A link is at most 500 characters',
    );
  });

  it('has nothing to say about no link', () => {
    expect(linkProblem('')).toBeNull();
    expect(linkProblem('   ')).toBeNull();
  });
});

describe('tags', () => {
  it('are lower case with their whitespace made single', () => {
    expect(tagOf('  Dark   Fantasy ')).toBe('dark fantasy');
  });

  it('are added in that form, several at once, and a repeat is not added', () => {
    expect(addTags([], 'Dark Fantasy, undead,  DARK fantasy')).toEqual({
      list: ['dark fantasy', 'undead'],
      problem: null,
    });
    expect(addTags(['undead'], 'Undead')).toEqual({ list: ['undead'], problem: null });
    expect(addTags(['a'], '  ,  ')).toEqual({ list: ['a'], problem: null });
  });

  it('are refused past the cap and when one is too long, in the API words', () => {
    const full = Array.from({ length: TAGS_MAX }, (_, index) => `tag${index}`);

    expect(addTags(full, 'one more')).toEqual({
      list: full,
      problem: `At most ${TAGS_MAX} tags`,
    });
    expect(addTags([], 'x'.repeat(33)).problem).toBe('A tag is at most 32 characters');
    expect(addTags([], 'x'.repeat(32)).problem).toBeNull();
  });
});

describe('languages', () => {
  it('are language codes, as the API takes them', () => {
    expect(languageProblem('de')).toBeNull();
    expect(languageProblem('PT-BR')).toBeNull();
    expect(languageProblem('zh-hans')).toBeNull();
    expect(languageProblem('German')).toBe(
      "'German' isn't a language code such as en, de or pt-br",
    );
    expect(languageProblem('e')).not.toBeNull();
  });

  it('are added in lower case without repeats, and refused past the cap', () => {
    expect(addLanguages(['de'], 'EN, de, pt-BR')).toEqual({
      list: ['de', 'en', 'pt-br'],
      problem: null,
    });
    expect(addLanguages([], 'xx yy').problem).not.toBeNull();

    const full = ['aa', 'bb', 'cc', 'dd', 'ee', 'ff', 'gg', 'hh'];

    expect(full).toHaveLength(LANGUAGES_MAX);
    expect(addLanguages(full, 'ii')).toEqual({
      list: full,
      problem: `At most ${LANGUAGES_MAX} languages`,
    });
  });

  it('are named in the language asked for, and the code stands where the browser does not know it', () => {
    expect(languageName('de', 'en')).toBe('German (de)');
    expect(languageName('de', 'de')).toBe('Deutsch (de)');
    expect(languageName('pt-br', 'en')).toContain('(pt-br)');
    expect(languageName('zzzzzz', 'en')).toBe('zzzzzz');
    expect(languageName('de', 'not a locale at all')).toBe('de');
  });

  it('are suggested from Discover and a few common ones, never the ones chosen', () => {
    const suggestions = suggestLanguages([{ value: 'fr' }, { value: 'sv' }], ['en', 'fr'], 'en');
    const codes = suggestions.map((suggestion) => suggestion.value);

    expect(codes[0]).toBe('sv');
    expect(codes).toContain('de');
    expect(codes).not.toContain('en');
    expect(codes).not.toContain('fr');
    expect(new Set(codes).size).toBe(codes.length);
    expect(suggestions.find((suggestion) => suggestion.value === 'de')?.label).toBe('German (de)');
  });

  it('are the only suggestions for tags and systems that Discover has, minus the chosen', () => {
    expect(suggestValues([{ value: 'a' }, { value: 'b' }, { value: 'a' }], ['b'])).toEqual(['a']);
    expect(suggestValues([], [])).toEqual([]);
  });
});

describe('the licence', () => {
  it('chooses a listed one by its name, and anything else as Other', () => {
    expect(licenceChoiceOf(null)).toBe('');
    expect(licenceChoiceOf({ label: 'CC BY 4.0', url: null })).toBe('CC BY 4.0');
    expect(licenceChoiceOf({ label: 'My own terms', url: null })).toBe(OTHER_LICENCE);
  });

  it('is none, a listed one or the author words, with an optional https link', () => {
    expect(licenceOf(draft())).toBeNull();
    expect(licenceOf(draft({ licence: 'CC BY 4.0', licenceUrl: '' }))).toEqual({
      label: 'CC BY 4.0',
      url: null,
    });
    expect(
      licenceOf(
        draft({
          licence: OTHER_LICENCE,
          licenceOther: '  Table  rules ',
          licenceUrl: 'https://example.com/t',
        }),
      ),
    ).toEqual({ label: 'Table rules', url: 'https://example.com/t' });
  });

  it('offers the usual link of a listed licence, and no link for one without', () => {
    expect(usualLink('CC BY 4.0')).toBe('https://creativecommons.org/licenses/by/4.0/');
    expect(usualLink('All rights reserved')).toBeNull();
    expect(usualLink('')).toBeNull();
    expect(usualLink(OTHER_LICENCE)).toBeNull();
    // Nothing in the list is a value the API refuses.
    for (const licence of LICENCES) {
      expect(licence.label.length).toBeLessThanOrEqual(80);
      if (licence.url) expect(linkProblem(licence.url)).toBeNull();
    }
  });

  it('wants a name for a link, and a link that is https', () => {
    expect(problemsOf(draft({ licenceUrl: 'https://example.com' })).licenceLink).toContain(
      'Choose a licence',
    );
    expect(problemsOf(draft({ licence: 'CC0 1.0', licenceUrl: 'http://x.y' })).licenceLink).toBe(
      'A link must start with https://',
    );
    expect(problemsOf(draft({ licence: OTHER_LICENCE, licenceOther: '  ' })).licence).toBe(
      "A licence name can't be empty",
    );
    expect(
      problemsOf(draft({ licence: OTHER_LICENCE, licenceOther: 'x'.repeat(81) })).licence,
    ).toBe('A licence name is at most 80 characters');
    expect(problemsOf(draft({ licence: 'CC0 1.0', licenceUrl: '' }))).toEqual({});
  });
});

describe('what is wrong with a draft, next to the field', () => {
  it('has nothing wrong with an empty profile: only making it public asks for a summary', () => {
    expect(problemsOf(draft())).toEqual({});
  });

  it('counts the summary as the API keeps it, on one line', () => {
    expect(problemsOf(draft({ summary: `${'a '.repeat(140)}` })).summary).toBeUndefined();
    expect(problemsOf(draft({ summary: 'a'.repeat(281) })).summary).toBe(
      'A summary is at most 280 characters. This one is 281.',
    );
    expect(problemsOf(draft({ summary: `a\n\n   b` }))).toEqual({});
  });

  it('checks each credit: a name, at most 80; a role, at most 60; an https link', () => {
    const problems = problemsOf(
      draft({
        credits: [
          { name: 'Ada', role: '', url: '' },
          { name: '  ', role: 'x'.repeat(61), url: 'http://x.y' },
        ],
      }),
    );

    expect(problems).toEqual({
      [creditKey(1, 'name')]: "A name can't be empty",
      [creditKey(1, 'role')]: 'A role is at most 60 characters',
      [creditKey(1, 'url')]: 'A link must start with https://',
    });
  });

  it('says the cap on credits, a system that is too long and a bad language', () => {
    expect(
      problemsOf(
        draft({
          credits: Array.from({ length: CREDITS_MAX + 1 }, () => ({
            name: 'A',
            role: '',
            url: '',
          })),
        }),
      ).credits,
    ).toBe(`At most ${CREDITS_MAX} credits`);
    expect(problemsOf(draft({ system: 'x'.repeat(SYSTEM_MAX + 1) })).system).toBe(
      `A system is at most ${SYSTEM_MAX} characters`,
    );
    expect(problemsOf(draft({ languages: ['deutsch'] })).languages).toBe(
      "'deutsch' isn't a language code such as en, de or pt-br",
    );
  });

  it('says how many of each there are against the cap', () => {
    expect(capLine(3, 12, 'tag', 'tags')).toBe('3 of 12 tags');
    expect(capLine(1, 20, 'credit', 'credits')).toBe('1 of 20 credits');
  });
});

describe('what changed, as one request', () => {
  const saved = profile({
    summary: 'Every beast there is.',
    licence: { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    credits: [{ name: 'Ada', role: 'Author', url: null }],
    tags: ['monsters'],
    system: 'D&D 5e',
    languages: ['en'],
  });

  it('is nothing for a draft made from the profile, and for the same said another way', () => {
    expect(isChanged(saved, draftOf(saved))).toBe(false);
    expect(patchOf(saved, draftOf(saved))).toEqual({});
    expect(
      isChanged(saved, {
        ...draftOf(saved),
        summary: 'Every   beast\nthere is.',
        tags: ['Monsters'],
        languages: ['EN'],
      }),
    ).toBe(false);
  });

  it('names only the fields that changed', () => {
    const changed = { ...draftOf(saved), summary: 'Every beast.', tags: ['monsters', 'undead'] };

    expect(changedFields(saved, changed)).toEqual(['summary', 'tags']);
    expect(patchOf(saved, changed)).toEqual({
      summary: 'Every beast.',
      tags: ['monsters', 'undead'],
    });
  });

  it('sends the normalised form of what was typed', () => {
    const typed = {
      ...draftOf(profile()),
      summary: '  Two\nlines ',
      tags: ['Dark  Fantasy', 'dark fantasy'],
      system: '  Pathfinder 2e ',
      languages: ['DE'],
      credits: [{ name: ' Ada ', role: ' ', url: 'HTTPS://example.com/a' }],
    };

    expect(patchOf(profile(), typed)).toEqual({
      summary: 'Two lines',
      tags: ['dark fantasy'],
      system: 'Pathfinder 2e',
      languages: ['de'],
      credits: [{ name: 'Ada', role: null, url: 'https://example.com/a' }],
    });
  });

  it('clears the licence and the system with null, and a list with an empty one', () => {
    const cleared = {
      ...draftOf(saved),
      licence: '',
      licenceUrl: '',
      system: '  ',
      tags: [],
      credits: [],
    };

    expect(patchOf(saved, cleared)).toEqual({
      licence: null,
      system: null,
      tags: [],
      credits: [],
    });
  });

  it('sends a licence as a name and a link, and a link change on its own', () => {
    expect(patchOf(saved, { ...draftOf(saved), licenceUrl: '' })).toEqual({
      licence: { label: 'CC BY 4.0', url: null },
    });
    expect(
      patchOf(profile(), { ...draftOf(profile()), licence: OTHER_LICENCE, licenceOther: 'Ours' }),
    ).toEqual({ licence: { label: 'Ours', url: null } });
  });

  it('is a change when credits are reordered', () => {
    const two = profile({
      credits: [
        { name: 'A', role: null, url: null },
        { name: 'B', role: null, url: null },
      ],
    });
    const reordered = { ...draftOf(two), credits: moved(draftOf(two).credits, 0, 1) };

    expect(changedFields(two, reordered)).toEqual(['credits']);
  });
});

describe('moving in a list', () => {
  it('swaps with the neighbour and stays put at the ends', () => {
    expect(moved(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c']);
    expect(moved(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'c', 'b']);
    expect(moved(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moved(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c']);
  });
});

describe('what the API refused, next to the field', () => {
  function refusal(errors: unknown[]): ApiError {
    return new ApiError('Request validation error.', 422, 'request-validation-failed', {
      title: 'Request validation error.',
      errors,
    });
  }

  it('finds the field from where the API says it is', () => {
    expect(keyOfLocation(['body', 'summary'])).toBe('summary');
    expect(keyOfLocation(['body', 'licence', 'url'])).toBe('licenceLink');
    expect(keyOfLocation(['body', 'licence', 'label'])).toBe('licence');
    expect(keyOfLocation(['body', 'credits', 2, 'url'])).toBe('credit.2.url');
    expect(keyOfLocation(['body', 'credits', 0, 'name'])).toBe('credit.0.name');
    expect(keyOfLocation(['body', 'credits'])).toBe('credits');
    expect(keyOfLocation(['body', 'tags'])).toBe('tags');
    expect(keyOfLocation(['body', 'tags', 3])).toBe('tags');
    expect(keyOfLocation(['body', 'languages'])).toBe('languages');
    expect(keyOfLocation(['body'])).toBeNull();
    expect(keyOfLocation('nope')).toBeNull();
  });

  it('says the API words next to each field it names, without its "Value error" prefix', () => {
    expect(
      apiProblems(
        refusal([
          { loc: ['body', 'licence', 'url'], msg: 'Value error, A link must start with https://' },
          { loc: ['body', 'credits', 1, 'url'], msg: "Value error, A link can't hold spaces" },
          { loc: ['body', 'tags'], msg: 'Value error, At most 12 tags' },
          { loc: ['body', 'summary'], msg: 'Value error, A summary is at most 280 characters' },
        ]),
      ),
    ).toEqual({
      licenceLink: 'A link must start with https://',
      'credit.1.url': "A link can't hold spaces",
      tags: 'At most 12 tags',
      summary: 'A summary is at most 280 characters',
    });
  });

  it('keeps what names no field as one sentence for the form', () => {
    expect(
      apiProblems(refusal([{ loc: ['body'], msg: "Value error, summary can't be null" }])),
    ).toEqual({ form: "summary can't be null" });
  });

  it('falls back to the API detail for a refusal that is not a validation one', () => {
    expect(
      apiProblems(
        new ApiError('Only an Owner.', 403, 'repository-management-forbidden', {
          detail: 'Only an Owner of the repository may change it.',
        }),
      ),
    ).toEqual({ form: 'Only an Owner of the repository may change it.' });
    expect(apiProblems(new ApiError('Request failed (500).', 500))).toEqual({
      form: 'Something went wrong. Try again in a moment.',
    });
  });
});

describe('what people will see', () => {
  const edited = draft({
    summary: 'Every beast there is.',
    tags: ['monsters', 'undead'],
    system: 'D&D 5e',
    languages: ['de', 'en'],
    licence: 'CC BY 4.0',
    licenceUrl: 'https://creativecommons.org/licenses/by/4.0/',
    credits: [
      { name: 'Ada', role: 'Author', url: 'https://example.com/ada' },
      { name: 'Bob', role: '', url: '' },
    ],
  });

  it("is Discover's card for the name and what the draft says", () => {
    expect(previewCard('Bestiary', edited)).toEqual({
      name: 'Bestiary',
      summary: 'Every beast there is.',
      tags: ['monsters', 'undead'],
      publishedBy: null,
      meta: ['D&D 5e'],
    });
    expect(previewCard('Bestiary', draft()).meta).toEqual([]);
  });

  it('adds what its own page says: system, languages, licence and credits', () => {
    expect(previewFacts(edited, 'en')).toEqual([
      { term: 'Game system', value: 'D&D 5e' },
      { term: 'Languages', value: 'German (de), English (en)' },
      {
        term: 'Licence',
        value: 'CC BY 4.0',
        url: 'https://creativecommons.org/licenses/by/4.0/',
      },
      { term: 'Credit', value: 'Ada, Author', url: 'https://example.com/ada' },
      { term: 'Credit', value: 'Bob', url: null },
    ]);
  });

  it('says "No licence stated" for none, which is not a licence', () => {
    expect(previewFacts(draft(), 'en')).toEqual([
      { term: 'Licence', value: 'No licence stated', url: null },
    ]);
  });

  it('shows no link that is not https, whatever was stored', () => {
    const facts = savedFacts(
      profile({
        licence: { label: 'Odd', url: 'http://example.com' },
        credits: [{ name: 'Ada', role: null, url: 'javascript:alert(1)' }],
      }),
      'en',
    );

    expect(facts.every((fact) => !fact.url)).toBe(true);
  });
});
