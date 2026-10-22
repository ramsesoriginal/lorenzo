import { createLorenzoClient, LorenzoApiError } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';
import { calendarReads } from './read-cache';

// The typed client, its error type, and paging all come from the client
// package this app shares with loot-bot (ADR 0122), generated from
// apps/api's own OpenAPI schema. A path typo, or a response field a route no
// longer sends, is a build-time type error rather than a silent undefined at
// runtime (ADR 0091). Re-exported here so every lib/*.ts keeps importing
// from './api'.
export type { components, paths } from '@lorenzo/api-client';
export { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE, unwrap } from '@lorenzo/api-client';

// Every request carries the viewer's token; with none, a request is refused
// with a 401 before it goes out, rather than sent for the API to reject.
export const client = createLorenzoClient({
  baseUrl: API_BASE_URL,
  getAccessToken,
  fetch: calendarReads.fetch,
});

const blobs = new Map<string, Promise<string>>();

/**
 * A file the API protects, such as a picture's `url`, as a `blob:` URL fetched with the
 * viewer's token (ADR 0108, 0112). Each URL/version is fetched once per page; failures aren't kept.
 * Versions only key this memory cache: the HTTP URL stays stable so
 * browser revalidation works across the list and sheet.
 */
export function blobUrl(url: string, version?: string): Promise<string> {
  const key = JSON.stringify([url, version ?? null]);
  const known = blobs.get(key);
  if (known) return known;
  const loading = (async () => {
    const token = await getAccessToken();
    const response = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok)
      throw new LorenzoApiError(`Couldn't load a file (${response.status}).`, response.status);
    return URL.createObjectURL(await response.blob());
  })();
  loading.catch(() => blobs.delete(key));
  blobs.set(key, loading);
  return loading;
}

export function clearPrivateState() {
  calendarReads.dropScoped();
  for (const pending of blobs.values())
    void pending.then((url) => URL.revokeObjectURL(url)).catch(() => {});
  blobs.clear();
}

if (typeof window !== 'undefined') {
  window.addEventListener('lorenzo:sign-out', clearPrivateState);
  window.addEventListener('pagehide', () => {
    clearPrivateState();
    document.querySelector('[data-page]')?.setAttribute('hidden', '');
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) location.reload();
  });
  document.addEventListener('astro:before-swap', () => {
    for (const pending of blobs.values())
      void pending.then((url) => URL.revokeObjectURL(url)).catch(() => {});
    blobs.clear();
  });
}
