import { client, unwrap } from './api';
import type { Page, Tenant, TenantSummary } from './types';

export async function listTenants(): Promise<Page<TenantSummary>> {
  return unwrap(await client.GET('/tenants'));
}

export async function getTenant(tenantId: string): Promise<Tenant> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}', {
      params: { path: { tenant_id: tenantId } },
    }),
  );
}
