import { getAppLinks } from '@lorenzo/api-client';
import type { AppRegistry } from '@lorenzo/app-shell';
import { API_BASE_URL } from './config';
import { calendarReads } from './read-cache';

let registry: Promise<AppRegistry | null> | null = null;

/** Where the apps are (the API's registry): asked once, and not again until the page is left for good. */
export function appRegistry(): Promise<AppRegistry | null> {
  registry ??= getAppLinks(API_BASE_URL, calendarReads.fetch).catch(() => null);

  return registry;
}
