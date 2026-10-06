import { getUserInfo, isAuthConfigured, isAuthenticated, login, logout } from '../../lib/auth';
import { sayError } from '../../lib/statusLine';
import { required } from './required';

export type AccountOptions = {
  // Someone is signed in.
  onSignedIn(): Promise<void>;
};

// Who's signed in, with log in and out. The auth redirect page is still finishing the login, so
// it shows neither.
export async function renderAccount(root: HTMLElement, options: AccountOptions): Promise<void> {
  const loading = required<HTMLElement>(root, '[data-account-loading]');
  const error = required<HTMLElement>(root, '[data-account-error]');

  function fail(cause: unknown) {
    loading.hidden = true;
    sayError(error, cause);
  }

  if (window.location.pathname.startsWith('/auth/')) {
    loading.hidden = true;

    return;
  }

  if (!isAuthConfigured()) {
    fail(new Error('Authgear is not configured for this app yet.'));

    return;
  }

  required<HTMLElement>(root, '[data-login]').addEventListener('click', () => void login());
  required<HTMLElement>(root, '[data-logout]').addEventListener('click', () => void logout());

  try {
    if (!(await isAuthenticated())) {
      loading.hidden = true;
      required<HTMLElement>(root, '[data-account-signed-out]').hidden = false;

      return;
    }

    const info = await getUserInfo();

    loading.hidden = true;
    required<HTMLElement>(root, '[data-account-email]').textContent = info.email ?? info.sub;
    required<HTMLElement>(root, '[data-account-signed-in]').hidden = false;
  } catch (cause) {
    fail(cause);

    return;
  }

  // Just a convenience - on failure, the header stays without it.
  options.onSignedIn().catch(() => {});
}
