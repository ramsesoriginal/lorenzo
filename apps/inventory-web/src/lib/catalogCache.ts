import type { CatalogItem } from './types';

// Scoped deliberately narrow: only the default (unfiltered) catalog
// listing on /items, per tenant - the one thing on this app that's both
// read-heavy and low-stakes to show briefly stale (a GM's catalog doesn't
// change moment-to-moment the way a live board does). Search results
// aren't cached - unbounded key growth for a query string, and staleness
// there is far less predictable to reason about. Never load-bearing: a
// read failure or a full cache miss just means "fetch like before," never
// a broken page.
//
// v2: stores every catalog item (lib/items.ts's listCatalogItems now
// follows every page, not just the first) as a plain array, not a single
// Page<CatalogItem> - v1's shape would otherwise cache a silently
// truncated catalog. Bumped so a v1 entry from a previous session is
// never misread as the new shape.
//
// v3: per viewer as well as per tenant. Players list only the public
// catalog (ADR 0116), so one cached for a GM mustn't paint for a player on
// the same browser.
const VERSION = 3;

function storageKey(tenantId: string, viewerId: string): string {
  return `lorenzo:inventory-web:catalog:v${VERSION}:${tenantId}:${viewerId}`;
}

export function readCatalogCache(tenantId: string, viewerId: string): CatalogItem[] | null {
  try {
    const raw = window.localStorage.getItem(storageKey(tenantId, viewerId));
    if (!raw) return null;
    return JSON.parse(raw) as CatalogItem[];
  } catch {
    return null;
  }
}

export function writeCatalogCache(tenantId: string, viewerId: string, items: CatalogItem[]): void {
  try {
    window.localStorage.setItem(storageKey(tenantId, viewerId), JSON.stringify(items));
  } catch {
    // localStorage can throw (quota, private browsing, disabled) - purely
    // a perceived-speed optimization, so failing silently here is
    // correct, not swallowing a real error the user needs to see.
  }
}
