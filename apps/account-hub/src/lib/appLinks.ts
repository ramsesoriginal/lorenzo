import { getAppLinks } from '@lorenzo/api-client';
import { API_BASE_URL, BEINGS_BASE_URL } from './config';

/**
 * Where Lorenzo Beings lives, or undefined when nothing says. The API's registry of app links
 * knows (ADR 0273); the build's own `PUBLIC_BEINGS_BASE_URL` is only the fallback for when the
 * registry cannot be reached.
 */
export async function beingsBaseUrl(): Promise<string | undefined> {
  try {
    const registry = await getAppLinks(API_BASE_URL);

    return registry.apps.beings.url.replace(/\/$/, '') || BEINGS_BASE_URL;
  } catch {
    return BEINGS_BASE_URL;
  }
}
