// The notification bell's rules, apart from the page (ADR 0265): what the badge says, where a
// notification leads, and how often to ask again. Pure, so a test can hold them still.

/** The pieces of a notification these rules read (a `NotificationOut`, narrowed). */
export type BellNotification = {
  scope: string;
  type: string;
  tenant_id: string | null;
  source_id: string | null;
};

/** How many the badge shows: nothing for none, and "99+" past two digits. */
export function badgeText(count: number): string {
  if (count <= 0) return '';

  return count > 99 ? '99+' : String(count);
}

/** What a screen reader hears for the bell, which the badge's number alone does not say. */
export function bellLabel(count: number): string {
  if (count <= 0) return 'Notifications, none unread';

  return `Notifications, ${count} unread`;
}

/**
 * The page in this app a notification is about, or null when it is about nothing here (the
 * account hub's list covers those). Only what the API names by id is linked: a library's
 * "items sorted" goes to its board, and a character's message to that character's board.
 */
export function notificationLink(notification: BellNotification): string | null {
  const { tenant_id: tenantId } = notification;

  if (!tenantId) return null;

  const tenant = `tenant=${encodeURIComponent(tenantId)}`;

  if (notification.scope === 'character' && notification.source_id) {
    return `/board/?${tenant}&character=${encodeURIComponent(notification.source_id)}`;
  }

  if (notification.type === 'items_sorted') return `/board/?${tenant}`;

  return null;
}

/** The account hub's notifications page, given its origin. */
export function hubNotificationsUrl(hubBase: string): string {
  return `${hubBase.replace(/\/$/, '')}/notifications/`;
}

const POLL_MS = 60_000;
const BACKOFF_CAP_MS = 5 * 60_000;

/**
 * Milliseconds to wait before asking again, or null to not ask at all: never while the tab is
 * hidden (it asks once when it comes back), every minute normally, and doubling after each
 * failure in a row up to five minutes.
 */
export function pollDelay(visible: boolean, failures: number): number | null {
  if (!visible) return null;

  return Math.min(POLL_MS * 2 ** Math.max(0, failures), BACKOFF_CAP_MS);
}
