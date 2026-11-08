import { getAppLinks } from '@lorenzo/api-client';
import { API_BASE_URL } from './config';
import { calendarReads } from './read-cache';

type Registry = Awaited<ReturnType<typeof getAppLinks>>;

let registry: Promise<Registry | null> | null = null;

/** Where the apps are (the API's registry): asked once, and not again until the page is left for good. */
export function appRegistry(): Promise<Registry | null> {
  registry ??= getAppLinks(API_BASE_URL, calendarReads.fetch).catch(() => null);

  return registry;
}
