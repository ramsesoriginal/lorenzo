import { client, fetchAllPages, unwrap } from './api';

// The words a page uses for where it is: the library and the campaign. They only label the page,
// so a name that cannot be read (no access to the library record) is left out, not an error.
const libraries = new Map<string, Promise<string | null>>();
const campaigns = new Map<string, Promise<string | null>>();

export function libraryName(tenant: string) {
  let name = libraries.get(tenant);
  if (!name) {
    name = client
      .GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant } } })
      .then((result) => (result.response.ok && result.data ? result.data.name : null))
      .catch(() => null);
    libraries.set(tenant, name);
  }
  return name;
}

export function campaignName(tenant: string, campaign: string) {
  const key = `${tenant}/${campaign}`;
  let name = campaigns.get(key);
  if (!name) {
    name = client
      .GET('/tenants/{tenant_id}/campaigns/{campaign_id}', {
        params: { path: { tenant_id: tenant, campaign_id: campaign } },
      })
      .then((result) => (result.response.ok && result.data ? result.data.name : null))
      .catch(() => null);
    campaigns.set(key, name);
  }
  return name;
}

/** Every library the person can open, by id, for a list that spans libraries. */
export async function libraryNames() {
  const names = new Map<string, string>();
  try {
    const all = await fetchAllPages(async (page) =>
      unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
    );
    for (const tenant of all) names.set(tenant.id, tenant.name);
  } catch {
    // Names are a label only.
  }
  return names;
}

// A name is read for one person; the next one to sign in reads their own.
if (typeof window !== 'undefined') {
  window.addEventListener('lorenzo:sign-out', () => {
    libraries.clear();
    campaigns.clear();
  });
}
