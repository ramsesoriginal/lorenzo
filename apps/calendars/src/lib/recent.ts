// "Continue" on the Calendars home (D16): the calendars and entries last opened in this library, kept
// in this browser. Nothing here is private content: a name and an address. Where the browser keeps
// nothing (private browsing), nothing is remembered and the block is simply not there.

import { parseRecent, type RecentPage, rememberPage } from '@lorenzo/app-shell';

const key = (tenantId: string) => `lorenzo:calendars:recent:${tenantId}`;

export function recentPages(tenantId: string): RecentPage[] {
  try {
    return parseRecent(window.localStorage.getItem(key(tenantId)));
  } catch {
    return [];
  }
}

/** The page the person is on, by the name it has: a calendar, an entry. */
export function rememberThisPage(tenantId: string, title: string): void {
  try {
    const page = {
      href: `${window.location.pathname}${window.location.search}`,
      title,
      at: Date.now(),
    };

    window.localStorage.setItem(
      key(tenantId),
      JSON.stringify(rememberPage(recentPages(tenantId), page)),
    );
  } catch {
    // Nothing is remembered; Continue is not offered.
  }
}
