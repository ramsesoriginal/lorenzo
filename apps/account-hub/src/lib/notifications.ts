import { client, unwrap } from './api';
import type { Notification, Page } from './types';

// The API caps `size` at 100; this app doesn't yet implement a pager UI
// (a later slice, if the 50-notification page ever isn't enough - see
// RFC 0013), so this just asks for its default page size explicitly.
const PAGE_SIZE = 50;

export async function listNotifications(unreadOnly = false): Promise<Page<Notification>> {
  return unwrap(
    await client.GET('/me/notifications', {
      params: { query: { page: 1, size: PAGE_SIZE, unread_only: unreadOnly } },
    }),
  );
}

// ADR 0085 - a nav badge only needs the pagination envelope's own count,
// not the items themselves, so size=1 (not PAGE_SIZE) keeps this cheap
// regardless of inbox size.
export async function getUnreadCount(): Promise<number> {
  const page = await unwrap(
    await client.GET('/me/notifications', {
      params: { query: { unread_only: true, page: 1, size: 1 } },
    }),
  );
  return page.total;
}

export async function markNotificationRead(id: string): Promise<Notification> {
  return unwrap(
    await client.POST('/me/notifications/{notification_id}/read', {
      params: { path: { notification_id: id } },
    }),
  );
}

// RFC 0017 (h) - the sender's side of read receipts (ADR 0061). Optional
// batchId pulls just one broadcast's full recipient list and read state.
export async function listSentNotifications(batchId?: string): Promise<Page<Notification>> {
  return unwrap(
    await client.GET('/me/notifications/sent', {
      params: { query: { page: 1, size: PAGE_SIZE, batch_id: batchId } },
    }),
  );
}
