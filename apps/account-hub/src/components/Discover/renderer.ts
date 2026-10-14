// /discover (ADR 0292, RFC 0038 §4): the public repositories, found by a word or a filter, and one
// repository's page. A list is `?q=&tag=&system=&language=&sort=&page=`, a repository `?repository=<id>`;
// all are plain links, so they can be opened, shared and gone back to. Where the deployment accepts
// no public repository the page says nothing is public yet, and so does a listing that has none.

import {
  NOT_LISTED,
  NOTHING_PUBLIC,
  NOTHING_PUBLIC_HINT,
  readDiscoverLocation,
  showsDiscover,
} from '../../lib/discover';
import { getFacets } from '../../lib/discoverApi';
import { sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { createList } from './list';
import { createStorefront } from './storefront';

const required = requiredIn('Discover');

// `root` is the <Discover /> block. It is built, and shown, once; the first load's failure rejects,
// for the page to show. Moving between the list and a repository reads the address and paints
// again.
export async function renderDiscover(root: HTMLElement): Promise<void> {
  const error = required<HTMLElement>(root, '[data-error]');
  const nothing = required<HTMLElement>(root, '[data-nothing]');
  const nothingText = required<HTMLElement>(root, '[data-nothing-text]');
  const nothingHint = required<HTMLElement>(root, '[data-nothing-hint]');
  const listView = required<HTMLElement>(root, '[data-list-view]');
  const storefrontView = required<HTMLElement>(root, '[data-storefront]');
  const notListed = required<HTMLElement>(root, '[data-not-listed]');

  const facets = await getFacets();

  // A deployment that accepts no public repository has nothing here, and no link to it.
  if (!showsDiscover(facets)) {
    nothingText.textContent = NOTHING_PUBLIC;
    nothingHint.textContent = NOTHING_PUBLIC_HINT;
    nothing.hidden = false;
    root.hidden = false;

    return;
  }

  const list = createList(root, listView, facets, (href) => {
    window.history.pushState(null, '', href);
    void reload();
  });
  const storefront = createStorefront(root, storefrontView);

  // Only the newest show paints.
  let latest = 0;

  async function show(): Promise<void> {
    const turn = ++latest;
    const isCurrent = () => turn === latest;
    const { repository, query } = readDiscoverLocation(window.location.search);

    error.hidden = true;
    notListed.hidden = true;

    if (repository) {
      listView.hidden = true;
      storefrontView.hidden = true;

      const found = await storefront.show(repository, isCurrent);

      if (!isCurrent()) return;

      if (found) {
        storefrontView.hidden = false;
      } else {
        notListed.textContent = NOT_LISTED;
        notListed.hidden = false;
      }

      return;
    }

    storefrontView.hidden = true;
    listView.hidden = false;
    await list.show(query, isCurrent);
  }

  async function reload(): Promise<void> {
    try {
      await show();
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // Links stay links: a modified click opens them as the browser would. A plain one moves within
  // the page and keeps the address true.
  root.addEventListener('click', (event) => {
    const link = (event.target as Element).closest<HTMLAnchorElement>('a[data-link]');

    if (!link || event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    event.preventDefault();
    window.history.pushState(null, '', link.href);
    window.scrollTo(0, 0);
    void reload();
  });

  window.addEventListener('popstate', () => void reload());

  await show();
  root.hidden = false;
}
