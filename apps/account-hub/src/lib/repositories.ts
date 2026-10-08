// A library's repositories, as Shelf reads them (RFC 0036 §3): the list, what a copy would bring,
// and the names a repository holds, and the copy itself. Every read goes through the cache like the
// rest of the hub's (lib/cache.ts); a copy is a write, which empties it (lib/api.ts).

import { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { cached } from './cache';
import type {
  ApplyUpdatesOut,
  ApplyUpdatesRequest,
  CopyOut,
  CopyPlanOut,
  CopyRequest,
  Page,
  PublishRequest,
  ReleaseAuthoredOut,
  ReleasePreviewOut,
  ReleaseUpdate,
  RepositoryEntityOut,
  RepositoryStatGroupOut,
  SubscriberOut,
  SubscriptionOut,
  UpdatesOut,
} from './types';

// Every repository offered to a library, and every one it has copied.
export async function listLibraryRepositories(
  libraryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<SubscriptionOut[]> {
  return cached(
    `repositories:${libraryId}`,
    async () =>
      fetchAllPages(async (page) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/repositories', {
            params: { path: { tenant_id: libraryId }, query: { page, size: MAX_PAGE_SIZE } },
          }),
        ),
      ),
    { force: fresh },
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

// What the repository changed since the library copied or last updated it, row by row, beside the
// library's own copy (ADR 0121). It needs the repository to be offered and published: for any
// other the API refuses, and so does this, with null, since that is a state to show and not a
// failure. The inbox asks `fresh`: what it shows decides what is applied.
export async function getUpdates(
  libraryId: string,
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<UpdatesOut | null> {
  return cached(
    `updates:${libraryId}:${repositoryId}`,
    async () => {
      try {
        return unwrap(
          await client.GET('/tenants/{tenant_id}/repositories/{repository_id}/updates', {
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

// Applies the rows named, in one transaction, or with `dry_run` does everything and rolls it back.
// A write, so it empties the hub's cache like any other.
export async function applyUpdates(
  libraryId: string,
  repositoryId: string,
  body: ApplyUpdatesRequest,
): Promise<ApplyUpdatesOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/repositories/{repository_id}/updates', {
      params: { path: { tenant_id: libraryId, repository_id: repositoryId } },
      body,
    }),
  );
}

// The libraries and repositories a repository is invited to or that copied it, as its members see
// them (ADR 0204): when each was invited, whether and when it copied and last updated.
export async function listSubscribers(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<SubscriberOut[]> {
  return cached(
    `subscribers:${repositoryId}`,
    async () =>
      fetchAllPages(async (page) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/subscribers', {
            params: { path: { tenant_id: repositoryId }, query: { page, size: MAX_PAGE_SIZE } },
          }),
        ),
      ),
    { force: fresh },
  );
}

// Invites a library (or another repository) to copy from this one, by its id. An Owner's.
export async function inviteLibrary(repositoryId: string, libraryId: string): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: repositoryId, subscriber_tenant_id: libraryId } },
    }),
  );
}

// Stops inviting it: what it copied stays with it, and it is told (ADR 0199). An Owner's.
export async function stopInviting(repositoryId: string, libraryId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: repositoryId, subscriber_tenant_id: libraryId } },
    }),
  );
}

// Publishes a release of a repository (the first publish makes it public to its invited libraries):
// the members of every library with an invitation are told (ADR 0118, 0207). An Owner's.
export async function publishRepository(
  repositoryId: string,
  body: PublishRequest = { breaking: false, acknowledge_breaking: false },
): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: repositoryId } },
      body,
    }),
  );
}

// Back to a draft: the libraries invited to it can no longer look inside it, copy it or check for
// updates, and what they copied stays. Nobody is told. An Owner's.
export async function unpublishRepository(repositoryId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: repositoryId } },
    }),
  );
}

// A repository's releases, newest first, for whoever works on it (RFC 0037).
export async function listReleases(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<ReleaseAuthoredOut[]> {
  return cached(
    `releases:${repositoryId}`,
    async () =>
      fetchAllPages(async (page) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/releases', {
            params: { path: { tenant_id: repositoryId }, query: { page, size: MAX_PAGE_SIZE } },
          }),
        ),
      ),
    { force: fresh },
  );
}

// What a publish would release now: the live content against the latest release (writes nothing).
export async function getReleasePreview(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<ReleasePreviewOut> {
  return cached(
    `release-preview:${repositoryId}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/release-preview', {
          params: { path: { tenant_id: repositoryId } },
        }),
      ),
    { force: fresh },
  );
}

// Changes a release's label or notes: an Owner's. Nothing else of a release can change.
export async function editRelease(
  repositoryId: string,
  releaseId: string,
  body: ReleaseUpdate,
): Promise<void> {
  await unwrap(
    await client.PATCH('/tenants/{tenant_id}/releases/{release_id}', {
      params: { path: { tenant_id: repositoryId, release_id: releaseId } },
      body,
    }),
  );
}
