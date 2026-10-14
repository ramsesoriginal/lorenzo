// Discover and a repository's page, as the hub reads them (RFC 0038 §4, ADR 0292): the listing, its
// facets, a storefront, and the reads of a public repository that need no library (ADR 0287):
// its releases, what it is built on, its cover. Every read goes through the cache like the rest of
// the hub's (lib/cache.ts).

import { fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { getAccessToken } from './auth';
import { cached } from './cache';
import { API_BASE_URL } from './config';
import { type DiscoverQuery, listQuery } from './discover';
import type {
  DiscoverFacetsOut,
  DiscoverPageOut,
  PublicDependencyOut,
  ReleaseOut,
  StorefrontOut,
} from './types';

// What the listing can be narrowed by, and whether this deployment accepts public repositories at
// all (ADR 0290): the header asks it to decide whether to show Discover.
export async function getFacets(): Promise<DiscoverFacetsOut> {
  return cached('discover-facets', async () => unwrap(await client.GET('/discover/facets')));
}

// A page of the public repositories. A listing too deep is refused (`discover-too-deep`), and is
// thrown for the page to say.
export async function listPublicRepositories(query: DiscoverQuery): Promise<DiscoverPageOut> {
  const params = listQuery(query);

  return cached(`discover:${JSON.stringify(params)}`, async () =>
    unwrap(await client.GET('/discover/repositories', { params: { query: params } })),
  );
}

// A repository's page, or null for one that is not listed: private, not released yet, or not
// there. That is a state to show, not a failure.
export async function getStorefront(repositoryId: string): Promise<StorefrontOut | null> {
  return cached(`storefront:${repositoryId}`, async () => {
    try {
      // `return await`, so that a refusal is caught here and not after it has left.
      return await unwrap(
        await client.GET('/discover/repositories/{repository_id}', {
          params: { path: { repository_id: repositoryId } },
        }),
      );
    } catch (cause) {
      if (cause instanceof LorenzoApiError && (cause.status === 404 || cause.status === 422)) {
        return null;
      }

      throw cause;
    }
  });
}

// What a public repository has released, newest first, with the notes of each.
export async function listPublicReleases(repositoryId: string): Promise<ReleaseOut[]> {
  return cached(`public-releases:${repositoryId}`, async () =>
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/repositories/{repository_id}/releases', {
          params: { path: { repository_id: repositoryId }, query: { page, size: MAX_PAGE_SIZE } },
        }),
      ),
    ),
  );
}

// What a public repository is built on, dependencies first, and whether each is public.
export async function listPublicDependencies(repositoryId: string): Promise<PublicDependencyOut[]> {
  return cached(`public-dependencies:${repositoryId}`, async () =>
    unwrap(
      await client.GET('/repositories/{repository_id}/dependencies', {
        params: { path: { repository_id: repositoryId } },
      }),
    ),
  );
}

const covers = new Map<string, Promise<string>>();

// A cover, as a `blob:` address. The route wants the token, which an <img> cannot send, so the
// picture is fetched with it and shown from the blob. Once for each repository on a page; a
// failure is not kept.
export function coverUrl(repositoryId: string): Promise<string> {
  const known = covers.get(repositoryId);

  if (known) return known;

  const loading = (async () => {
    const token = await getAccessToken();
    const response = await fetch(`${API_BASE_URL}/repositories/${repositoryId}/profile/cover`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new LorenzoApiError(`Could not load a cover (${response.status}).`, response.status);
    }

    return URL.createObjectURL(await response.blob());
  })();

  loading.catch(() => covers.delete(repositoryId));
  covers.set(repositoryId, loading);

  return loading;
}
