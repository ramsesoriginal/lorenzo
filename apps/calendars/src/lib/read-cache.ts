import { createFetchCache, type Policy } from '@lorenzo/read-cache';

/**
 * What Calendars keeps of its reads (ADR 0325): bounded session memory in front of fetch, never an
 * offline grant and never authorization (ADR 0313). A library's reads are held in memory for a
 * few seconds, under the viewer's scope; who the person is and where they may go (`/me`,
 * `/tenants`, `/app-links`) is also kept in the tab's `sessionStorage`, so a navigation that
 * reloads the page does not ask for it again.
 */
const IDENTITY: Policy = { freshMs: 15_000, staleMs: 600_000, persist: true };
const LIBRARY: Policy = { freshMs: 10_000 };

export function calendarPolicy(url: URL): Policy | null {
  const path = url.pathname;

  if (path === '/me' || path === '/tenants' || path === '/app-links') return IDENTITY;

  if (!path.startsWith('/tenants/')) return null;

  // Access is checked fresh whenever a protected view is entered, and a lookup is not worth keeping.
  if (
    path.endsWith('/events/access') ||
    path.endsWith('/entities/resolve') ||
    path.includes('/entities/by-slug/')
  ) {
    return null;
  }

  return LIBRARY;
}

/** A write that changes nothing, so it must not empty the cache. */
export function isPureWrite(url: URL): boolean {
  return (
    url.pathname.endsWith('/calendar-references/resolve') ||
    url.pathname.endsWith('/preview') ||
    url.pathname.endsWith('/events/compare')
  );
}

function sessionStore(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

export const calendarReads = createFetchCache({
  policy: calendarPolicy,
  isPureWrite,
  storage: sessionStore(),
  storagePrefix: 'lorenzo.calendars.reads.',
});

/** The scope the reads are kept under: the viewer, the library, their role and what they may do. */
export function readScope(
  viewer: string,
  tenant: string,
  role: string,
  access: { canOrder: boolean; canReadOrder: boolean; canRetainPrivate: boolean },
): string {
  return JSON.stringify([
    viewer,
    tenant,
    role,
    access.canOrder,
    access.canReadOrder,
    access.canRetainPrivate,
  ]);
}
