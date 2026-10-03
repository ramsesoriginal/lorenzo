import { client, unwrap } from './api';
import { cloneTemplate, requiredIn } from './template';
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

const required = requiredIn('Tenant card');

export function renderTenantCard(tenant: TenantSummary): HTMLLIElement {
  const item = cloneTemplate<HTMLLIElement>(
    required<HTMLTemplateElement>(document, '#tenant-card-template'),
    'li',
  );
  const kind = required<HTMLElement>(item, '[data-kind]');

  required<HTMLAnchorElement>(item, '[data-link]').href = `/board/?tenant=${tenant.id}`;
  required<HTMLElement>(item, '[data-name]').textContent = tenant.name;
  required<HTMLElement>(item, '[data-role]').textContent = tenant.role;

  if (tenant.kind !== 'play') {
    kind.classList.add('pill-warning');
    kind.textContent = tenant.kind;
    kind.hidden = false;
  }

  return item;
}
