// Looking inside a repository, as the hub reads it (RFC 0038 §5, ADR 0293). The same four reads come
// in two forms: for a person with no library, or a library that holds nothing of the repository
// (`/repositories/{id}/...`, a visitor), and for a library (`/tenants/{id}/repositories/{id}/...`,
// a holder where it holds access). A page asks a `PreviewSource` and does not care which. What is
// looked at follows the Owner's switch, which can change at any moment, and is text that was
// chosen to be shown and may be hidden again, so these reads do not go through the cache of the
// hub's other reads (lib/cache.ts): each asks the API. A picture is fetched with the token and shown
// from a blob, as a cover is.

import { LorenzoApiError, MAX_PAGE_SIZE } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';
import { listRepositoryEntries } from './repositories';
import type { Page, PreviewEntityOut, PreviewOut, RepositoryEntityOut } from './types';

export type EntryQuery = { q?: string; page?: number; size?: number };

export type PreviewSource = {
  // The Owner's switch and the featured entries with their text, as far as this reader may look.
  preview(): Promise<PreviewOut>;
  // One entry, or null for one this reader may not look at (the API says the same for one that
  // does not exist).
  entry(entityId: string): Promise<PreviewEntityOut | null>;
  // A page of the entries by name, as far as this reader sees names.
  entries(query: EntryQuery): Promise<Page<RepositoryEntityOut>>;
  // A picture on a row of an entry's text, as a `blob:` address.
  picture(entityId: string, payloadId: string): Promise<string>;
};

const pictures = new Map<string, Promise<string>>();

// A picture, once for each address: fetched with the token, since an <img> cannot send one. A
// failure is not kept.
function pictureAt(path: string): Promise<string> {
  const known = pictures.get(path);

  if (known) return known;

  const loading = (async () => {
    const token = await getAccessToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new LorenzoApiError(`Could not load a picture (${response.status}).`, response.status);
    }

    return URL.createObjectURL(await response.blob());
  })();

  loading.catch(() => pictures.delete(path));
  pictures.set(path, loading);

  return loading;
}

// A refusal for an entry the reader may not look at is a state to show, not a failure.
function missing(cause: unknown): boolean {
  return cause instanceof LorenzoApiError && (cause.status === 404 || cause.status === 422);
}

// A person with no library, or a library with no access to a public repository: a visitor.
export function visitorSource(repositoryId: string): PreviewSource {
  const path = { repository_id: repositoryId };

  return {
    preview: async () =>
      unwrap(await client.GET('/repositories/{repository_id}/preview', { params: { path } })),

    entry: async (entityId) => {
      try {
        // `return await`, so that a refusal is caught here and not after it has left.
        return await unwrap(
          await client.GET('/repositories/{repository_id}/entities/{entity_id}', {
            params: { path: { ...path, entity_id: entityId } },
          }),
        );
      } catch (cause) {
        if (missing(cause)) return null;

        throw cause;
      }
    },

    entries: async ({ q, page = 1, size = MAX_PAGE_SIZE }) =>
      unwrap(
        await client.GET('/repositories/{repository_id}/entities', {
          params: { path, query: { page, size, ...(q ? { q } : {}) } },
        }),
      ),

    picture: (entityId, payloadId) =>
      pictureAt(`/repositories/${repositoryId}/entities/${entityId}/pictures/${payloadId}`),
  };
}

// A library: a holder of the repository where it holds access, and then it sees every name and the
// text the Owner's switch says.
export function librarySource(libraryId: string, repositoryId: string): PreviewSource {
  const path = { tenant_id: libraryId, repository_id: repositoryId };

  return {
    preview: async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/repositories/{repository_id}/preview', {
          params: { path },
        }),
      ),

    entry: async (entityId) => {
      try {
        return await unwrap(
          await client.GET(
            '/tenants/{tenant_id}/repositories/{repository_id}/entities/{entity_id}',
            {
              params: { path: { ...path, entity_id: entityId } },
            },
          ),
        );
      } catch (cause) {
        if (missing(cause)) return null;

        throw cause;
      }
    },

    entries: ({ q, page = 1, size = MAX_PAGE_SIZE }) =>
      listRepositoryEntries(libraryId, repositoryId, { q, page, size }),

    picture: (entityId, payloadId) =>
      pictureAt(
        `/tenants/${libraryId}/repositories/${repositoryId}/entities/${entityId}/pictures/${payloadId}`,
      ),
  };
}
