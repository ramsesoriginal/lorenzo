import { createLorenzoClient, LorenzoApiError } from '@lorenzo/api-client';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';

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
export const client = createLorenzoClient({ baseUrl: API_BASE_URL, getAccessToken });

const blobs = new Map<string, Promise<string>>();

/**
 * A file the API protects, such as a picture's `url`, as a `blob:` URL fetched with the
 * viewer's token (ADR 0108, 0112). Each URL is fetched once per page; a failure isn't kept.
 */
export function blobUrl(url: string): Promise<string> {
  const known = blobs.get(url);
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
  loading.catch(() => blobs.delete(url));
  blobs.set(url, loading);
  return loading;
}
