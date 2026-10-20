/**
 * The tenant last used in this browser, so a page reached without ?tenant=
 * (the header's links, a bookmark) opens that one. The URL always wins: this
 * only fills in for it. The session module validates it against this account's libraries.
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
 * The library this page is about: the URL's id or slug, otherwise the remembered one.
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
