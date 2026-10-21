import { client, unwrap } from './api';

const tenants = new Map<string, string>();
const names = new Map<string, string>();
export const tenantAddress = (id: string): string => tenants.get(id) ?? id;
export function rememberTenantAddress(id: string, slug?: string | null) {
  tenants.set(id, slug || id);
}
export function rememberEntryAddress(
  tenant: string,
  entry: { id?: string; entity_id?: string; slug?: string | null },
) {
  const id = entry.id ?? entry.entity_id;
  if (id) {
    const key = `${tenant}/${id}`;
    if (entry.slug) names.set(key, entry.slug);
    else names.delete(key);
  }
}
export function namedParams(tenant: string, id: string): URLSearchParams {
  const slug = names.get(`${tenant}/${id}`);
  return new URLSearchParams({ tenant: tenantAddress(tenant), ...(slug ? { slug } : { id }) });
}
export async function resolveAddress(
  tenant: string,
  params: URLSearchParams,
  kind?: string,
): Promise<string> {
  const explicit = params.get('slug');
  const address =
    explicit ?? params.get('id') ?? params.get(kind === 'calendar' ? 'calendar' : 'event');
  if (!address) throw new Error('Choose an entry from your library.');
  if (!explicit && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(address))
    return address;
  const found = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path: { tenant_id: tenant }, query: { slug: [address] } },
    }),
  );
  const entry = found.find((e) => !kind || e.kinds.includes(kind as 'calendar'));
  if (!entry) throw new Error('This entry is not available in this library.');
  rememberEntryAddress(tenant, entry);
  return entry.entity_id;
}
export function canonicalAddress(tenant: string, id: string) {
  const url = new URL(location.href);
  url.searchParams.delete('id');
  url.searchParams.delete('slug');
  for (const [key, value] of namedParams(tenant, id)) url.searchParams.set(key, value);
  history.replaceState(history.state, '', url);
}

if (typeof document !== 'undefined')
  document.addEventListener('astro:before-swap', () => {
    tenants.clear();
    names.clear();
  });
