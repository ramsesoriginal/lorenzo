import { getAppLinks } from '@lorenzo/api-client';
import { API_BASE_URL } from './config';
import { hubNotificationsUrl } from './notificationBell';

/**
 * Where "See all" in the notification bell goes. The API's registry of app links says where the
 * account hub lives (ADR 0273); the build's own `PUBLIC_ACCOUNT_HUB_URL` is only what is used
 * until that answers, or when it cannot (offline, an older API without the endpoint).
 */
export async function notificationsUrl(fallbackHub: string): Promise<string> {
  const fallback = hubNotificationsUrl(fallbackHub);
  try {
    const registry = await getAppLinks(API_BASE_URL);
    return registry.links.notifications || fallback;
  } catch {
    return fallback;
  }
}
