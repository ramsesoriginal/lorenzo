import { getAppLinks } from '@lorenzo/api-client';
import { client, fetchAllPages, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { message } from './dom';
import { currentTenant, rememberTenant } from './lastTenant';
export type Session = { tenantId: string; canWrite: boolean };
export async function start(): Promise<Session | null> {
  const status = document.querySelector<HTMLElement>('[data-session]');
  if (!status) return null;
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
      status.textContent = 'Log in to open the calendars in your libraries.';
      if (signIn) signIn.hidden = false;
      return null;
    }
    const out = document.querySelector<HTMLElement>('[data-logout]');
    if (out) out.hidden = false;
    const tenants = await fetchAllPages(async (page) =>
      unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
    );
    const picker = document.querySelector<HTMLSelectElement>('[data-library]');
    if (!picker || !tenants.length) {
      status.textContent = 'There are no libraries available to this account yet.';
      return null;
    }
    const requested = currentTenant();
    const tenant = requested
      ? tenants.find((t) => t.id === requested || t.slug === requested)
      : tenants[0];
    if (!tenant) {
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
    picker.addEventListener('change', () => {
      rememberTenant(picker.value);
      location.assign(`/?tenant=${encodeURIComponent(picker.value)}`);
    });
    document.querySelector<HTMLElement>('[data-library-field]')?.removeAttribute('hidden');
    document.querySelector<HTMLElement>('[data-page]')?.removeAttribute('hidden');
    status.hidden = true;
    return { tenantId: tenant.id, canWrite: ['owner', 'orga', 'author'].includes(tenant.role) };
  } catch (e) {
    status.textContent = message(e);
    if (signIn) signIn.hidden = false;
    return null;
  }
}
