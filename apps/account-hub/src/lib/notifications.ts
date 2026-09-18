import { apiFetch, apiPost } from './api';
import type { Notification, Page } from './types';

// The API caps `size` at 100; this app doesn't yet implement a pager UI
// (a later slice, if the 50-notification page ever isn't enough - see
// RFC 0013), so this just asks for its default page size explicitly.
const PAGE_SIZE = 50;

export async function listNotifications(unreadOnly = false): Promise<Page<Notification>> {
  const params = new URLSearchParams({ page: '1', size: String(PAGE_SIZE) });
  if (unreadOnly) params.set('unread_only', 'true');
  return apiFetch<Page<Notification>>(`/me/notifications?${params.toString()}`);
}

export async function markNotificationRead(id: string): Promise<Notification> {
  return apiPost<Notification>(`/me/notifications/${id}/read`, undefined);
}

// RFC 0017 (h) - the sender's side of read receipts (ADR 0061). Optional
// batchId pulls just one broadcast's full recipient list and read state.
export async function listSentNotifications(batchId?: string): Promise<Page<Notification>> {
  const params = new URLSearchParams({ page: '1', size: String(PAGE_SIZE) });
  if (batchId) params.set('batch_id', batchId);
  return apiFetch<Page<Notification>>(`/me/notifications/sent?${params.toString()}`);
}
