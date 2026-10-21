import { getAppLinks } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL } from './config';
import { message } from './dom';
import { bindThemeToggle } from './theme';
export async function start() {
  bindThemeToggle();
  const status = document.querySelector<HTMLElement>('[data-session]');
  if (!status) return null;
  document.querySelector('[data-login]')?.addEventListener('click', () => {
    sessionStorage.setItem('lorenzo:sessions:return', location.pathname + location.search);
    void login().catch((error) => {
      status.textContent = message(error);
    });
  });
  document.querySelector('[data-logout]')?.addEventListener('click', () => void logout());
  try {
    const registry = await getAppLinks(API_BASE_URL);
    const hub = document.querySelector<HTMLAnchorElement>('[data-hub]');
    if (hub && registry.apps.account_hub) {
      hub.href = registry.apps.account_hub.url;
      hub.hidden = false;
    }
    if (!isAuthConfigured() || !(await isAuthenticated())) {
      status.textContent = 'Log in to prepare sessions and read your group’s notes.';
      document.querySelector<HTMLElement>('[data-login]')?.removeAttribute('hidden');
      return null;
    }
    const me = await unwrap(await client.GET('/me'));
    document.querySelector<HTMLElement>('[data-logout]')?.removeAttribute('hidden');
    document.querySelector<HTMLElement>('[data-welcome]')?.setAttribute('hidden', '');
    document.querySelector<HTMLElement>('[data-page]')?.removeAttribute('hidden');
    return me;
  } catch (error) {
    status.textContent = message(error);
    document.querySelector<HTMLElement>('[data-login]')?.removeAttribute('hidden');
    return null;
  }
}
