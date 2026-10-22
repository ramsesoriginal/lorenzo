import { getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import { rememberTenantAddress, tenantAddress } from './addresses';
import { client, fetchAllPages, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { message } from './dom';
import { currentTenant, rememberTenant } from './lastTenant';
import { calendarReads, readScope } from './read-cache';
export type Session = {
  tenantId: string;
  canWrite: boolean;
  canCreateEntries: boolean;
  canOrderEvents: boolean;
  canReadEventOrder: boolean;
};
export async function start(): Promise<Session | null> {
  calendarReads.suspend();
  const shell = bindShell({
    themeKey: 'lorenzo:calendars:theme',
    onLogin() {
      sessionStorage.setItem('lorenzo:calendars:return', location.pathname + location.search);
      void login().catch((e) => shell?.status(message(e), 'error'));
    },
    onLogout() {
      void logout();
    },
  });
  const marker = document.querySelector('[data-session]');
  if (!shell || !marker) return null;
  shell.account({ state: 'checking' });
  // The registry, the viewer and the libraries do not wait for one another, and none of them blocks
  // the page: calendar reading does not depend on the registry.
  void getAppLinks(API_BASE_URL, calendarReads.fetch)
    .then((registry) => {
      if (registry.apps.account_hub) shell.accountLink(registry.apps.account_hub.url);
    })
    .catch(() => {});
  if (!isAuthConfigured()) {
    shell.account({ state: 'error', message: 'Sign-in is not set up' });
    shell.status('Sign-in for this calendar app is not set up yet.');
    return null;
  }
  try {
    if (!(await isAuthenticated())) {
      calendarReads.clear();
      shell.account({ state: 'signed-out' });
      shell.status('Log in to open the calendars in your libraries.');
      return null;
    }
    const [viewer, tenants] = await Promise.all([
      client.GET('/me').then(unwrap),
      fetchAllPages(async (page) =>
        unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
      ),
    ]);
    shell.account({ state: 'signed-in', label: viewer.email ?? undefined });
    if (!marker.isConnected) return null;
    if (!tenants.length) {
      calendarReads.clear();
      shell.status('There are no libraries available to this account yet.');
      return null;
    }
    const explicit = new URLSearchParams(location.search).get('tenant');
    const requested = currentTenant();
    const tenant =
      (requested ? tenants.find((t) => t.id === requested || t.slug === requested) : undefined) ??
      (explicit ? undefined : tenants[0]);
    if (!tenant) {
      calendarReads.clear();
      shell.status(
        'This library is not available to this account. Open Calendars to choose a library.',
      );
      return null;
    }
    rememberTenant(tenant.id);
    for (const t of tenants) rememberTenantAddress(t.id, t.slug);
    const address = new URL(location.href);
    address.searchParams.set('tenant', tenantAddress(tenant.id));
    history.replaceState(history.state, '', address);
    shell.library(tenantAddress(tenant.id));
    shell.libraries(
      tenants.map((t) => ({ id: t.id, name: t.name })),
      tenant.id,
      (id) => {
        rememberTenant(id);
        location.assign(`/?tenant=${encodeURIComponent(tenantAddress(id))}`);
      },
    );

    // Entering a protected view revalidates access before anything held is drawn (ADR 0313).
    const access = await unwrap(
      await client.GET('/tenants/{tenant_id}/events/access', {
        params: { path: { tenant_id: tenant.id } },
      }),
    );
    const canOrderEvents = access.can_order;
    const canReadEventOrder = access.can_read_order;
    if (!marker.isConnected) return null;
    calendarReads.configure(
      readScope(viewer.id, tenant.id, tenant.role, {
        canOrder: access.can_order,
        canReadOrder: access.can_read_order,
        canRetainPrivate: access.can_retain_private,
      }),
    );
    shell.status('');
    shell.reveal();
    return {
      tenantId: tenant.id,
      canWrite: ['owner', 'orga', 'author'].includes(tenant.role),
      canCreateEntries: true,
      canOrderEvents,
      canReadEventOrder,
    };
  } catch (e) {
    calendarReads.clear();
    shell.account({ state: 'signed-out' });
    shell.status(message(e), 'error');
    return null;
  }
}
