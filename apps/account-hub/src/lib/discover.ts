// What Discover and the storefront say (RFC 0038 §4, ADR 0292), as plain functions over what the API
// returns: the state of a search as an address and back, a result's lines, the filters, the pager,
// the lines of a repository's page, and the libraries a copy can go into. No DOM and nothing but
// ./types, ./shelf, ./format and ./tenantKind, so they run under Node in the unit tests. The words
// are those of identity.md §14.3: library, repository, release, Owner, entry, copy, built on,
// public; never "tenant", "grant" or "subscription". Nothing here says how often a repository was
// copied: Discover has no ranking (RFC 0038 §4).

import { byName, isTenantAdmin } from './format';
import { dayOf } from './shelf';
import { isRepository } from './tenantKind';
import type {
  CreditOut,
  DiscoverFacetOut,
  DiscoverFacetsOut,
  DiscoverItemOut,
  DiscoverPageOut,
  LicenceOut,
  PublicDependencyOut,
  PublisherOut,
  ReleaseOut,
  TenantSummaryOut,
} from './types';

// ---------------------------------------------------------------------------------------------
// The words of the page.

export const NOTHING_PUBLIC = 'Nothing is public yet.';
export const NOTHING_PUBLIC_HINT =
  'When the Owner of a repository makes it public, it is found here.';
export const NOTHING_FOUND = 'Nothing found. Try another word, or remove a filter.';
export const TOO_DEEP = 'Narrow your search with a word or a filter.';
export const NOT_LISTED =
  'This repository is not listed. It may be private, it may not have a release yet, or it may not exist.';
export const NO_LICENCE = 'No licence stated';
export const PAST_THE_END = 'There is nothing on that page.';
export const REPORT_LABEL = 'Report this repository';

// ---------------------------------------------------------------------------------------------
// The search, as an address.

export type DiscoverSort = 'name' | 'released';

export type DiscoverQuery = {
  q: string;
  tag: string;
  system: string;
  language: string;
  sort: DiscoverSort;
  page: number;
};

export const EMPTY_QUERY: DiscoverQuery = {
  q: '',
  tag: '',
  system: '',
  language: '',
  sort: 'name',
  page: 1,
};

// The API caps a page at 50; twenty is a screenful on a phone and a few on a desk.
export const PAGE_SIZE = 20;

export const SORT_LABEL: Record<DiscoverSort, string> = {
  name: 'Name',
  released: 'Newest release first',
};

// A search of the API's `q` is at most this long.
export const WORD_MAX = 100;

// What an address asks for: a repository's page (`repository=`), or a list as narrowed by `q`,
// `tag`, `system`, `language`, `sort` and `page`, any of which may be absent. Whatever is not
// understood is the default, so a link that was mistyped still shows the list.
export function readDiscoverLocation(search: string): {
  repository: string | null;
  query: DiscoverQuery;
} {
  const params = new URLSearchParams(search);
  const page = Number.parseInt(params.get('page') ?? '', 10);

  return {
    repository: params.get('repository')?.trim() || null,
    query: {
      q: (params.get('q') ?? '').trim().slice(0, WORD_MAX),
      tag: (params.get('tag') ?? '').trim(),
      system: (params.get('system') ?? '').trim(),
      language: (params.get('language') ?? '').trim(),
      sort: params.get('sort') === 'released' ? 'released' : 'name',
      page: Number.isFinite(page) && page >= 1 ? page : 1,
    },
  };
}

// The address of the list for a search: what is the default is left out, so the plain list is
// `/discover/` and a link to a result list is as short as it can be.
export function discoverHref(query: Partial<DiscoverQuery> = {}): string {
  const wanted = { ...EMPTY_QUERY, ...query };
  const params = new URLSearchParams();

  if (wanted.q.trim() !== '') params.set('q', wanted.q.trim());
  if (wanted.tag !== '') params.set('tag', wanted.tag);
  if (wanted.system !== '') params.set('system', wanted.system);
  if (wanted.language !== '') params.set('language', wanted.language);
  if (wanted.sort !== 'name') params.set('sort', wanted.sort);
  if (wanted.page > 1) params.set('page', String(wanted.page));

  const text = params.toString();

  return text === '' ? '/discover/' : `/discover/?${text}`;
}

// The address of a repository's page.
export function storefrontHref(repositoryId: string): string {
  return `/discover/?${new URLSearchParams({ repository: repositoryId }).toString()}`;
}

// The query string of the API for a search.
export function listQuery(query: DiscoverQuery): {
  q?: string;
  tag?: string;
  system?: string;
  language?: string;
  sort: DiscoverSort;
  page: number;
  size: number;
} {
  return {
    ...(query.q !== '' ? { q: query.q } : {}),
    ...(query.tag !== '' ? { tag: query.tag } : {}),
    ...(query.system !== '' ? { system: query.system } : {}),
    ...(query.language !== '' ? { language: query.language } : {}),
    sort: query.sort,
    page: query.page,
    size: PAGE_SIZE,
  };
}

// Whether a search narrows the list at all, for "Clear".
export function isNarrowed(query: DiscoverQuery): boolean {
  return query.q !== '' || query.tag !== '' || query.system !== '' || query.language !== '';
}

// ---------------------------------------------------------------------------------------------
// Whether Discover is shown.

// Discover is shown where the deployment accepts public repositories (ADR 0290, `enabled` of the
// facets) and nowhere else. An answer that did not come shows nothing, rather than a link that may
// lead nowhere.
export function showsDiscover(facets: Pick<DiscoverFacetsOut, 'enabled'> | null | undefined) {
  return facets?.enabled === true;
}

// ---------------------------------------------------------------------------------------------
// The filters.

// The most used values are shown, not all hundred of them: a list to choose from, and a search for
// the rest.
export const FILTER_LIMIT = 30;

export type FilterOption = { value: string; label: string };

// "German (de)" for a language code the browser knows, the code itself for one it does not.
export function languageLabel(code: string): string {
  try {
    const name = new Intl.DisplayNames(['en'], { type: 'language' }).of(code);

    return name && name.toLowerCase() !== code.toLowerCase() ? `${name} (${code})` : code;
  } catch {
    return code;
  }
}

// The choices of one filter: "any", then the most used values with how many repositories have each,
// and the value the address names if it is not among them, so the filter always shows what the
// list is narrowed by.
export function filterOptions(
  facets: readonly DiscoverFacetOut[],
  current: string,
  any: string,
  label: (value: string) => string = (value) => value,
): FilterOption[] {
  const shown = facets.slice(0, FILTER_LIMIT);
  const options: FilterOption[] = [
    { value: '', label: any },
    ...shown.map((facet) => ({
      value: facet.value,
      label: `${label(facet.value)} (${facet.count})`,
    })),
  ];

  if (
    current !== '' &&
    !shown.some((facet) => facet.value.toLowerCase() === current.toLowerCase())
  ) {
    options.push({ value: current, label: label(current) });
  }

  return options;
}

// ---------------------------------------------------------------------------------------------
// A result.

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function entriesLine(count: number | null): string | null {
  return count === null ? null : plural(count, 'entry', 'entries');
}

export function releaseLine(release: Pick<DiscoverItemOut['release'], 'label'>): string {
  return `Release ${release.label}`;
}

export type CardLines = {
  name: string;
  summary: string;
  tags: string[];
  // "Published by Ada, Bob": the Owners' accounts, or null where none is named.
  publishedBy: string | null;
  // The system, the release and how many entries, as small print.
  meta: string[];
};

// Who published it, by the names of the Owners' accounts (RFC 0038 section 6, ADR 0299): never a
// field the repository writes about itself. Null where the answer names nobody.
export function publishedByLine(publishers: readonly PublisherOut[] | undefined): string | null {
  const names = (publishers ?? []).map((publisher) => publisher.display_name);

  return names.length === 0 ? null : `Published by ${names.join(', ')}`;
}

// The Report link of a page: the address the API built, only if it is a `mailto:`, so that nothing
// else can ever be put in a link there. Null where the deployment sets no report address.
export function reportHref(mailto: string | null | undefined): string | null {
  return typeof mailto === 'string' && mailto.startsWith('mailto:') ? mailto : null;
}

// What a result says of a repository: its name and summary, its tags, and one line of small print.
export function cardLines(item: DiscoverItemOut): CardLines {
  return {
    name: item.name,
    summary: item.summary,
    tags: item.tags,
    publishedBy: publishedByLine(item.publishers),
    meta: [item.system, releaseLine(item.release), entriesLine(item.entries)].filter(
      (part): part is string => part !== null && part !== '',
    ),
  };
}

// "12 repositories", or null when there are none.
export function resultsLine(page: Pick<DiscoverPageOut, 'total'>): string | null {
  return page.total === 0 ? null : plural(page.total, 'repository', 'repositories');
}

// Why a list has nothing to show, in words: nothing is public at all, nothing matches, or the page
// asked for is past the last one. Null when it has something.
export function emptyLine(
  page: Pick<DiscoverPageOut, 'items' | 'total'>,
  query: DiscoverQuery,
): string | null {
  if (page.items.length > 0) return null;
  if (page.total > 0) return PAST_THE_END;

  return isNarrowed(query) ? NOTHING_FOUND : NOTHING_PUBLIC;
}

// ---------------------------------------------------------------------------------------------
// The pager.

export type Pager = {
  // "Page 2 of 5". Previous is the last page for a page past the end.
  label: string;
  previous: string | null;
  next: string | null;
};

// Previous and next, and where the list is: null for a list of one page.
export function pagerOf(
  page: Pick<DiscoverPageOut, 'page' | 'pages'>,
  query: DiscoverQuery,
): Pager | null {
  if (page.pages <= 1 && page.page <= 1) return null;

  const at = (number: number) => discoverHref({ ...query, page: number });

  return {
    label: `Page ${page.page} of ${page.pages}`,
    previous: page.page > 1 ? at(Math.min(page.page - 1, page.pages)) : null,
    next: page.page < page.pages ? at(page.page + 1) : null,
  };
}

// The API refuses a listing deeper than it goes (`422 discover-too-deep`).
export function isTooDeep(problemType: string | undefined): boolean {
  return problemType === 'discover-too-deep';
}

// ---------------------------------------------------------------------------------------------
// A repository's page.

// A link that is shown as one: https and nothing else (RFC 0038 §2), whatever the API stored.
export function safeLink(url: string | null | undefined): string | null {
  if (!url) return null;

  try {
    return new URL(url).protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

export type LicenceLine = { text: string; url: string | null };

// The licence, or "No licence stated": a missing one is not a licence (RFC 0038 §2).
export function licenceLine(licence: LicenceOut | null): LicenceLine {
  if (!licence) return { text: NO_LICENCE, url: null };

  return { text: licence.label, url: safeLink(licence.url) };
}

export type CreditLine = { name: string; role: string | null; url: string | null };

export function creditLine(credit: CreditOut): CreditLine {
  return { name: credit.name, role: credit.role || null, url: safeLink(credit.url) };
}

export type ReleaseGroups = {
  // The release a library takes, which is the one a repository is read at (ADR 0288).
  latest: ReleaseOut | null;
  others: ReleaseOut[];
  othersHeading: string;
};

// The latest release and the rest, newest first. The latest is the current release, which is the
// newest unless an Owner made an older one current again (ADR 0288); the heading says which of the
// two it is.
export function releaseGroups(releases: readonly ReleaseOut[]): ReleaseGroups {
  const ordered = [...releases].sort((a, b) => b.number - a.number);
  const latest = ordered.find((release) => release.current) ?? ordered[0] ?? null;
  const others = ordered.filter((release) => release !== latest);
  const allOlder = latest !== null && others.every((release) => release.number < latest.number);

  return { latest, others, othersHeading: allOlder ? 'Earlier releases' : 'Other releases' };
}

// "Release 1.3, 2026-10-14".
export function releaseHeading(release: Pick<ReleaseOut, 'label' | 'created_at'>): string {
  return `Release ${release.label}, ${dayOf(release.created_at)}`;
}

export type BuiltOnLine = { id: string; name: string; href: string | null; note: string | null };

// What a repository is built on: each one a link to its own page where it is public, and a plain
// name saying so where it is not.
export function builtOnLines(dependencies: readonly PublicDependencyOut[]): BuiltOnLine[] {
  return dependencies.map((dependency) => ({
    id: dependency.id,
    name: dependency.name,
    href: dependency.public ? storefrontHref(dependency.id) : null,
    note: dependency.public ? null : 'Not public',
  }));
}

export const BUILT_ON_NOT_PUBLIC =
  'A repository that is not public can be copied only by a library its Owner invited. Ask its Owner to make it public.';

export function hasPrivateUpstream(dependencies: readonly PublicDependencyOut[]): boolean {
  return dependencies.some((dependency) => !dependency.public);
}

export type Fact = { term: string; value: string };

// The facts under the heading: the game system, the languages and what is in it.
export function factsOf(item: DiscoverItemOut): Fact[] {
  const facts: Fact[] = [];

  if (item.system) facts.push({ term: 'Game system', value: item.system });

  if (item.languages.length > 0) {
    facts.push({ term: 'Languages', value: item.languages.map(languageLabel).join(', ') });
  }

  if (item.entries !== null) facts.push({ term: 'Entries', value: String(item.entries) });
  if (item.stat_definitions !== null) {
    facts.push({ term: 'Stats', value: String(item.stat_definitions) });
  }

  return facts;
}

// ---------------------------------------------------------------------------------------------
// Copying.

// Where a copy can go: what the person is an Owner or an Organizer of, since a copy changes what
// the library holds. Libraries first, by name, then repositories that copy from others (ADR 0205),
// which say so.
export function copyTargets(tenants: readonly TenantSummaryOut[]): TenantSummaryOut[] {
  return tenants
    .filter(isTenantAdmin)
    .sort((a, b) => Number(isRepository(a)) - Number(isRepository(b)) || byName(a.name, b.name));
}

export function copyTargetLabel(tenant: TenantSummaryOut): string {
  return isRepository(tenant) ? `${tenant.name} (repository)` : tenant.name;
}
