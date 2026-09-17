import { apiFetch } from './api';
import type { Page, Tenant, TenantSummary } from './types';

export async function listTenants(): Promise<Page<TenantSummary>> {
  return apiFetch<Page<TenantSummary>>('/tenants');
}

export async function getTenant(tenantId: string): Promise<Tenant> {
  return apiFetch<Tenant>(`/tenants/${tenantId}`);
}
