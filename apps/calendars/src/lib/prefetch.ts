import { client, unwrap } from './api';
import { calendarReads } from './read-cache';

// Two active requests, eight queued, sixteen distinct intentions per view.
const queue: Array<() => Promise<unknown>> = [];
const seen = new Set<string>();
let active = 0;
function pump() {
  while (active < 2 && queue.length) {
    const read = queue.shift();
    if (!read) break;
    active++;
    void read()
      .catch(() => {})
      .finally(() => {
        active--;
        pump();
      });
  }
}
export function prefetch(key: string, read: () => Promise<unknown>) {
  if (!calendarReads.canPrefetch() || seen.has(key) || seen.size >= 16 || queue.length >= 8) return;
  seen.add(key);
  queue.push(read);
  pump();
}
export function prefetchEntry(tenant: string, id: string) {
  prefetch(`entry/${tenant}/${id}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: id } },
      }),
    ),
  );
}
export function prefetchCalendar(tenant: string, id: string) {
  prefetchEntry(tenant, id);
  prefetch(`calendar/${tenant}/${id}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: id } },
      }),
    ),
  );
}
export function prefetchYear(tenant: string, id: string, year: number) {
  if (Math.abs(year) > 1000000) return;
  const path = { tenant_id: tenant, calendar_id: id };
  prefetch(`year/${tenant}/${id}/${year}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
        params: { path: { tenant_id: tenant, entity_id: id, year } },
      }),
    ),
  );
  prefetch(`periods/${tenant}/${id}/${year}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
        params: { path, query: { year, page: 1, size: 100 } },
      }),
    ),
  );
  prefetch(`observances/${tenant}/${id}/${year}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{calendar_id}/years/{year}/observances', {
        params: { path: { ...path, year }, query: { page: 1, size: 100 } },
      }),
    ),
  );
}
if (typeof document !== 'undefined')
  document.addEventListener('astro:before-swap', () => {
    queue.length = 0;
    seen.clear();
  });
