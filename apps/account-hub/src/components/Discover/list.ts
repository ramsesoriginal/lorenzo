// The list of /discover (ADR 0292): a search box, the filters, the sort, the results as cards and a
// pager. The state of the search is in the address, so a result list can be linked; the search is
// sent when it is submitted, not on each keystroke, and a filter is a choice made at once.

import { ApiError } from '../../lib/apiError';
import {
  cardLines,
  type DiscoverQuery,
  discoverHref,
  emptyLine,
  type FilterOption,
  filterOptions,
  isNarrowed,
  isTooDeep,
  languageLabel,
  pagerOf,
  resultsLine,
  SORT_LABEL,
  storefrontHref,
  TOO_DEEP,
} from '../../lib/discover';
import { listPublicRepositories } from '../../lib/discoverApi';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { DiscoverFacetsOut } from '../../lib/types';
import { showCover } from './cover';

const required = requiredIn('Discover list');

export type DiscoverList = {
  // Paints the list for a search. `isCurrent` says whether it is still the one asked for.
  show(query: DiscoverQuery, isCurrent: () => boolean): Promise<void>;
};

function fill(select: HTMLSelectElement, options: FilterOption[], value: string): void {
  select.replaceChildren(
    ...options.map((option) => {
      const element = document.createElement('option');

      element.value = option.value;
      element.textContent = option.label;

      return element;
    }),
  );
  select.value = value;
}

// `root` is the <Discover /> block, whose templates are used, and `view` its list. `onSearch` is
// called with the address of a search the person made.
export function createList(
  root: HTMLElement,
  view: HTMLElement,
  facets: DiscoverFacetsOut,
  onSearch: (href: string) => void,
): DiscoverList {
  const form = required<HTMLFormElement>(view, '[data-search]');
  const word = required<HTMLInputElement>(view, '[data-word]');
  const tag = required<HTMLSelectElement>(view, '[data-tag]');
  const system = required<HTMLSelectElement>(view, '[data-system]');
  const language = required<HTMLSelectElement>(view, '[data-language]');
  const sort = required<HTMLSelectElement>(view, '[data-sort]');
  const error = required<HTMLElement>(view, '[data-list-error]');
  const tooDeep = required<HTMLElement>(view, '[data-too-deep]');
  const tooDeepText = required<HTMLElement>(view, '[data-too-deep-text]');
  const firstPage = required<HTMLAnchorElement>(view, '[data-first-page]');
  const count = required<HTMLElement>(view, '[data-count]');
  const empty = required<HTMLElement>(view, '[data-empty]');
  const clearLine = required<HTMLElement>(view, '[data-clear-line]');
  const clear = required<HTMLAnchorElement>(view, '[data-clear]');
  const results = required<HTMLElement>(view, '[data-results]');
  const pager = required<HTMLElement>(view, '[data-pager]');
  const previous = required<HTMLAnchorElement>(view, '[data-previous]');
  const next = required<HTMLAnchorElement>(view, '[data-next]');
  const pageOf = required<HTMLElement>(view, '[data-page-of]');

  const read = (): DiscoverQuery => ({
    q: word.value.trim(),
    tag: tag.value,
    system: system.value,
    language: language.value,
    sort: sort.value === 'released' ? 'released' : 'name',
    page: 1,
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    onSearch(discoverHref(read()));
  });

  // A choice of a filter or of the order is made at once, with the word as it is typed.
  for (const select of [tag, system, language, sort]) {
    select.addEventListener('change', () => form.requestSubmit());
  }

  function paintForm(query: DiscoverQuery): void {
    word.value = query.q;
    fill(tag, filterOptions(facets.tags, query.tag, 'Any tag'), query.tag);
    fill(system, filterOptions(facets.systems, query.system, 'Any game system'), query.system);
    fill(
      language,
      filterOptions(facets.languages, query.language, 'Any language', languageLabel),
      query.language,
    );
    fill(
      sort,
      (Object.keys(SORT_LABEL) as (keyof typeof SORT_LABEL)[]).map((value) => ({
        value,
        label: SORT_LABEL[value],
      })),
      query.sort,
    );
  }

  function clearResults(): void {
    results.replaceChildren();
    count.textContent = '';
    empty.hidden = true;
    pager.hidden = true;
    tooDeep.hidden = true;
    error.hidden = true;
  }

  return {
    async show(query, isCurrent) {
      paintForm(query);
      clear.href = discoverHref();
      clearLine.hidden = !isNarrowed(query);
      clearResults();

      let page: Awaited<ReturnType<typeof listPublicRepositories>>;

      try {
        page = await listPublicRepositories(query);
      } catch (cause) {
        if (!isCurrent()) return;

        if (cause instanceof ApiError && isTooDeep(cause.problemType)) {
          tooDeepText.textContent = TOO_DEEP;
          firstPage.href = discoverHref({ ...query, page: 1 });
          tooDeep.hidden = false;

          return;
        }

        sayError(error, cause);

        return;
      }

      if (!isCurrent()) return;

      count.textContent = resultsLine(page) ?? '';

      const nothing = emptyLine(page, query);

      empty.textContent = nothing ?? '';
      empty.hidden = nothing === null;

      results.replaceChildren(
        ...page.items.map((item) => {
          const lines = cardLines(item);
          const card = cloneRoot(root, '[data-card-template]');
          const name = required<HTMLAnchorElement>(card, '[data-name]');

          name.textContent = lines.name;
          name.href = storefrontHref(item.id);
          required<HTMLElement>(card, '[data-summary]').textContent = lines.summary;

          const tags = required<HTMLElement>(card, '[data-tags]');

          tags.replaceChildren(
            ...lines.tags.map((text) => {
              const tagItem = cloneRoot(root, '[data-tag-template]');

              required<HTMLElement>(tagItem, '[data-text]').textContent = text;

              return tagItem;
            }),
          );
          tags.hidden = lines.tags.length === 0;
          required<HTMLElement>(card, '[data-meta]').textContent = lines.meta.join(' · ');

          showCover(
            required<HTMLImageElement>(card, '[data-picture]'),
            required<HTMLElement>(card, '[data-initial]'),
            item,
            isCurrent,
          );

          return card;
        }),
      );

      const pages = pagerOf(page, query);

      pager.hidden = pages === null;

      if (pages) {
        pageOf.textContent = pages.label;
        previous.hidden = pages.previous === null;
        previous.href = pages.previous ?? '#';
        next.hidden = pages.next === null;
        next.href = pages.next ?? '#';
      }
    },
  };
}
