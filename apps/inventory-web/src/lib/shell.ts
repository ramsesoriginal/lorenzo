import { accountPreferences, getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import { tenantNamed } from './addresses';
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { notificationsUrl } from './appLinks';
import { getUserInfo, isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { ACCOUNT_HUB_URL, API_BASE_URL } from './config';
import { currentTenant, getLastTenant, rememberTenant } from './lastTenant';
import { isCampaignGm } from './me';
import { pollDelay } from './notificationBell';
import { unreadCount } from './notifications';

type Shell = NonNullable<ReturnType<typeof bindShell>>;
let started: Shell | null = null;

/** The shell this page started, for a page that says something in its toasts; null before it starts. */
export function currentShell(): Shell | null {
  return started;
}

/**
 * The notification bell of the shell's header (ADR 0265, ADR 0423): the unread count, linking to the
 * account hub's notifications. It asks on load, on coming back to the tab and every minute while the
 * tab is visible; failing, it keeps what it showed and backs off. Only for someone signed in.
 */
function startBell(shell: Shell): void {
  let failures = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let href = `${ACCOUNT_HUB_URL.replace(/\/$/, '')}/notifications/`;

  void notificationsUrl(ACCOUNT_HUB_URL).then((url) => {
    href = url;
  });

  async function ask() {
    clearTimeout(timer);

    try {
      shell.notifications({ count: await unreadCount(), href });
      failures = 0;
    } catch {
      failures++;
    }

    const delay = pollDelay(document.visibilityState === 'visible', failures);

    if (delay !== null) timer = setTimeout(() => void ask(), delay);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void ask();
  });
  void ask();
}

/**
 * The web shell around every page of Inventory (ADR 0410): its header with the tabs, the library
 * switcher and the account, the palette, the apps sheet, the bell and the status bar. The pages keep
 * saying their own loading and sign-in lines; this is only the frame.
 */
export async function startShell(): Promise<void> {
  const shell = bindShell({
    themeKey: 'lorenzo:inventory:theme',
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
  // The debug page is kept for debugging (ADR 0524); the account menu is the shell's, so it is in the palette.
  shell.palette({
    commands: [
      {
        id: 'inventory.debug',
        name: 'Debug: the raw account data (GET /me)',
        icon: 'command',
        keywords: ['debug', 'me', 'account'],
        run: () => location.assign('/debug/me/'),
      },
    ],
  });
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

  startBell(shell);

  // The libraries, for the switcher, and the tab only a GM has. Just a convenience: without them the
  // frame stays as it is.
  try {
    const tenants = await fetchAllPages(async (page) =>
      unwrap(await client.GET('/tenants', { params: { query: { page, size: MAX_PAGE_SIZE } } })),
    );
    const current = named ? tenantNamed(tenants, named) : undefined;
    // A slug is remembered as the library it names (ADR 0135).
    if (current && current.id !== getLastTenant()) rememberTenant(current.id);
    shell.libraries(tenants, current?.id ?? '', (id) => {
      rememberTenant(id);
      location.assign(`/board/?tenant=${encodeURIComponent(id)}`);
    });
    if (current && (await isCampaignGm(current.id).catch(() => false))) shell.allow('gm');
  } catch {
    // The switcher is a convenience.
  }
}
