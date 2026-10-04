import { tenantNamed } from '../../lib/addresses';
import { currentTenant, rememberTenant } from '../../lib/lastTenant';
import { requiredIn } from '../../lib/template';
import { listTenants } from '../../lib/tenants';

const required = requiredIn('Site header');

// Only for someone with more than one library. Switching stays on the board or the catalog, of
// the other library; anything else (an item, home) goes to its board, since what it shows
// belongs to the library being left.
export async function renderTenantSwitcher(root: HTMLElement): Promise<void> {
  const { items: tenants } = await listTenants();

  if (tenants.length < 2) return;

  const switcher = required<HTMLSelectElement>(root, '[data-tenant-switcher]');
  const named = currentTenant();
  const current = named ? tenantNamed(tenants, named)?.id : undefined;

  if (!current) switcher.append(new Option('Choose a library…', '', true, true));

  for (const tenant of tenants) {
    switcher.append(new Option(tenant.name, tenant.id, false, tenant.id === current));
  }

  switcher.addEventListener('change', () => {
    if (!switcher.value) return;

    rememberTenant(switcher.value);

    const path = ['/board/', '/items/'].includes(window.location.pathname)
      ? window.location.pathname
      : '/board/';

    window.location.assign(`${path}?tenant=${encodeURIComponent(switcher.value)}`);
  });

  // The whole group, icon included - not a lone icon without its switcher.
  required<HTMLElement>(root, '[data-tenant-switcher-group]').hidden = false;
}
