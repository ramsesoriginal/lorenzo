import { getAppLinks } from '@lorenzo/api-client';
import { rememberTenantAddress, tenantAddress } from './addresses';
import { client, fetchAllPages, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { message } from './dom';
import { currentTenant, rememberTenant } from './lastTenant';
import { calendarReads } from './read-cache';
import { bindThemeToggle } from './theme';
export type Session = {
  tenantId: string;
  canWrite: boolean;
  canOrderEvents: boolean;
  canReadEventOrder: boolean;
};
export async function start(): Promise<Session | null> {
  calendarReads.suspend();
  const status = document.querySelector<HTMLElement>('[data-session]');
  if (!status) return null;
  bindThemeToggle();
  const signIn = document.querySelector<HTMLButtonElement>('[data-login]');
  signIn?.addEventListener('click', () => {
    sessionStorage.setItem('lorenzo:calendars:return', location.pathname + location.search);
    void login().catch((e) => {
      status.textContent = message(e);
    });
  });
  document.querySelector('[data-logout]')?.addEventListener('click', () => {
    void logout();
  });
  try {
    const registry = await getAppLinks(API_BASE_URL);
    const hub = document.querySelector<HTMLAnchorElement>('[data-hub]');
    if (hub && registry.apps.account_hub) {
      hub.href = registry.apps.account_hub.url;
      hub.hidden = false;
    }
  } catch {
    /* Calendar reading does not depend on the app registry. */
  }
  if (!isAuthConfigured()) {
    status.textContent = 'Sign-in for this calendar app is not set up yet.';
    return null;
  }
  try {
    if (!(await isAuthenticated())) {
      calendarReads.clear();
      status.textContent = 'Log in to open the calendars in your libraries.';
      if (signIn) signIn.hidden = false;
      return null;
    }
    const out = document.querySelector<HTMLElement>('[data-logout]');
    if (out) out.hidden = false;
    const viewer = await unwrap(await client.GET('/me'));
    const tenants = await fetchAllPages(async (page) =>
      unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
    );
    if (!status.isConnected) return null;
    const picker = document.querySelector<HTMLSelectElement>('[data-library]');
    if (!picker || !tenants.length) {
      calendarReads.clear();
      status.textContent = 'There are no libraries available to this account yet.';
      return null;
    }
    const explicit = new URLSearchParams(location.search).get('tenant');
    const requested = currentTenant();
    const tenant =
      (requested ? tenants.find((t) => t.id === requested || t.slug === requested) : undefined) ??
      (explicit ? undefined : tenants[0]);
    if (!tenant) {
      calendarReads.clear();
      status.textContent =
        'This library is not available to this account. Open Calendars to choose a library.';
      return null;
    }
    for (const t of tenants) {
      const o = document.createElement('option');
      o.value = t.id;
      o.textContent = t.name;
      picker.append(o);
    }
    picker.value = tenant.id;
    rememberTenant(tenant.id);
    for (const t of tenants) rememberTenantAddress(t.id, t.slug);
    const address = new URL(location.href);
    address.searchParams.set('tenant', tenantAddress(tenant.id));
    history.replaceState(history.state, '', address);
    picker.addEventListener('change', () => {
      rememberTenant(picker.value);
      location.assign(`/?tenant=${encodeURIComponent(tenantAddress(picker.value))}`);
    });

    let canOrderEvents = false;
    let canReadEventOrder = false;
    {
      const access = await unwrap(
        await client.GET('/tenants/{tenant_id}/events/access', {
          params: { path: { tenant_id: tenant.id } },
        }),
      );
      canOrderEvents = access.can_order;
      canReadEventOrder = access.can_read_order;
    }
    if (!status.isConnected) return null;
    calendarReads.configure(viewer.id, tenant.id, tenant.role, canOrderEvents);
    document.querySelector<HTMLElement>('[data-library-field]')?.removeAttribute('hidden');
    document.querySelector<HTMLElement>('[data-page]')?.removeAttribute('hidden');
    status.hidden = true;
    document.querySelector<HTMLElement>('[data-welcome]')?.setAttribute('hidden', '');
    return {
      tenantId: tenant.id,
      canWrite: ['owner', 'orga', 'author'].includes(tenant.role),
      canOrderEvents,
      canReadEventOrder,
    };
  } catch (e) {
    calendarReads.clear();
    status.textContent = message(e);
    if (signIn) signIn.hidden = false;
    return null;
  }
}
