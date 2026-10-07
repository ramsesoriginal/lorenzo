// One library in the main area: its heading, and the slots of <Tenant /> filled with what the
// person can do with it. Showing another replaces it, and an answer
// that arrives after that is dropped.

import { showLorenzoScript } from '../../lib/lorenzoScript';
import { sayError } from '../../lib/statusLine';
import { bindTabs } from '../../lib/tabs';
import { requiredIn } from '../../lib/template';
import type { MeOut, TenantOut, TenantSummaryOut } from '../../lib/types';
import { renderTenantEdit } from '../TenantEdit/renderer';
import type { TenantHooks } from './hooks';
import { bindLeaveTenant } from './leaveTenant';
import { fillLibrary, loadLibrary } from './library';

export type RenderedTenant = {
  // Shows `tenant`, replacing what was shown.
  show(tenant: TenantSummaryOut): Promise<void>;
  hide(): void;
};

const required = requiredIn('Tenant');

// `root` is the <Tenant /> article.
export function renderTenant(root: HTMLElement, me: MeOut, hooks: TenantHooks): RenderedTenant {
  const name = required<HTMLElement>(root, '[data-name]');
  const role = required<HTMLElement>(root, '[data-role]');
  const slug = required<HTMLElement>(root, '[data-slug]');
  const description = required<HTMLElement>(root, '[data-tenant-description]');
  const loading = required<HTMLElement>(root, '[data-loading]');
  const error = required<HTMLElement>(root, '[data-error]');
  const campaigns = required<HTMLElement>(root, '[data-campaigns]');
  const campaignList = required<HTMLElement>(root, '[data-campaign-list]');
  // Every slot the markup has now: the campaigns' are in a <template>, so not among them.
  const slots = [...root.querySelectorAll<HTMLElement>('[data-slot]')];

  // Only the newest `show` paints.
  let latest = 0;

  const showDescription = (text: string) => showLorenzoScript(description, text);

  // A saved name and slug show in the heading at once, without loading everything again.
  const tenantHooks: TenantHooks = {
    onChanged: hooks.onChanged,
    onRenamed(updated: TenantOut) {
      name.textContent = updated.name;
      slug.textContent = updated.slug;
      showDescription(updated.description);
      hooks.onRenamed(updated);
    },
  };

  // Every slot empty and hidden again, for the next tenant to fill the ones it uses.
  function empty() {
    for (const slot of slots) {
      slot.replaceChildren();
      slot.hidden = true;
    }

    campaignList.replaceChildren();
    campaigns.hidden = true;
    showDescription('');
  }

  // The Edit button is this block's own, bound once for whichever tenant is shown.
  const tenantEdit = renderTenantEdit(
    required<HTMLElement>(root, '[data-tenant-edit]'),
    tenantHooks.onRenamed,
  );

  // The same for the Leave button: it is this block's own, and leaving ends the Membership whichever
  // tenant is shown.
  const leaveTenant = bindLeaveTenant(
    required<HTMLElement>(root, '[data-leave]'),
    me.id,
    hooks.onChanged,
  );

  // The tabs: which of them there are depends on what the open tenant filled in.
  const tabs = bindTabs(required<HTMLElement>(root, '[data-tenant-tabs]'));
  let lastId: string | null = null;

  return {
    async show(tenant) {
      const turn = ++latest;

      root.hidden = false;
      name.textContent = tenant.name;
      slug.textContent = tenant.slug;
      role.textContent = tenant.role;
      tenantEdit.show(tenant);
      leaveTenant.show(tenant);
      error.hidden = true;
      empty();

      // Another tenant starts on its first tab; the same one, loaded again after a change, stays
      // where it was.
      if (tenant.id !== lastId) tabs.reset();

      lastId = tenant.id;
      tabs.refresh();
      loading.hidden = false;

      try {
        const data = await loadLibrary(root, tenant, me);

        if (turn !== latest) return;

        showDescription(data.description);
        fillLibrary(root, tenant, me, tenantHooks, data);
      } catch (cause) {
        if (turn !== latest) return;

        sayError(error, cause);
      } finally {
        if (turn === latest) {
          loading.hidden = true;
          // What the panels hold has changed.
          tabs.refresh();
        }
      }
    },

    hide() {
      latest++;
      root.hidden = true;
    },
  };
}
