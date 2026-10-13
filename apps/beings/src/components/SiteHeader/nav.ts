import { tenantIdFor } from '../../lib/addresses';
import {
  currentTenant,
  getLastTenant,
  LAST_TENANT_EVENT,
  rememberTenant,
} from '../../lib/lastTenant';

// Links to a library's pages go to the current one, as the URL names it, and stay hidden until
// there is one. The page being shown is marked.
export async function renderNav(root: HTMLElement): Promise<void> {
  const links = [...root.querySelectorAll<HTMLAnchorElement>('nav a[data-path]')];

  async function update() {
    const tenant = currentTenant();

    if (tenant) {
      // A slug is remembered as the library it names (ADR 0135).
      const tenantId = await tenantIdFor(tenant).catch(() => null);

      if (tenantId && tenantId !== getLastTenant()) rememberTenant(tenantId);
    }

    for (const link of links) {
      const path = link.dataset.path ?? '';

      if (link.hasAttribute('data-needs-tenant')) {
        link.hidden = !tenant;
        link.href = tenant ? `${path}?tenant=${encodeURIComponent(tenant)}` : path;
      }

      if (path === window.location.pathname) link.setAttribute('aria-current', 'page');
    }
  }

  await update();
  window.addEventListener(LAST_TENANT_EVENT, update);
}
