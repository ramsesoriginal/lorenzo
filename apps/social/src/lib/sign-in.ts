import { getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import { client, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { message } from './dom';
import { readScope, socialReads } from './read-cache';

export async function start() {
  const shell = bindShell({
    themeKey: 'lorenzo:social:theme',
    onLogin() {
      sessionStorage.setItem('lorenzo:social:return', location.pathname + location.search);
      void login().catch((error) => shell?.status(message(error), 'error'));
    },
    onLogout() {
      void logout();
    },
  });
  if (!shell || !document.querySelector('[data-session]')) return null;
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
    return me;
  } catch (error) {
    shell.account({ state: 'signed-out' });
    shell.status(message(error), 'error');
    return null;
  }
}
