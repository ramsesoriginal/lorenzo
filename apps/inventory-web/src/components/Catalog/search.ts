import {
  readCatalogCache,
  writeCatalogCache,
} from '../../lib/catalogCache';
import { listCatalogItems } from '../../lib/items';
import type { CatalogItem } from '../../lib/types';

export type CatalogSearch = {
  /**
   * Initial load and explicit refresh after a catalog mutation.
   *
   * Refreshes the complete catalog first, because that is also the
   * prototype taxonomy source. If a text query is active, its result
   * is refreshed afterwards.
   */
  reload(): Promise<void>;

  destroy(): void;
};

export type CatalogSearchOptions = {
  input: HTMLInputElement;
  tenantId: string;
  viewerId: string;
  signal: AbortSignal;

  /**
   * The complete unfiltered catalog changed. Used to rebuild the
   * prototype DAG independently of whatever text search is active.
   */
  onCatalog(items: CatalogItem[]): void;

  /**
   * These are the items matching the current text query, before
   * prototype filters are applied.
   */
  onResult(items: CatalogItem[]): void;

  /**
   * Nothing useful is currently painted, so the caller should show
   * its loading/skeleton state.
   */
  onLoading(): void;

  onError(error: unknown): void;
  onClearError(): void;
};

export function createCatalogSearch(
  options: CatalogSearchOptions,
): CatalogSearch {
  let fullCatalog =
    readCatalogCache(
      options.tenantId,
      options.viewerId,
    );

  let currentQuery =
    options.input.value.trim();

  /*
   * Only query-result painting is superseded by a newer query.
   * A full-catalog refresh remains useful even if the user types
   * while it is in flight, because filter.ts still needs that DAG.
   */
  let queryRequest = 0;

  if (fullCatalog) {
    options.onCatalog(fullCatalog);

    if (!currentQuery) {
      options.onResult(fullCatalog);
    }
  }

  async function refreshFullCatalog():
    Promise<CatalogItem[]> {
    const items =
      await listCatalogItems(
        options.tenantId,
      );

    fullCatalog = items;

    writeCatalogCache(
      options.tenantId,
      options.viewerId,
      items,
    );

    options.onCatalog(items);

    return items;
  }

  async function runQuery(
    query: string,
  ): Promise<void> {
    currentQuery = query;

    const request =
      ++queryRequest;

    options.onClearError();

    if (!query) {
      if (fullCatalog) {
        options.onResult(
          fullCatalog,
        );
        return;
      }

      options.onLoading();

      try {
        const items =
          await refreshFullCatalog();

        if (
          request === queryRequest &&
          !currentQuery
        ) {
          options.onResult(items);
        }
      } catch (error) {
        if (
          request === queryRequest &&
          !fullCatalog
        ) {
          options.onError(error);
        }
      }

      return;
    }

    options.onLoading();

    try {
      const items =
        await listCatalogItems(
          options.tenantId,
          query,
        );

      if (
        request !== queryRequest ||
        currentQuery !== query
      ) {
        return;
      }

      options.onResult(items);
    } catch (error) {
      if (
        request === queryRequest &&
        currentQuery === query
      ) {
        options.onError(error);
      }
    }
  }

  async function reload():
    Promise<void> {
    const query =
      options.input.value.trim();

    currentQuery = query;

    const request =
      ++queryRequest;

    options.onClearError();

    /*
     * If there is no cached/default catalog painted, loading the
     * full catalog is user-visible work.
     *
     * With a cache, leave that useful stale paint in place while
     * refreshing, matching the previous renderer's behavior.
     */
    if (!fullCatalog && !query) {
      options.onLoading();
    }

    let freshCatalog:
      | CatalogItem[]
      | null = null;

    try {
      freshCatalog =
        await refreshFullCatalog();
    } catch (error) {
      /*
       * An existing cache is deliberately enough to keep showing.
       * catalogCache.ts is a perceived-speed optimization, but a
       * refresh failure shouldn't replace useful cached content.
       */
      if (!fullCatalog && !query) {
        options.onError(error);
        return;
      }
    }

    /*
     * The user changed the search while the catalog refresh was in
     * flight. Don't paint results for the old query; the input event
     * has started its own request.
     */
    if (request !== queryRequest) {
      return;
    }

    if (!query) {
      const items =
        freshCatalog ??
        fullCatalog;

      if (items) {
        options.onResult(items);
      }

      return;
    }

    options.onLoading();

    try {
      const items =
        await listCatalogItems(
          options.tenantId,
          query,
        );

      if (
        request !== queryRequest ||
        currentQuery !== query
      ) {
        return;
      }

      options.onResult(items);
    } catch (error) {
      if (
        request === queryRequest &&
        currentQuery === query
      ) {
        options.onError(error);
      }
    }
  }

  let debounce:
    | ReturnType<typeof setTimeout>
    | undefined;

  options.input.addEventListener(
    'input',
    () => {
      clearTimeout(debounce);

      debounce = setTimeout(
        () => {
          void runQuery(
            options.input.value.trim(),
          );
        },
        300,
      );
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
