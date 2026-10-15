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
  FlipCheckOut,
  MadePrivateOut,
  MakePublicRequest,
  Page,
  PublishRequest,
  ReleaseAuthoredOut,
  ReleasePreviewOut,
  ReleaseUpdate,
  RepositoryEntityOut,
  RepositoryProfileOut,
  RepositoryStatGroupOut,
  ShowcaseOut,
  SubscriberOut,
  SubscribersSummaryOut,
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
        // `return await`: a refusal is caught here, as the answer below says, and not after it has left.
        return await unwrap(
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

// How many libraries copied it by themselves, from Discover: the one thing a repository learns of them
// besides the libraries it invited, which `listSubscribers` names (ADR 0299).
export async function getSubscribersSummary(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<SubscribersSummaryOut> {
  return cached(
    `subscribers-summary:${repositoryId}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/subscribers/summary', {
          params: { path: { tenant_id: repositoryId } },
        }),
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

// What a repository says about itself, for any of its members: its summary and its preview switch,
// and whether it is private or public (ADR 0213).
export async function getRepositoryProfile(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<RepositoryProfileOut> {
  return cached(
    `repository-profile:${repositoryId}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/profile', {
          params: { path: { tenant_id: repositoryId } },
        }),
      ),
    { force: fresh },
  );
}

// What making it public or private would run into, before it is asked (ADR 0290). An Owner's. It
// writes nothing, and what a dialog says of it decides what is sent, so it is read `fresh`.
export async function flipCheck(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<FlipCheckOut> {
  return cached(
    `flip-check:${repositoryId}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/flip-check', {
          params: { path: { tenant_id: repositoryId } },
        }),
      ),
    { force: fresh },
  );
}

// Makes it public with its first public release, in one step (ADR 0290): a refusal changes nothing.
// An Owner's.
export async function makePublic(repositoryId: string, body: MakePublicRequest): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body,
    }),
  );
}

// Makes it private again: the libraries that copied it by themselves lose its updates and keep what
// they copied. Refused, with their number, until `acknowledgeRevokes`. An Owner's.
export async function makePrivate(
  repositoryId: string,
  acknowledgeRevokes: boolean,
): Promise<MadePrivateOut> {
  return unwrap(
    await client.DELETE('/tenants/{tenant_id}/public', {
      params: {
        path: { tenant_id: repositoryId },
        query: { acknowledge_revokes: acknowledgeRevokes },
      },
    }),
  );
}

// What a visitor may look at before copying (RFC 0038 §5, ADR 0293): the Owner's switch, written on
// the profile. An Owner's.
export async function setPreviewChoice(
  repositoryId: string,
  preview: RepositoryProfileOut['preview'],
): Promise<RepositoryProfileOut> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repositoryId } },
      body: { preview },
    }),
  );
}

// The entries the Owner features, in order, and how many they may (any member reads them).
export async function getShowcase(
  repositoryId: string,
  { fresh = false }: { fresh?: boolean } = {},
): Promise<ShowcaseOut> {
  return cached(
    `showcase:${repositoryId}`,
    async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/showcase', {
          params: { path: { tenant_id: repositoryId } },
        }),
      ),
    { force: fresh },
  );
}

// Features these entries, in this order, instead of the ones there. An Owner's. A refusal
// (`showcase-invalid`) changes nothing and is thrown for the card to say.
export async function putShowcase(
  repositoryId: string,
  entityIds: readonly string[],
): Promise<ShowcaseOut> {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/showcase', {
      params: { path: { tenant_id: repositoryId } },
      body: { entity_ids: [...entityIds] },
    }),
  );
}

// The entries of the repository whose name has `q` in it, by name: to find one to feature. Names as
// they are now, which is what the Owner sees when they edit; a visitor reads the latest release.
export async function searchOwnEntries(
  repositoryId: string,
  q: string,
  size = 10,
): Promise<{ id: string; name: string }[]> {
  const page = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: repositoryId }, query: { q, page: 1, size } },
    }),
  );

  return page.items.map((entry) => ({ id: entry.id, name: entry.name }));
}
