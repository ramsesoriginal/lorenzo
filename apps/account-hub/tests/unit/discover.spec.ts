import { describe, expect, it } from 'vitest';
import {
  BUILT_ON_NOT_PUBLIC,
  builtOnLines,
  cardLines,
  copyTargetLabel,
  copyTargets,
  creditLine,
  type DiscoverQuery,
  discoverHref,
  EMPTY_QUERY,
  emptyLine,
  entriesLine,
  FILTER_LIMIT,
  factsOf,
  filterOptions,
  hasPrivateUpstream,
  isNarrowed,
  isTooDeep,
  languageLabel,
  licenceLine,
  listQuery,
  NO_LICENCE,
  NOT_LISTED,
  NOTHING_FOUND,
  NOTHING_PUBLIC,
  PAGE_SIZE,
  PAST_THE_END,
  pagerOf,
  publishedByLine,
  REPORT_LABEL,
  readDiscoverLocation,
  releaseGroups,
  releaseHeading,
  reportHref,
  resultsLine,
  safeLink,
  showsDiscover,
  storefrontHref,
  TOO_DEEP,
} from '../../src/lib/discover';
import { subjectOfPublic, subjectOfSubscription } from '../../src/lib/shelf';
import type {
  DiscoverItemOut,
  DiscoverPageOut,
  PublicDependencyOut,
  ReleaseOut,
  SubscriptionOut,
  TenantSummaryOut,
} from '../../src/lib/types';

function item(overrides: Partial<DiscoverItemOut> = {}): DiscoverItemOut {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    name: 'Bestiary',
    slug: 'bestiary',
    summary: 'Every beast there is.',
    tags: ['monsters', 'srd'],
    system: 'D&D 5e',
    languages: ['en'],
    has_cover: false,
    release: { label: '1.2', released_at: '2026-10-14T09:00:00Z' },
    entries: 309,
    stat_definitions: 12,
    publishers: [{ display_name: 'Ada Author' }],
    ...overrides,
  };
}

function page(overrides: Partial<DiscoverPageOut> = {}): DiscoverPageOut {
  return { items: [item()], total: 1, page: 1, size: 20, pages: 1, ...overrides };
}

function release(overrides: Partial<ReleaseOut> = {}): ReleaseOut {
  return {
    id: 'r',
    number: 1,
    label: '1.0',
    notes: null,
    breaking: false,
    created_at: '2026-10-01T12:00:00Z',
    digest: null,
    counts: null,
    breaking_rows: [],
    warning_rows: [],
    current: false,
    ...overrides,
  };
}

function tenant(overrides: Partial<TenantSummaryOut> = {}): TenantSummaryOut {
  return {
    id: 't',
    name: 'Table',
    slug: 'table',
    kind: 'play',
    role: 'owner',
    ...overrides,
  } as TenantSummaryOut;
}

describe('the address of a search', () => {
  it('reads a list as the address says it, and a plain one as the defaults', () => {
    expect(readDiscoverLocation('')).toEqual({ repository: null, query: EMPTY_QUERY });
    expect(
      readDiscoverLocation(
        '?q=%20dragon%20&tag=srd&system=D%26D%205e&language=en&sort=released&page=3',
      ),
    ).toEqual({
      repository: null,
      query: {
        q: 'dragon',
        tag: 'srd',
        system: 'D&D 5e',
        language: 'en',
        sort: 'released',
        page: 3,
      },
    });
  });

  it('reads a repository page, and takes what it does not understand as the default', () => {
    expect(readDiscoverLocation('?repository=abc').repository).toBe('abc');
    expect(readDiscoverLocation('?sort=popularity&page=0').query).toMatchObject({
      sort: 'name',
      page: 1,
    });
    expect(readDiscoverLocation('?page=two').query.page).toBe(1);
    expect(readDiscoverLocation(`?q=${'x'.repeat(300)}`).query.q).toHaveLength(100);
  });

  it('writes the address back, leaving out what is the default', () => {
    expect(discoverHref()).toBe('/discover/');
    expect(discoverHref({ q: '  ' })).toBe('/discover/');
    expect(discoverHref({ q: 'red dragon', tag: 'srd', sort: 'released', page: 2 })).toBe(
      '/discover/?q=red+dragon&tag=srd&sort=released&page=2',
    );
  });

  it('is the same list whether it is read or written', () => {
    const query: DiscoverQuery = {
      q: 'owl & bear',
      tag: 'monsters',
      system: 'D&D 5e',
      language: 'de',
      sort: 'released',
      page: 4,
    };
    const href = discoverHref(query);

    expect(readDiscoverLocation(href.slice(href.indexOf('?'))).query).toEqual(query);
  });

  it('addresses a repository, and says which searches narrow the list', () => {
    expect(storefrontHref('a b')).toBe('/discover/?repository=a+b');
    expect(isNarrowed(EMPTY_QUERY)).toBe(false);
    expect(isNarrowed({ ...EMPTY_QUERY, sort: 'released', page: 3 })).toBe(false);
    expect(isNarrowed({ ...EMPTY_QUERY, language: 'de' })).toBe(true);
  });

  it('asks the API for a page of its own size, and for what is set', () => {
    expect(listQuery(EMPTY_QUERY)).toEqual({ sort: 'name', page: 1, size: PAGE_SIZE });
    expect(listQuery({ ...EMPTY_QUERY, q: 'owl', tag: 'srd', page: 2 })).toEqual({
      q: 'owl',
      tag: 'srd',
      sort: 'name',
      page: 2,
      size: PAGE_SIZE,
    });
    expect(PAGE_SIZE).toBeLessThanOrEqual(50);
  });
});

describe('whether Discover is shown', () => {
  it('is shown where the deployment accepts public repositories, and nowhere else', () => {
    expect(showsDiscover({ enabled: true })).toBe(true);
    expect(showsDiscover({ enabled: false })).toBe(false);
    // An answer that did not come shows no link.
    expect(showsDiscover(null)).toBe(false);
    expect(showsDiscover(undefined)).toBe(false);
  });
});

describe('the filters', () => {
  const tags = [
    { value: 'srd', count: 12 },
    { value: 'monsters', count: 4 },
  ];

  it('offers any, then the most used with how many have each', () => {
    expect(filterOptions(tags, '', 'Any tag')).toEqual([
      { value: '', label: 'Any tag' },
      { value: 'srd', label: 'srd (12)' },
      { value: 'monsters', label: 'monsters (4)' },
    ]);
  });

  it('shows only the most used, and still the value the address names', () => {
    const many = Array.from({ length: FILTER_LIMIT + 10 }, (_, index) => ({
      value: `tag-${index}`,
      count: 100 - index,
    }));

    expect(filterOptions(many, '', 'Any tag')).toHaveLength(FILTER_LIMIT + 1);
    expect(filterOptions(many, 'tag-3', 'Any tag')).toHaveLength(FILTER_LIMIT + 1);

    const named = filterOptions(many, 'tag-39', 'Any tag');

    expect(named).toHaveLength(FILTER_LIMIT + 2);
    expect(named.at(-1)).toEqual({ value: 'tag-39', label: 'tag-39' });
    // The case the address was written in does not add a second copy.
    expect(filterOptions(tags, 'SRD', 'Any tag')).toHaveLength(3);
  });

  it('names a language by its code, and by its name where it is known', () => {
    expect(languageLabel('de')).toBe('German (de)');
    expect(languageLabel('zz-unknown-code')).toContain('zz');
    expect(
      filterOptions([{ value: 'en', count: 2 }], '', 'Any language', languageLabel)[1],
    ).toEqual({ value: 'en', label: 'English (en) (2)' });
  });
});

describe('a result', () => {
  it('says the name, the summary, the tags and one line of small print', () => {
    expect(cardLines(item())).toEqual({
      name: 'Bestiary',
      summary: 'Every beast there is.',
      tags: ['monsters', 'srd'],
      publishedBy: 'Published by Ada Author',
      meta: ['D&D 5e', 'Release 1.2', '309 entries'],
    });
  });

  it('leaves out what it does not know, and counts one entry as one', () => {
    expect(cardLines(item({ system: null, entries: null })).meta).toEqual(['Release 1.2']);
    expect(entriesLine(1)).toBe('1 entry');
    expect(entriesLine(0)).toBe('0 entries');
    expect(entriesLine(null)).toBeNull();
  });

  it('says who published it by the accounts of its Owners, and nothing where none is named', () => {
    expect(publishedByLine([{ display_name: 'Ada' }, { display_name: 'Bob' }])).toBe(
      'Published by Ada, Bob',
    );
    expect(publishedByLine([])).toBeNull();
    expect(publishedByLine(undefined)).toBeNull();
    expect(cardLines(item({ publishers: [] })).publishedBy).toBeNull();
  });

  it('links a report only to the address the API built, and only a mailto', () => {
    expect(REPORT_LABEL).toBe('Report this repository');
    expect(reportHref('mailto:reports@example.org?subject=Report')).toBe(
      'mailto:reports@example.org?subject=Report',
    );
    expect(reportHref(null)).toBeNull();
    expect(reportHref('https://example.org')).toBeNull();
    expect(reportHref('javascript:alert(1)')).toBeNull();
  });

  it('says nothing of how often it was copied', () => {
    const words = JSON.stringify([cardLines(item()), factsOf(item())]);

    expect(words).not.toMatch(/popular|copied|most|trending|downloads/i);
  });

  it('counts the results', () => {
    expect(resultsLine(page({ total: 0 }))).toBeNull();
    expect(resultsLine(page({ total: 1 }))).toBe('1 repository');
    expect(resultsLine(page({ total: 57 }))).toBe('57 repositories');
  });
});

describe('what an empty list says', () => {
  it('says nothing is public when nothing is, and nothing was found when a search found none', () => {
    const none = page({ items: [], total: 0, pages: 0 });

    expect(emptyLine(none, EMPTY_QUERY)).toBe(NOTHING_PUBLIC);
    expect(emptyLine(none, { ...EMPTY_QUERY, q: 'zzz' })).toBe(NOTHING_FOUND);
    expect(emptyLine(page(), EMPTY_QUERY)).toBeNull();
  });

  it('says a page past the last has nothing, and a listing too deep to narrow it', () => {
    expect(emptyLine(page({ items: [], total: 30, page: 9, pages: 2 }), EMPTY_QUERY)).toBe(
      PAST_THE_END,
    );
    expect(TOO_DEEP).toBe('Narrow your search with a word or a filter.');
    expect(isTooDeep('discover-too-deep')).toBe(true);
    expect(isTooDeep('repository-not-found')).toBe(false);
    expect(isTooDeep(undefined)).toBe(false);
  });
});

describe('the pager', () => {
  const query: DiscoverQuery = { ...EMPTY_QUERY, q: 'owl', page: 2 };

  it('has none for a list of one page', () => {
    expect(pagerOf(page(), EMPTY_QUERY)).toBeNull();
    expect(pagerOf(page({ items: [], total: 0, pages: 0 }), EMPTY_QUERY)).toBeNull();
  });

  it('says where the list is, and links to the pages beside it, with the search kept', () => {
    expect(pagerOf(page({ page: 2, pages: 5 }), query)).toEqual({
      label: 'Page 2 of 5',
      previous: '/discover/?q=owl',
      next: '/discover/?q=owl&page=3',
    });
  });

  it('has no previous on the first page and no next on the last', () => {
    expect(pagerOf(page({ page: 1, pages: 3 }), EMPTY_QUERY)).toMatchObject({
      previous: null,
      next: '/discover/?page=2',
    });
    expect(pagerOf(page({ page: 3, pages: 3 }), EMPTY_QUERY)).toMatchObject({
      previous: '/discover/?page=2',
      next: null,
    });
  });

  it('leads a page past the end back to the last one', () => {
    expect(pagerOf(page({ items: [], total: 30, page: 9, pages: 2 }), EMPTY_QUERY)).toMatchObject({
      previous: '/discover/?page=2',
      next: null,
    });
  });
});

describe('a repository page', () => {
  it('shows a link only for an https address', () => {
    expect(safeLink('https://example.org/licence')).toBe('https://example.org/licence');
    expect(safeLink('http://example.org')).toBeNull();
    expect(safeLink('javascript:alert(1)')).toBeNull();
    expect(safeLink('data:text/html,hi')).toBeNull();
    expect(safeLink('not a url')).toBeNull();
    expect(safeLink(null)).toBeNull();
    expect(safeLink('')).toBeNull();
  });

  it('says the licence, or that none is stated', () => {
    expect(licenceLine(null)).toEqual({ text: NO_LICENCE, url: null });
    expect(NO_LICENCE).toBe('No licence stated');
    expect(
      licenceLine({ label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' }),
    ).toEqual({
      text: 'CC BY 4.0',
      url: 'https://creativecommons.org/licenses/by/4.0/',
    });
    expect(licenceLine({ label: 'Own terms', url: null })).toEqual({
      text: 'Own terms',
      url: null,
    });
    expect(licenceLine({ label: 'Own terms', url: 'http://insecure.example' }).url).toBeNull();
  });

  it('says the credits with their role and a link where there is one', () => {
    expect(creditLine({ name: 'Ada', role: 'Writer', url: 'https://ada.example' })).toEqual({
      name: 'Ada',
      role: 'Writer',
      url: 'https://ada.example',
    });
    expect(creditLine({ name: 'Bo', role: null, url: 'http://bo.example' })).toEqual({
      name: 'Bo',
      role: null,
      url: null,
    });
  });

  it('lists the facts that are known, in order', () => {
    expect(factsOf(item())).toEqual([
      { term: 'Game system', value: 'D&D 5e' },
      { term: 'Languages', value: 'English (en)' },
      { term: 'Entries', value: '309' },
      { term: 'Stats', value: '12' },
    ]);
    expect(
      factsOf(item({ system: null, languages: [], entries: null, stat_definitions: null })),
    ).toEqual([]);
  });

  it('takes the current release as the latest and says the rest are earlier ones', () => {
    const one = release({ id: 'a', number: 1, label: '1.0' });
    const two = release({ id: 'b', number: 2, label: '1.1', current: true });
    const groups = releaseGroups([one, two]);

    expect(groups.latest?.label).toBe('1.1');
    expect(groups.others.map((r) => r.label)).toEqual(['1.0']);
    expect(groups.othersHeading).toBe('Earlier releases');
  });

  it('does not call a newer release earlier, when an older one was made current again', () => {
    const groups = releaseGroups([
      release({ id: 'a', number: 1, label: '1.0', current: true }),
      release({ id: 'b', number: 2, label: '1.1' }),
    ]);

    expect(groups.latest?.label).toBe('1.0');
    expect(groups.othersHeading).toBe('Other releases');
    expect(releaseGroups([]).latest).toBeNull();
    expect(
      releaseGroups([release({ number: 3 }), release({ id: 'x', number: 4 })]).latest?.number,
    ).toBe(4);
  });

  it('heads a release with its label and its day', () => {
    expect(releaseHeading(release({ label: '1.1', created_at: '2026-10-14T09:00:00Z' }))).toBe(
      'Release 1.1, 2026-10-14',
    );
  });

  it('links what it is built on to its own page where that is public', () => {
    const dependencies: PublicDependencyOut[] = [
      { id: 'core', name: 'Core', slug: 'core', public: true },
      { id: 'secret', name: 'Secret', slug: 'secret', public: false },
    ];

    expect(builtOnLines(dependencies)).toEqual([
      { id: 'core', name: 'Core', href: '/discover/?repository=core', note: null },
      { id: 'secret', name: 'Secret', href: null, note: 'Not public' },
    ]);
    expect(hasPrivateUpstream(dependencies)).toBe(true);
    expect(hasPrivateUpstream(dependencies.slice(0, 1))).toBe(false);
    expect(BUILT_ON_NOT_PUBLIC).toContain('Ask its Owner to make it public');
  });

  it('has a word for a repository that is not listed', () => {
    expect(NOT_LISTED).toContain('not listed');
  });
});

describe('where a copy can go', () => {
  it('offers what the person is an Owner or an Organizer of, libraries first', () => {
    const targets = copyTargets([
      tenant({ id: 'p', name: 'Player', role: 'participant' }),
      tenant({ id: 'r', name: 'Rules', kind: 'repository', role: 'owner' }),
      tenant({ id: 'z', name: 'Zed table', role: 'orga' }),
      tenant({ id: 'a', name: 'alder table', role: 'owner' }),
    ]);

    expect(targets.map((target) => target.id)).toEqual(['a', 'z', 'r']);
    expect(copyTargetLabel(targets[0] as TenantSummaryOut)).toBe('alder table');
    expect(copyTargetLabel(targets[2] as TenantSummaryOut)).toBe('Rules (repository)');
    expect(copyTargets([tenant({ role: 'participant' })])).toEqual([]);
  });
});

describe('the subject of a copy', () => {
  it('is a public repository that can be copied from where it stands, and backs out to its page', () => {
    expect(subjectOfPublic({ id: 'abc', name: 'Bestiary' })).toEqual({
      id: 'abc',
      name: 'Bestiary',
      offered: true,
      copied: false,
      public: true,
      backHref: storefrontHref('abc'),
    });
  });

  it('is a repository of a library as it stands in its Shelf, and backs out to its Shelf page', () => {
    const subscription = {
      granted_at: '2026-10-01T00:00:00Z',
      copied_at: null,
      synced_at: null,
      repository: { id: 'abc', name: 'Bestiary', published_at: '2026-10-02T00:00:00Z' },
    } as unknown as SubscriptionOut;

    expect(subjectOfSubscription(subscription, { slug: 'table' })).toEqual({
      id: 'abc',
      name: 'Bestiary',
      offered: true,
      copied: false,
      public: false,
      backHref: '/repositories/?tenant=table&repository=abc',
    });
    expect(
      subjectOfSubscription(
        { ...subscription, repository: { ...subscription.repository, published_at: null } },
        { slug: 'table' },
      ).offered,
    ).toBe(false);
    expect(
      subjectOfSubscription({ ...subscription, copied_at: '2026-10-03T00:00:00Z' }, { slug: 't' })
        .copied,
    ).toBe(true);
  });
});

describe('the words of the page', () => {
  it('never says tenant, grant or subscription', () => {
    const words = [
      NOT_LISTED,
      NOTHING_FOUND,
      NOTHING_PUBLIC,
      TOO_DEEP,
      PAST_THE_END,
      BUILT_ON_NOT_PUBLIC,
      NO_LICENCE,
    ].join(' ');

    expect(words).not.toMatch(/tenant|grant|subscri|stable|frozen/i);
  });
});
