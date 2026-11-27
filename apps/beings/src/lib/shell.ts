import { accountPreferences, getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import { tenantNamed } from './addresses';
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { getUserInfo, isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { currentTenant, getLastTenant, rememberTenant } from './lastTenant';

type Shell = NonNullable<ReturnType<typeof bindShell>>;
let started: Shell | null = null;

/** The shell this page started, for a page that says something in its toasts; null before it starts. */
export function currentShell(): Shell | null {
  return started;
}

/**
 * The web shell around every page of Beings (ADR 0410): its header with the library switcher and
 * the account, the palette, the apps sheet, the status bar. The pages keep saying their own
 * loading and sign-in lines; this is only the frame.
 */
export async function startShell(): Promise<void> {
  const shell = bindShell({
    themeKey: 'lorenzo:beings:theme',
    preferences: accountPreferences(client),
    onLogin() {
      void login();
    },
    onLogout() {
      void logout();
    },
  });
  if (!shell) return;
  started = shell;
  shell.palette();
  // The links that belong to a library name the one the address names.
  const named = currentTenant();
  shell.library(named);
  void getAppLinks(API_BASE_URL)
    .then((registry) => {
      if (registry.apps.account_hub) shell.accountLink(registry.apps.account_hub.url);
      shell.apps(registry);
    })
    .catch(() => {});

  // The auth redirect page is still finishing the login: it shows no account yet.
  if (location.pathname.startsWith('/auth/')) return;
  if (!isAuthConfigured()) {
    shell.account({ state: 'signed-out' });
    return;
  }
  shell.account({ state: 'checking' });
  try {
    if (!(await isAuthenticated())) {
      shell.account({ state: 'signed-out' });
      return;
    }
    const info = await getUserInfo();
    shell.account({ state: 'signed-in', label: info.email ?? info.sub });
    shell.statusBar({ sync: 'synced', syncedAt: new Date() });
  } catch {
    shell.account({ state: 'signed-out' });
    return;
  }

  // The libraries, for the switcher. Just a convenience: without them the frame stays as it is.
  try {
    const tenants = await fetchAllPages(async (page) =>
      unwrap(await client.GET('/tenants', { params: { query: { page, size: MAX_PAGE_SIZE } } })),
    );
    const current = named ? tenantNamed(tenants, named) : undefined;
    // A slug is remembered as the library it names (ADR 0135).
    if (current && current.id !== getLastTenant()) rememberTenant(current.id);
    shell.libraries(tenants, current?.id ?? '', (id) => {
      rememberTenant(id);
      location.assign(`/beings/?tenant=${encodeURIComponent(id)}`);
    });
  } catch {
    // The switcher is a convenience.
  }
}
