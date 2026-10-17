import { client, fetchAllPages, unwrap } from '../../lib/api';
import { factPageHref } from '../../lib/entityLinks';

const generations = new WeakMap<HTMLElement, object>();

/** Empty and hidden facts add no section, count or placeholder to the sheet. */
export function renderFactsAbout(host: HTMLElement, tenantId: string, entryId: string): void {
  const generation = {};
  generations.set(host, generation);
  host.dataset.factsAbout = entryId;
  host.hidden = true;
  void fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/facts', {
        params: { path: { tenant_id: tenantId, entity_id: entryId }, query: { page, size: 100 } },
      }),
    ),
  )
    .then((facts) => {
      if (generations.get(host) !== generation || !facts.length) return;
      const heading = document.createElement('h2');
      heading.textContent = 'Facts about this item';
      const list = document.createElement('ul');
      for (const fact of facts) {
        const row = document.createElement('li');
        const link = document.createElement('a');
        link.href = factPageHref(tenantId, fact.id);
        link.textContent = fact.name;
        row.append(link);
        list.append(row);
      }
      host.replaceChildren(heading, list);
      host.hidden = false;
    })
    .catch(() => {});
}
