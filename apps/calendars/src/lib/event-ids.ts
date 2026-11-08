import { client, fetchAllPages, unwrap } from './api';

const known = new Map<string, Promise<Set<string>>>();

/**
 * Which entries are Events: a dated entry is named and not given a kind, and the Events the person can
 * see are one list, so an entry on it is an Event and any other is a Fact. Asked once for each library
 * and page; a failed read leaves the set empty and is asked again next time.
 */
export function eventIds(tenantId: string): Promise<Set<string>> {
  let ids = known.get(tenantId);
  if (!ids) {
    ids = fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/events', {
          params: { path: { tenant_id: tenantId }, query: { page, size: 100 } },
        }),
      ),
    )
      .then((rows) => new Set(rows.map((row) => row.entity_id)))
      .catch(() => {
        known.delete(tenantId);
        return new Set<string>();
      });
    known.set(tenantId, ids);
  }
  return ids;
}
