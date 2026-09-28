// What an address names (ADR 0135): each of its ids can be a slug instead, a tenant's or an
// entity's, and this finds the id it stands for.
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { resolveSlugs } from './slugs';
import type { BeingRef, TenantSummary } from './types';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Whether `value` is an id rather than a slug: every id is a UUID. */
export function isId(value: string): boolean {
  return UUID.test(value);
}

/** The one of `tenants` that `value` names, by id or by slug. */
export function tenantNamed(
  tenants: readonly TenantSummary[],
  value: string,
): TenantSummary | undefined {
  return tenants.find((tenant) => (isId(value) ? tenant.id : tenant.slug) === value);
}

const tenantIds = new Map<string, Promise<string | null>>();

/**
 * The id of the tenant `value` names: an id as it is, a slug looked up among the viewer's own
 * libraries, once per page. Null if none of theirs has that slug.
 */
export function tenantIdFor(value: string): Promise<string | null> {
  if (isId(value)) return Promise.resolve(value);
  const known = tenantIds.get(value);
  if (known) return known;
  const finding = fetchAllPages(async (page) =>
    unwrap(await client.GET('/tenants', { params: { query: { page, size: MAX_PAGE_SIZE } } })),
  ).then((tenants) => tenantNamed(tenants, value)?.id ?? null);
  finding.catch(() => tenantIds.delete(value));
  tenantIds.set(value, finding);
  return finding;
}

/** What a page's `?tenant=` names: its id, or null and why (nothing, if there's no `?tenant=`). */
export type AddressedTenant = { id: string; problem: null } | { id: null; problem: string | null };

export async function addressedTenant(value: string | null): Promise<AddressedTenant> {
  if (!value) return { id: null, problem: null };
  try {
    const id = await tenantIdFor(value);
    if (id) return { id, problem: null };
    return { id: null, problem: `There's no library “${value}” you can see.` };
  } catch (e) {
    return { id: null, problem: e instanceof Error ? e.message : String(e) };
  }
}

/**
 * The being or group `value` names in the tenant: an id as it is, named by itself, else what
 * the slug names. Null if nothing holds that slug.
 */
export async function beingNamed(tenantId: string, value: string): Promise<BeingRef | null> {
  if (isId(value)) return { entity_id: value, name: value };
  const [found] = await resolveSlugs(tenantId, [value]);
  return found ? { entity_id: found.entity_id, name: found.name } : null;
}

export const unknownSlug = (value: string) => `Nothing here has the slug “${value}”.`;
