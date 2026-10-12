import type { components } from './schema';

/** The registry of app links `GET /app-links` serves (ADR 0273). */
export type AppLinks = components['schemas']['AppLinksOut'];

const cache = new Map<string, Promise<AppLinks>>();

/**
 * The registry for the API at `baseUrl`, fetched once per page load and kept in memory. A
 * failed fetch is not remembered, so the next call tries again; the caller falls back to
 * its own configuration meanwhile (ADR 0273). No authentication: the endpoint is public.
 */
export function getAppLinks(
  baseUrl: string,
  fetchImpl: typeof fetch = (...args) => fetch(...args),
): Promise<AppLinks> {
  const key = baseUrl.replace(/\/+$/, '');
  const known = cache.get(key);
  if (known) return known;
  const pending = fetchImpl(`${key}/app-links`, { headers: { Accept: 'application/json' } })
    .then((response) => {
      if (!response.ok) throw new Error(`GET /app-links failed (${response.status}).`);
      return response.json() as Promise<AppLinks>;
    })
    .catch((error) => {
      cache.delete(key);
      throw error;
    });
  cache.set(key, pending);
  return pending;
}

/** Forget what was fetched (tests, or a long-lived page that wants a fresh registry). */
export function clearAppLinksCache(): void {
  cache.clear();
}

/**
 * Fill a template's `{name}` placeholders, percent-encoding each value. A placeholder with
 * no value is left as written, so a missing parameter shows up rather than silently
 * producing a wrong link.
 */
export function fill(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    Object.hasOwn(params, name) ? encodeURIComponent(String(params[name])) : whole,
  );
}
