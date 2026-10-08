// A library's repositories, as Shelf reads them (RFC 0036 §3): the list, what a copy would bring,
// and the names a repository holds, and the copy itself. Every read goes through the cache like the
// rest of the hub's (lib/cache.ts); a copy is a write, which empties it (lib/api.ts).

import { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { cached } from './cache';
import type {
  CopyOut,
  CopyPlanOut,
  CopyRequest,
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
// show and not a failure. The copy wizard asks for the plan `fresh`: what it shows decides a copy.
export async function getCopyPlan(
  libraryId: string,
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<CopyPlanOut | null> {
  return cached(
    `copy-plan:${libraryId}:${repositoryId}`,
    async () => {
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
    },
    { force: fresh },
  );
}

// Copies a repository, and what it is built on that the library has not copied, into the library.
// With `dry_run` it does everything, every check included, and rolls it back: "check first". A
// refusal is thrown with its details, for lib/copyWizard.ts's copyRefusal to read.
export async function copyRepository(
  libraryId: string,
  repositoryId: string,
  body: CopyRequest,
): Promise<CopyOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: libraryId, repository_id: repositoryId } },
      body,
    }),
  );
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
