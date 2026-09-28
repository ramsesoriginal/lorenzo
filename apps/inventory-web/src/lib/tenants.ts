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

export function renderTenantCard(tenant: TenantSummary): HTMLLIElement {
  const template = document.querySelector<HTMLTemplateElement>('#tenant-card-template');

  if (!template) {
    throw new Error('Tenant card template not found');
  }

  const fragment = template.content.cloneNode(true) as DocumentFragment;

  const item = fragment.querySelector<HTMLLIElement>('li')!;
  const link = fragment.querySelector<HTMLAnchorElement>('a')!;
  const name = fragment.querySelector<HTMLElement>('.name')!;
  const badge = fragment.querySelector<HTMLElement>('.badge')!;
  const pill = fragment.querySelector<HTMLElement>('.pill')!;

  link.href = `/board/?tenant=${tenant.id}`;
  name.textContent = tenant.name;
  badge.textContent = `${tenant.role}`;
  if (tenant.kind !== 'play') {
    pill.classList.add('pill-warning');
    pill.textContent = `${tenant.kind}`;
    pill.hidden = false;
  }

  return item;
}
