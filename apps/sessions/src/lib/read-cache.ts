import { createFetchCache, type Policy } from '@lorenzo/read-cache';

/**
 * What Sessions keeps of its reads (ADR 0325): bounded session memory in front of fetch, never an
 * offline grant and never authorization (ADR 0317). A library's reads and the person's own lists
 * are held in memory for a few seconds under the viewer's scope; who the person is and where they
 * may go (`/me`, `/tenants`, `/app-links`) is also kept in the tab's `sessionStorage`. A
 * Session's notes and every other private body stay in memory only.
 */
const IDENTITY: Policy = { freshMs: 15_000, staleMs: 600_000, persist: true };
const HELD: Policy = { freshMs: 10_000 };

export function sessionPolicy(url: URL): Policy | null {
  const path = url.pathname;

  if (path === '/me' || path === '/tenants' || path === '/app-links') return IDENTITY;

  if (path === '/me/sessions' || path === '/me/managed') return HELD;

  if (!path.startsWith('/tenants/')) return null;

  // Who may read something is asked fresh whenever it is shown, and a lookup is not worth keeping.
  if (path.endsWith('/access') || path.endsWith('/entities/resolve')) return null;

  return HELD;
}

function sessionStore(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

export const sessionReads = createFetchCache({
  policy: sessionPolicy,
  storage: sessionStore(),
  storagePrefix: 'lorenzo.sessions.reads.',
});

/**
 * The scope the reads are kept under: the viewer. A library is already in every path that is read
 * from it, and moving between pages (from My Sessions to a Session) must keep what was asked ahead.
 */
export function readScope(viewer: string): string {
  return JSON.stringify([viewer]);
}
