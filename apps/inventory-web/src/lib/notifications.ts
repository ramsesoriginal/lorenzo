import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';

/** How many the bell's dropdown lists. */
export const RECENT_SIZE = 10;

/** The newest notifications, newest first, with how many are unread in all. */
export async function loadRecent() {
  const [recent, unread] = await Promise.all([
    unwrap(
      await client.GET('/me/notifications', { params: { query: { page: 1, size: RECENT_SIZE } } }),
    ),
    // The envelope's own total is the count; one item keeps it cheap (ADR 0085).
    unwrap(
      await client.GET('/me/notifications', {
        params: { query: { unread_only: true, page: 1, size: 1 } },
      }),
    ),
  ]);

  return { items: recent.items, unread: unread.total };
}

export async function markRead(id: string): Promise<void> {
  await unwrap(
    await client.POST('/me/notifications/{notification_id}/read', {
      params: { path: { notification_id: id } },
    }),
  );
}

/**
 * Every unread one, not only those listed. There is no read-all route, so each is marked in
 * turn; the ones that failed are counted, and the next load shows what is still unread.
 */
export async function markAllRead(): Promise<{ failed: number }> {
  const unread = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/me/notifications', {
        params: { query: { unread_only: true, page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
  const results = await Promise.allSettled(unread.map((n) => markRead(n.id)));

  return { failed: results.filter((r) => r.status === 'rejected').length };
}
