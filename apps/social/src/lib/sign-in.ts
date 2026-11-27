import { accountPreferences, getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import { client, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { entryHref, message } from './dom';
import { canManage, myLibraries } from './names';
import { readScope, socialReads } from './read-cache';
import { findEnds } from './social-api';

let bound: ReturnType<typeof bindShell> = null;

/** The shell the page is in, once `start` has bound it: for toasts, confirmations and states. */
export const shellOf = () => bound;

export async function start() {
  const shell = bindShell({
    themeKey: 'lorenzo:social:theme',
    preferences: accountPreferences(client),
    onLogin() {
      sessionStorage.setItem('lorenzo:social:return', location.pathname + location.search);
      void login().catch((error) => shell?.status(message(error), 'error'));
    },
    onLogout() {
      void logout();
    },
  });
  bound = shell;
  if (!shell || !document.querySelector('[data-session]')) return null;
  // The palette and its go-to keys: the app's pages and actions for this library, and its entries.
  offerPalette(shell, new URLSearchParams(location.search).get('tenant'));
  shell.account({ state: 'checking' });
  // The links that belong to a library name the one the address names.
  const tenant = new URLSearchParams(location.search).get('tenant');
  shell.library(tenant);
  // The registry does not hold the page up.
  void getAppLinks(API_BASE_URL, socialReads.fetch)
    .then((registry) => {
      if (registry.apps.account_hub) shell.accountLink(registry.apps.account_hub.url);
    })
    .catch(() => {});
  try {
    if (!isAuthConfigured() || !(await isAuthenticated())) {
      socialReads.clear();
      shell.account({ state: 'signed-out' });
      shell.status('Log in to see the relationships of your libraries.');
      return null;
    }
    const me = await unwrap(await client.GET('/me'));
    socialReads.configure(readScope(me.id));
    shell.account({ state: 'signed-in', label: me.email ?? undefined });
    shell.status('');
    shell.reveal();
    await offerLibraries(shell, tenant);
    return me;
  } catch (error) {
    shell.account({ state: 'signed-out' });
    shell.status(message(error), 'error');
    return null;
  }
}

/**
 * The libraries, for the switcher (SO1), and what the person may write, for the tabs that are only for
 * those who write (Types and standings, Problems). Both are conveniences: without them the frame stays
 * as it is, and the API decides every write.
 */
async function offerLibraries(
  shell: NonNullable<ReturnType<typeof bindShell>>,
  tenant: string | null,
) {
  try {
    const libraries = await myLibraries();
    shell.libraries(libraries, tenant ?? '', (id) => {
      try {
        localStorage.setItem('lorenzo:social:last-library', id);
      } catch {
        // A library that cannot be remembered is chosen again next time.
      }
      // Another library has other webs and entries: it opens at its webs.
      location.assign(`/webs/?${new URLSearchParams({ tenant: id })}`);
    });
    if (tenant && (await canManage(tenant))) shell.allow('write');
  } catch {
    // The switcher and the writers' tabs are a convenience.
  }
}

/** What the palette offers in Social (ADR 0414): where to go, what to make, and any being or group. */
function offerPalette(shell: NonNullable<ReturnType<typeof bindShell>>, tenant: string | null) {
  const to =
    (path: string, extra: Record<string, string> = {}) =>
    () =>
      location.assign(
        `${path}?${new URLSearchParams({ ...(tenant ? { tenant } : {}), ...extra })}`,
      );
  shell.palette({
    commands: tenant
      ? [
          { id: 'social.webs', name: 'Webs', icon: 'kind-social-web', run: to('/webs/') },
          {
            id: 'social.relationships',
            name: 'Relationships',
            icon: 'kind-relationship',
            run: to('/relationships/'),
          },
          {
            id: 'social.types',
            name: 'Types and standings',
            icon: 'kind-entity',
            keywords: ['standing', 'scale', 'type'],
            run: to('/types/'),
          },
          {
            id: 'social.problems',
            name: 'Problems',
            icon: 'warning',
            keywords: ['doubled', 'chain'],
            run: to('/problems/'),
          },
          {
            id: 'social.new-web',
            name: 'New web…',
            icon: 'add',
            keywords: ['make', 'create'],
            run: to('/webs/', { new: '1' }),
          },
          {
            id: 'social.new-relationship',
            name: 'New relationship…',
            icon: 'add',
            keywords: ['make', 'create', 'tie', 'connect'],
            run: to('/relationships/', { new: '1' }),
          },
        ]
      : [],
    entries: async (query) => {
      if (!tenant) return [];
      const found = await findEnds(tenant, query).catch(() => []);
      return found.map((entry) => ({
        id: `social.entry:${entry.id}`,
        group: 'Entries' as const,
        name: entry.name,
        kind: 'Relationships of',
        app: 'Social',
        icon: 'kind-relationship',
        run: () => location.assign(entryHref(tenant, entry.id)),
      }));
    },
  });
}
