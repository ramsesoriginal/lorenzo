import { fetchAllPages, type LorenzoClient, unwrap } from '@lorenzo/api-client';

export type FactsDeps = {
  client: LorenzoClient;
  // Where a Fact's own page is.
  factPageHref(tenantId: string, factId: string): string;
  // "Facts about this item", "Facts about this being".
  heading: string;
};

const generations = new WeakMap<HTMLElement, object>();

/** Empty and hidden facts add no section, count or placeholder to the sheet. */
export function renderFactsAbout(
  deps: FactsDeps,
  host: HTMLElement,
  tenantId: string,
  entryId: string,
): void {
  const { client, factPageHref } = deps;
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
      heading.textContent = deps.heading;
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
