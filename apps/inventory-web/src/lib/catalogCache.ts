import type { CatalogItem, Page } from './types';

// Scoped deliberately narrow: only the default (unfiltered) catalog
// listing on /items, per tenant - the one thing on this app that's both
// read-heavy and low-stakes to show briefly stale (a GM's catalog doesn't
// change moment-to-moment the way a live board does). Search results
// aren't cached - unbounded key growth for a query string, and staleness
// there is far less predictable to reason about. Never load-bearing: a
// read failure or a full cache miss just means "fetch like before," never
// a broken page.
const VERSION = 1;

function storageKey(tenantId: string): string {
  return `lorenzo:inventory-web:catalog:v${VERSION}:${tenantId}`;
}

export function readCatalogCache(tenantId: string): Page<CatalogItem> | null {
  try {
    const raw = window.localStorage.getItem(storageKey(tenantId));
    if (!raw) return null;
    return JSON.parse(raw) as Page<CatalogItem>;
  } catch {
    return null;
  }
}

export function writeCatalogCache(tenantId: string, page: Page<CatalogItem>): void {
  try {
    window.localStorage.setItem(storageKey(tenantId), JSON.stringify(page));
  } catch {
    // localStorage can throw (quota, private browsing, disabled) - purely
    // a perceived-speed optimization, so failing silently here is
    // correct, not swallowing a real error the user needs to see.
  }
}
