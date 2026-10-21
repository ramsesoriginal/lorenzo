// Where the other Lorenzo apps live. The API's registry of app links says (ADR 0273); the build's
// own PUBLIC_INVENTORY_WEB_BASE_URL is only the fallback for when the registry cannot be reached.
import {
  type AppLinks,
  calendarEntryHref,
  fill,
  getAppLinks,
  type Schema,
} from '@lorenzo/api-client';
import { API_BASE_URL, INVENTORY_WEB_BASE_URL } from './config';

let registry: AppLinks | undefined;

/** Ask the registry once (kept in memory by the client); a failure leaves the fallbacks in use. */
export async function loadAppLinks(): Promise<void> {
  try {
    registry = await getAppLinks(API_BASE_URL);
  } catch {
    registry = undefined;
  }
}

/** A being's board in inventory-web, or null when neither the registry nor the build knows where. */
export function boardUrl(tenant: string, entityId: string): string | null {
  const template = registry?.links.board;

  if (template) return fill(template, { tenant, id: entityId });

  return INVENTORY_WEB_BASE_URL
    ? `${INVENTORY_WEB_BASE_URL}/board/?tenant=${encodeURIComponent(tenant)}&character=${entityId}`
    : null;
}

/** An item's page in inventory-web, or null in the same way. */
export function itemUrl(tenant: string, entityId: string): string | null {
  const template = registry?.links.item;

  if (template) return fill(template, { tenant, id: entityId });

  return INVENTORY_WEB_BASE_URL
    ? `${INVENTORY_WEB_BASE_URL}/item/?tenant=${encodeURIComponent(tenant)}&id=${entityId}`
    : null;
}

export function calendarUrl(
  tenant: string,
  entry: Pick<Schema<'ResolvedSlugOut'>, 'entity_id' | 'kinds'> & { slug?: string | null },
  hint = '',
): string | null {
  return calendarEntryHref(registry, tenant, entry, hint);
}

export function livedOrderUrl(tenant: string, beingId: string): string | null {
  const template = registry?.links.lived_order;
  return template ? fill(template, { tenant, id: beingId }) : null;
}
