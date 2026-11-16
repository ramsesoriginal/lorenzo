// What the notifications page says and does about a list of them (ADR 0417, the notifications
// screen). Pure, so it is tested without a browser.

import type { Notification } from './types';

/** "3 unread", or that nothing is. */
export function unreadSummary(unread: number): string {
  return unread === 0 ? 'Nothing unread' : `${unread} unread`;
}

/** The ones still to read, in the order shown. */
export function unreadIds(notifications: Pick<Notification, 'id' | 'read_at'>[]): string[] {
  return notifications.filter((n) => n.read_at === null).map((n) => n.id);
}

/** What the empty list says: nothing at all, or nothing unread under the "Unread" view. */
export function emptyWords(unreadOnly: boolean): { title: string; text: string } {
  return unreadOnly
    ? { title: 'You’re all caught up', text: 'Nothing is waiting to be read.' }
    : { title: 'You’re all caught up', text: 'No notifications yet. They will appear here.' };
}
