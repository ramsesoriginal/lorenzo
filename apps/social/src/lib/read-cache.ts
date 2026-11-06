import { createFetchCache, type Policy } from '@lorenzo/read-cache';

/**
 * What Social keeps of its reads (ADR 0325): bounded session memory in front of fetch, never an
 * offline grant and never authorization. A library's reads are held in memory for a few seconds
 * under the viewer's scope; who the person is and where they may go (`/me`, `/tenants`,
 * `/app-links`) is also kept in the tab's `sessionStorage`.
 */
const IDENTITY: Policy = { freshMs: 15_000, staleMs: 600_000, persist: true };
const HELD: Policy = { freshMs: 10_000 };

export function socialPolicy(url: URL): Policy | null {
  const path = url.pathname;

  if (path === '/me' || path === '/tenants' || path === '/app-links') return IDENTITY;

  if (path === '/me/managed') return HELD;

  if (!path.startsWith('/tenants/')) return null;

  // Who may read something is asked fresh whenever it is shown, and a lookup is not worth keeping.
  if (path.endsWith('/access') || path.endsWith('/audience') || path.endsWith('/entities/resolve'))
    return null;

  return HELD;
}

function sessionStore(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

export const socialReads = createFetchCache({
  policy: socialPolicy,
  storage: sessionStore(),
  storagePrefix: 'lorenzo.social.reads.',
});

/** The scope the reads are kept under: the viewer. A library is already in every path read from it. */
export function readScope(viewer: string): string {
  return JSON.stringify([viewer]);
}
