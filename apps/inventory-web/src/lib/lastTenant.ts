/**
 * The tenant last used in this browser, so a page reached without ?tenant=
 * (the header's links, a bookmark) opens that one. The URL always wins: this
 * only fills in for it. components/SiteHead's inline script reads the same
 * key before any page script runs - keep the two in step.
 */
export const LAST_TENANT_KEY = 'lorenzo:lastTenant';

/** Fired on window whenever the remembered tenant changes, for the header. */
export const LAST_TENANT_EVENT = 'lorenzo:last-tenant';

// localStorage can throw (private browsing, disabled) - then nothing is
// remembered, and every page behaves as if it never was.

export function getLastTenant(): string | null {
  try {
    return window.localStorage.getItem(LAST_TENANT_KEY);
  } catch {
    return null;
  }
}

export function rememberTenant(tenantId: string): void {
  try {
    window.localStorage.setItem(LAST_TENANT_KEY, tenantId);
  } catch {
    return;
  }
  window.dispatchEvent(new CustomEvent(LAST_TENANT_EVENT));
}

/**
 * The tenant this page is about, by id or by slug: the URL's (the head script puts a remembered
 * one there on a subpage), else the remembered one (home).
 */
export function currentTenant(): string | null {
  return new URLSearchParams(window.location.search).get('tenant') ?? getLastTenant();
}

export function forgetTenant(): void {
  try {
    window.localStorage.removeItem(LAST_TENANT_KEY);
  } catch {
    // Nothing was remembered either.
  }
}
