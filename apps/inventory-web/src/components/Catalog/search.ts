import { readCatalogCache, writeCatalogCache } from '../../lib/catalogCache';
import { listCatalogItems } from '../../lib/items';
import type { CatalogItem } from '../../lib/types';

export type CatalogSearch = {
  // Refreshes the whole catalog (the filter tree is built from it), then
  // re-runs the text query, if there is one.
  reload(): Promise<void>;
  destroy(): void;
};

export type CatalogSearchOptions = {
  input: HTMLInputElement;
  tenantId: string;
  viewerId: string;
  signal: AbortSignal;
  // The whole, unfiltered catalog.
  onCatalog(items: CatalogItem[]): void;
  // What the current text query matches, before the prototype filter.
  onResult(items: CatalogItem[]): void;
  onLoading(): void;
  onError(error: unknown): void;
  onClearError(): void;
};

export function createCatalogSearch(options: CatalogSearchOptions): CatalogSearch {
  let fullCatalog = readCatalogCache(options.tenantId, options.viewerId);
  let currentQuery = options.input.value.trim();

  // Only painting query results is superseded by a newer query; a catalog
  // refresh still lands, since the filter tree needs it.
  let queryRequest = 0;

  if (fullCatalog) {
    options.onCatalog(fullCatalog);

    if (!currentQuery) {
      options.onResult(fullCatalog);
    }
  }

  async function refreshFullCatalog(): Promise<CatalogItem[]> {
    const items = await listCatalogItems(options.tenantId);

    fullCatalog = items;
    writeCatalogCache(options.tenantId, options.viewerId, items);
    options.onCatalog(items);

    return items;
  }

  async function runQuery(query: string): Promise<void> {
    currentQuery = query;
    const request = ++queryRequest;
    options.onClearError();

    if (!query) {
      if (fullCatalog) {
        options.onResult(fullCatalog);
        return;
      }

      options.onLoading();

      try {
        const items = await refreshFullCatalog();

        if (request === queryRequest && !currentQuery) {
          options.onResult(items);
        }
      } catch (error) {
        if (request === queryRequest && !fullCatalog) {
          options.onError(error);
        }
      }

      return;
    }

    options.onLoading();

    try {
      const items = await listCatalogItems(options.tenantId, query);

      if (request !== queryRequest || currentQuery !== query) {
        return;
      }

      options.onResult(items);
    } catch (error) {
      if (request === queryRequest && currentQuery === query) {
        options.onError(error);
      }
    }
  }

  async function reload(): Promise<void> {
    const query = options.input.value.trim();

    currentQuery = query;
    const request = ++queryRequest;
    options.onClearError();

    // With a cache, keep showing it while refreshing.
    if (!fullCatalog && !query) {
      options.onLoading();
    }

    let freshCatalog: CatalogItem[] | null = null;

    try {
      freshCatalog = await refreshFullCatalog();
    } catch (error) {
      // A failed refresh doesn't replace a cache that's already painted.
      if (!fullCatalog && !query) {
        options.onError(error);
        return;
      }
    }

    // The query changed meanwhile; its own request paints.
    if (request !== queryRequest) {
      return;
    }

    if (!query) {
      const items = freshCatalog ?? fullCatalog;

      if (items) {
        options.onResult(items);
      }

      return;
    }

    options.onLoading();

    try {
      const items = await listCatalogItems(options.tenantId, query);

      if (request !== queryRequest || currentQuery !== query) {
        return;
      }

      options.onResult(items);
    } catch (error) {
      if (request === queryRequest && currentQuery === query) {
        options.onError(error);
      }
    }
  }

  let debounce: ReturnType<typeof setTimeout> | undefined;

  options.input.addEventListener(
    'input',
    () => {
      clearTimeout(debounce);

      debounce = setTimeout(() => {
        void runQuery(options.input.value.trim());
      }, 300);
    },
    { signal: options.signal },
  );

  return {
    reload,

    destroy() {
      clearTimeout(debounce);
    },
  };
}
