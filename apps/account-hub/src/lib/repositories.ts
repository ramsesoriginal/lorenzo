// A library's repositories, as Shelf reads them (RFC 0036 §3): the list, what a copy would bring,
// and the names a repository holds. Reads only; copying is a later slice. Every read goes through
// the cache like the rest of the hub's (lib/cache.ts).

import { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { cached } from './cache';
import type {
  CopyPlanOut,
  Page,
  RepositoryEntityOut,
  RepositoryStatGroupOut,
  SubscriptionOut,
} from './types';

// Every repository offered to a library, and every one it has copied.
export async function listLibraryRepositories(libraryId: string): Promise<SubscriptionOut[]> {
  return cached(`repositories:${libraryId}`, async () =>
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/repositories', {
          params: { path: { tenant_id: libraryId }, query: { page, size: MAX_PAGE_SIZE } },
        }),
      ),
    ),
  );
}

// What copying a repository would bring, which is also the one place the API lists what a
// repository is built on. It is only there for a repository that is offered and published: for
// any other the API answers "not found", and so does this, with null, since that is a state to
// show and not a failure.
export async function getCopyPlan(
  libraryId: string,
  repositoryId: string,
): Promise<CopyPlanOut | null> {
  return cached(`copy-plan:${libraryId}:${repositoryId}`, async () => {
    try {
      return unwrap(
        await client.GET('/tenants/{tenant_id}/repositories/{repository_id}/copy-plan', {
          params: { path: { tenant_id: libraryId, repository_id: repositoryId } },
        }),
      );
    } catch (cause) {
      if (cause instanceof LorenzoApiError && (cause.status === 404 || cause.status === 409)) {
        return null;
      }

      throw cause;
    }
  });
}

// A page of the entries a repository holds, by name, optionally those matching `q`. Names, kinds
// and parents only: no text is shown before a library copies it (ADR 0118).
export async function listRepositoryEntries(
  libraryId: string,
  repositoryId: string,
  options: { q?: string; page?: number; size?: number } = {},
): Promise<Page<RepositoryEntityOut>> {
  const { q, page = 1, size = MAX_PAGE_SIZE } = options;

  return cached(
    `repository-entries:${libraryId}:${repositoryId}:${q ?? ''}:${page}:${size}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/repositories/{repository_id}/entities', {
          params: {
            path: { tenant_id: libraryId, repository_id: repositoryId },
            query: { page, size, ...(q ? { q } : {}) },
          },
        }),
      ),
  );
}

export async function listRepositoryStatGroups(
  libraryId: string,
  repositoryId: string,
): Promise<RepositoryStatGroupOut[]> {
  return cached(`repository-stat-groups:${libraryId}:${repositoryId}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/repositories/{repository_id}/stat-groups', {
        params: { path: { tenant_id: libraryId, repository_id: repositoryId } },
      }),
    ),
  );
}
